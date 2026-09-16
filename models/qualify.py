# -*- coding: utf-8 -*-
"""The qualification wizard: what the customer wants, written onto their lead.

Opened from the chat header ("تأهيل العميل") with the customer already filled
in by `ConversationExtension.action_qualify_customer`. Save runs
`action_apply`, which writes the `ka_*` fields the assistant's dynamic
context, the follow-up rules and the funnel dashboard all read — the fields
that never got filled when filling them meant leaving the conversation.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.base.models import TransientModel
from modules.base.decorators import action


class QualifyCustomer(TransientModel):
    partner = models.ForeignKey('base.Partner', on_delete=models.CASCADE, verbose_name=_("Customer"))
    program = models.CharField(max_length=32, blank=True, null=True, verbose_name=_("Programme"), choices=[
        ('initiative', _("Initiative")), ('personal', _("Personal import")),
        ('commercial', _("Commercial import")), ('showroom', _("Showroom car")),
        ('consignment', _("Consignment")),
    ])
    initiative_type = models.CharField(max_length=16, blank=True, null=True, verbose_name=_("Initiative type"),
                                       choices=[('gulf', _("Gulf")), ('european', _("European"))])
    model_wanted = models.CharField(max_length=128, blank=True, null=True, verbose_name=_("Model wanted"))
    model_year_wanted = models.PositiveIntegerField(blank=True, null=True, verbose_name=_("Model year wanted"))
    trim_wanted = models.CharField(max_length=128, blank=True, null=True, verbose_name=_("Trim wanted"))
    colour_wanted = models.CharField(max_length=64, blank=True, null=True, verbose_name=_("Colour wanted"))
    condition_wanted = models.CharField(max_length=16, blank=True, null=True, verbose_name=_("Zero or used"),
                                        choices=[('new', _("Zero")), ('used', _("Used"))])
    budget_eur = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True,
                                     verbose_name=_("Budget (€)"))
    funds_ready_on = models.DateField(blank=True, null=True, verbose_name=_("Funds ready on"))
    residence_country = models.CharField(max_length=64, blank=True, null=True,
                                         verbose_name=_("Country of residence"))
    is_expat = models.BooleanField(default=False, verbose_name=_("Egyptian abroad"))
    note = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("Note"))

    class Meta:
        verbose_name = _("Qualify customer")
        verbose_name_plural = _("Qualify customer")

    @action
    def action_apply(queryset, form):
        """Write the answers onto the customer's latest lead (creating one if
        they have none) and onto the contact, then leave a note in the thread."""
        from django.utils.translation import gettext as _t

        from car_import.services import chat_actions

        partner = form.partner
        lead = chat_actions.lead_for(partner, create=True)
        written = []
        pairs = [
            ('ka_program', form.program), ('ka_initiative_type', form.initiative_type),
            ('ka_model_wanted', form.model_wanted), ('ka_model_year_wanted', form.model_year_wanted),
            ('ka_trim_wanted', form.trim_wanted), ('ka_colour_wanted', form.colour_wanted),
            ('ka_condition_wanted', form.condition_wanted), ('ka_budget_eur', form.budget_eur),
            ('ka_funds_ready_on', form.funds_ready_on),
        ]
        if lead is not None:
            for field, value in pairs:
                if value not in (None, '') and getattr(lead, field, None) != value:
                    setattr(lead, field, value)
                    written.append(field)
            if written:
                lead.save(update_fields=written)
        contact_written = []
        for field, value in (('residence_country', form.residence_country), ('is_expat', form.is_expat)):
            if value not in (None, '', False) and getattr(partner, field, None) != value:
                setattr(partner, field, value)
                contact_written.append(field)
        if contact_written:
            partner.save(update_fields=contact_written)

        summary = chat_actions.qualification_summary(form)
        chat_actions.note(partner, _t("Qualified from the chat: %(summary)s") % {'summary': summary},
                          extra=form.note)
        if lead is None:
            return {'status': True, 'open_mode': 'message',
                    'message': _t("Saved on the contact. No lead exists for this customer, so the "
                                  "programme and the car wanted were not stored — open a lead first."),
                    'data': {}, 'on_success': {'type': 'refresh'}}
        return {'status': True, 'open_mode': 'message',
                'message': _t("Qualification saved: %(summary)s") % {'summary': summary},
                'data': {}, 'on_success': {'type': 'refresh'}}
