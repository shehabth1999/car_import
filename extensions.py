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
