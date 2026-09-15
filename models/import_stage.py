# -*- coding: utf-8 -*-
from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.base.models.base import BaseModel


class ImportStage(BaseModel):
    """
    One shipping stage and the message the customer gets when a deal enters it.

    Ops own this table: they rename, reorder and re-colour stages, switch a
    message off, or change its wording, without a developer. The client's list
    (13 stages, confirmed 2026-09-14) is seeded by `seed_import_stages`.
    """

    code = models.CharField(
        max_length=64, unique=True, verbose_name=_("Code"),
        help_text=_("Stable identifier used by the stage machine, e.g. contract_reserved"),
    )
    name = models.CharField(max_length=128, verbose_name=_("Stage name"))
    name_en = models.CharField(max_length=128, blank=True, verbose_name=_("Name (English)"))
    sequence = models.PositiveIntegerField(default=10, verbose_name=_("Sequence"))
    color = models.CharField(max_length=32, blank=True, verbose_name=_("Colour"))
    fold = models.BooleanField(
        default=False, verbose_name=_("Folded in kanban"),
        help_text=_("Closed stages are folded so the pipeline stays readable"),
    )
    is_final = models.BooleanField(
        default=False, verbose_name=_("Final stage"),
        help_text=_("Reaching it marks the deal done"),
    )

    # ── the customer message ────────────────────────────────────────────────
    notify_customer = models.BooleanField(
        default=True, verbose_name=_("Message the customer"),
        help_text=_("Off for internal stages. Cancellation never sends automatically"),
    )
    whatsapp_template = models.ForeignKey(
        'whatsapp.WhatsAppTemplate', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='car_import_stages', verbose_name=_("WhatsApp template"),
        help_text=_("Used outside the 24-hour WhatsApp window"),
    )
    fallback_text_ar = models.TextField(
        blank=True, verbose_name=_("Message text (Arabic)"),
        help_text=_("Used inside the WhatsApp window and on every other channel. "
                    "Placeholders: {customer_name} {model} {model_year} {vin} {stage_name} "
                    "{port} {vessel} {eta} {bl_number} {tracking_url} {deal_ref}"),
    )
    fallback_text_en = models.TextField(blank=True, verbose_name=_("Message text (English)"))
    send_delay_minutes = models.PositiveIntegerField(
        default=0, verbose_name=_("Delay (minutes)"),
        help_text=_("So a late-night stage move does not wake the customer"),
    )
    requires_agent_approval = models.BooleanField(
        default=False, verbose_name=_("Agent presses send"),
        help_text=_("The message waits for an agent instead of going out automatically"),
    )
    attach_media = models.BooleanField(
        default=False, verbose_name=_("Attach media"),
        help_text=_("Stage 6 sends the Berlin photos and video"),
    )

    class Meta:
        ordering = ['sequence', 'id']
        verbose_name = _("Import Stage")
        verbose_name_plural = _("Import Stages")

    def __str__(self):
        return self.name or self.name_en or self.code
