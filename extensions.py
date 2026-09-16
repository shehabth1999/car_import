# -*- coding: utf-8 -*-
"""
What we add to models other modules own.

Only three, and all small — the deal itself is our own model, so there is no
large extension here (decision D24). Fields land in the database through
`sync_schema`, never a migration, and lifecycle hooks are chained by the
dispatcher, so they never call super().
"""
import logging

from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.base.decorators import action
from modules.base.model_inheritance import ModelExtension

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# E1 — the customer
# ═══════════════════════════════════════════════════════════════════════════

class PartnerCarImportExtension(ModelExtension):
    """Identity and profile fields every contract and quote needs."""

    _inherit = 'base.partner'
    _depends = ['car_import']

    # Contracts cannot be generated without these, and they are restricted:
    # only management and operations see them (client, 2026-09-14).
    national_id = models.CharField(max_length=32, blank=True, null=True, verbose_name=_("National ID"))
    passport_number = models.CharField(max_length=32, blank=True, null=True, verbose_name=_("Passport number"))
    nationality = models.CharField(max_length=64, blank=True, null=True, verbose_name=_("Nationality"))
    id_address = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Address on the ID"))

    residence_country = models.CharField(max_length=64, blank=True, null=True, verbose_name=_("Country of residence"))
    is_expat = models.BooleanField(default=False, verbose_name=_("Egyptian abroad"))
    initiative_status = models.CharField(
        max_length=32, blank=True, null=True, verbose_name=_("Initiative"),
        help_text=_("none / gulf / european — drives eligibility and the deposit"),
    )
    budget_band = models.CharField(max_length=64, blank=True, null=True, verbose_name=_("Budget"))
    kyc_complete = models.BooleanField(default=False, verbose_name=_("Documents complete"))
    media_consent = models.BooleanField(
        default=False, verbose_name=_("Agreed to appear in content"),
        help_text=_("The company photographs delivered cars; consent is taken in the contract"),
    )

    # "Stop sending me updates" has to live on the customer, not on a deal: it
    # follows them across every car they ever import.
    stage_messages_opt_out = models.BooleanField(
        default=False, verbose_name=_("No automatic updates"),
        help_text=_("The customer asked not to receive the automatic stage messages. "
                    "Outranks every other switch, including a manual send."),
    )


# ═══════════════════════════════════════════════════════════════════════════
# E2 — the lead, and the button that turns it into a deal
# ═══════════════════════════════════════════════════════════════════════════

class LeadCarImportExtension(ModelExtension):
    """Qualification belongs on the CRM object the funnel already uses."""

    _inherit = 'crm.lead'
    _depends = ['car_import']

    ka_program = models.CharField(
        max_length=24, blank=True, null=True, verbose_name=_("Programme"),
        help_text=_("initiative / personal / commercial / first_owner / showroom / shipping_only"),
    )
    ka_initiative_type = models.CharField(max_length=16, blank=True, null=True, verbose_name=_("Initiative type"))
    ka_model_wanted = models.CharField(max_length=128, blank=True, null=True, verbose_name=_("Model wanted"))
    ka_model_year_wanted = models.PositiveIntegerField(blank=True, null=True, verbose_name=_("Model year wanted"))
    ka_trim_wanted = models.CharField(max_length=128, blank=True, null=True, verbose_name=_("Trim wanted"))
    ka_colour_wanted = models.CharField(max_length=64, blank=True, null=True, verbose_name=_("Colour wanted"))
    ka_condition_wanted = models.CharField(max_length=16, blank=True, null=True, verbose_name=_("Zero or used"))
    ka_budget_eur = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True,
                                        verbose_name=_("Budget (EUR)"))
    ka_funds_ready_on = models.DateField(blank=True, null=True, verbose_name=_("Funds ready on"))
    ka_eligibility_verdict = models.CharField(max_length=32, blank=True, null=True, verbose_name=_("Eligibility"))
    ka_eligibility_reason = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Why"))

    @action
    def action_create_car_deal(queryset):
        """
        Turn a qualified lead into a car deal.

        This replaces the sales quotation flow: `crm_sales` is not installed,
        because it only exists when `sales` is (doc 16 §2).
        """
        from car_import.models import CarDeal, ImportStage

        first_stage = ImportStage.objects.filter(active=True).order_by('sequence', 'id').first()
        created, skipped = [], []
        for lead in queryset:
            partner = getattr(lead, 'partner', None)
            if partner is None:
                skipped.append(lead.name or str(lead.pk))
                continue
            deal = CarDeal.create(
                partner=partner,
                lead=lead,
                assigned_to=getattr(lead, 'assigned_to', None),
                program=(lead.ka_program or 'initiative'),
                import_stage=first_stage,
            )
            created.append(deal)

        message = _("Created %(count)d car deal(s)") % {'count': len(created)}
        if skipped:
            message += "\n" + str(_("No contact on: %(leads)s")) % {'leads': ', '.join(skipped)}

        result = {
            'status': True,
            'open_mode': 'message',
            'message': message,
            'data': {},
            'on_success': {'type': 'refresh'},
        }
        if len(created) == 1:
            # Open the new deal straight away — the agent is already mid-flow.
            result['open_mode'] = 'form'
            result['data'] = {'model': 'car_import.cardeal', 'id': created[0].pk}
        return result


# ═══════════════════════════════════════════════════════════════════════════
# E6 — after-sales tickets point at the deal
# ═══════════════════════════════════════════════════════════════════════════

try:
    from modules.support.models import Ticket  # noqa: F401

    class TicketCarImportExtension(ModelExtension):
        _inherit = 'support.ticket'
        _depends = ['car_import']

        car_deal = models.ForeignKey(
            'car_import.CarDeal', null=True, blank=True, on_delete=models.SET_NULL,
            related_name='tickets', verbose_name=_("Car deal"),
        )
        contract_article = models.CharField(max_length=32, blank=True, null=True,
                                            verbose_name=_("Contract article"))
except Exception:  # pragma: no cover - support is optional in the first release
    logger.info("car_import: support module not installed, skipping the ticket extension")


# ─────────────────────────────────────────────────────────────────────────────
# The chat header: act on the customer of the open conversation
# ─────────────────────────────────────────────────────────────────────────────
class ConversationCarImportExtension(ModelExtension):
    """Four actions in the chat header, all `type: server` on purpose.

    A menu-type button opens static schema, and static schema cannot know
    whose conversation is on screen. Running the action first is the only way
    the form arrives with this customer already in it — which is the whole
    point of a button in the chat. Each action opens an existing form or
    wizard and stops; the forms and their own actions do the work, so the
    kill switch, the opt-out, the approvals and the stage rules all still
    apply. Menu patch: `ui/menu_items/chat_actions.py`.
    """

    _inherit = 'chat.conversation'
    _depends = ['chat', 'car_import']

    @action
    def action_open_or_create_deal(queryset):
        """Open the customer's open deal; if they have none, the create form
        pre-filled with the customer, their lead and its programme."""
        from django.utils.translation import gettext as _t

        from car_import.services import chat_actions as ca

        partner = ca.partner_of(queryset.first() if hasattr(queryset, 'first') else queryset)
        if partner is None:
            return ca.no_customer()
        deal = ca.open_deal_for(partner)
        if deal is not None:
            return {'status': True, 'open_mode': 'slideover', 'data': {
                'menu_item_key': 'car_import_menu_deals', 'view_type': 'form', 'id': deal.pk,
                'type': 'action', 'title': deal.name or _t("Deal")}}
        lead = ca.lead_for(partner)
        defaults = {'partner': ca.ref(partner)}
        if lead is not None:
            defaults['lead'] = ca.ref(lead)
            if getattr(lead, 'ka_program', None):
                defaults['program'] = lead.ka_program
        return {'status': True, 'open_mode': 'slideover', 'data': {
            'menu_item_key': 'car_import_menu_deals', 'view_type': 'form', 'id': None,
            'context': {'default_fields': defaults}, 'type': 'action',
            'title': _t("New deal for %(name)s") % {'name': partner.name}}}

    @action
    def action_new_quote(queryset):
        """A quotation for this customer, on their open deal when there is one."""
        from django.utils.translation import gettext as _t

        from car_import.services import chat_actions as ca

        partner = ca.partner_of(queryset.first() if hasattr(queryset, 'first') else queryset)
        if partner is None:
            return ca.no_customer()
        deal = ca.open_deal_for(partner)
        defaults = {'partner': ca.ref(partner)}
        if deal is not None:
            defaults['deal'] = ca.ref(deal)
            if getattr(deal, 'vehicle_id', None):
                defaults['vehicle'] = ca.ref(deal.vehicle)
        return {'status': True, 'open_mode': 'slideover', 'data': {
            'menu_item_key': 'car_import_menu_quotes', 'view_type': 'form', 'id': None,
            'context': {'default_fields': defaults}, 'type': 'action',
            'title': _t("Quotation for %(name)s") % {'name': partner.name}}}

    @action
    def action_qualify_customer(queryset):
        """The qualification wizard, pre-filled with what the lead already says;
        Save runs QualifyCustomer.action_apply."""
        from django.utils.translation import gettext as _t

        from car_import.services import chat_actions as ca

        partner = ca.partner_of(queryset.first() if hasattr(queryset, 'first') else queryset)
        if partner is None:
            return ca.no_customer()
        lead = ca.lead_for(partner)
        defaults = {'partner': ca.ref(partner),
                    'residence_country': getattr(partner, 'residence_country', None),
                    'is_expat': bool(getattr(partner, 'is_expat', False))}
        if lead is not None:
            for wizard_field, lead_field in (
                    ('program', 'ka_program'), ('initiative_type', 'ka_initiative_type'),
                    ('model_wanted', 'ka_model_wanted'), ('model_year_wanted', 'ka_model_year_wanted'),
                    ('trim_wanted', 'ka_trim_wanted'), ('colour_wanted', 'ka_colour_wanted'),
                    ('condition_wanted', 'ka_condition_wanted'), ('budget_eur', 'ka_budget_eur'),
                    ('funds_ready_on', 'ka_funds_ready_on')):
                value = getattr(lead, lead_field, None)
                if value not in (None, ''):
                    defaults[wizard_field] = str(value) if hasattr(value, 'isoformat') else value
        return {'status': True, 'open_mode': 'slideover', 'data': {
            'view_key': 'car_import_qualify_form_view', 'view_type': 'form', 'id': None,
            'action_name': 'action_apply', 'model': 'car_import.qualifycustomer',
            'selected_ids': [],
            'context': {'default_fields': {k: v for k, v in defaults.items() if v is not None}},
            'type': 'action', 'title': _t("Qualify %(name)s") % {'name': partner.name}}}

    @action
    def action_set_stage_from_chat(queryset):
        """The existing Set-stage wizard, on the customer's open deal. Save runs
        CarDeal.action_set_stage(deal, form) — the same path as the deal form."""
        from django.utils.translation import gettext as _t

        from car_import.services import chat_actions as ca

        partner = ca.partner_of(queryset.first() if hasattr(queryset, 'first') else queryset)
        if partner is None:
            return ca.no_customer()
        deal = ca.open_deal_for(partner)
        if deal is None:
            return {'status': False, 'open_mode': 'message', 'data': {},
                    'message': _t("%(name)s has no open deal to move.") % {'name': partner.name}}
        return {'status': True, 'open_mode': 'slideover', 'data': {
            'view_key': 'car_import_set_stage_form_view', 'view_type': 'form', 'id': None,
            'action_name': 'action_set_stage', 'model': 'car_import.cardeal',
            'selected_ids': [deal.pk],
            'context': {'default_fields': {}},
            'type': 'action',
            'title': _t("Set stage — %(deal)s") % {'deal': deal.name}}}
