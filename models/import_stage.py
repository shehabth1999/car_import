# -*- coding: utf-8 -*-
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.base.fields import AttachmentForeignKeyField
from modules.base.models.base import BaseModel

#: The icon each seeded stage shows on the website's tracking page — Font Awesome 6
#: (solid) class names, because the website already loads Font Awesome 6.
DEFAULT_ICONS = {
    'contract_reserved': 'fa-solid fa-file-signature',
    'signed_and_paid': 'fa-solid fa-money-bill-transfer',
    'purchased': 'fa-solid fa-cart-shopping',
    'received_inspected': 'fa-solid fa-clipboard-check',
    'internal_transport': 'fa-solid fa-truck',
    'at_berlin': 'fa-solid fa-warehouse',
    'prep_for_shipping': 'fa-solid fa-box',
    'awaiting_acid': 'fa-solid fa-hourglass-half',
    'shipped_bl': 'fa-solid fa-ship',
    'at_egypt_port': 'fa-solid fa-anchor',
    'customs_release': 'fa-solid fa-stamp',
    'out_of_port': 'fa-solid fa-truck-fast',
    'delivered': 'fa-solid fa-key',
    'licensing': 'fa-solid fa-id-card',
}


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

    # ── the website's tracking page ─────────────────────────────────────────
    show_on_tracking = models.BooleanField(
        default=True, verbose_name=_("Show on the website tracking page"),
        help_text=_("Off for internal stages the customer should not see as a step"))
    icon_class = models.CharField(
        max_length=64, blank=True, verbose_name=_("Icon (Font Awesome)"),
        help_text=_("A Font Awesome 6 class the website draws, e.g. fa-solid fa-ship"))
    icon = AttachmentForeignKeyField(
        related_name='+', upload_to='car_import/stages/icons', allowed_types=['image'],
        verbose_name=_("Icon image"),
        help_text=_("Optional. When set, the website receives this image's link as well"))

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
                    "Placeholders: {customer_name} {car_full} {model} {model_year} {vin} "
                    "{stage_name} {port} {vessel} {eta} {bl_number} {tracking_url} {deal_ref}. "
                    "Prefer {car_full} over {model} {model_year}: a WhatsApp template may "
                    "not put two placeholders next to each other, even with a space"),
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

    # ── who may move a deal here ────────────────────────────────────────────
    #: The client, 2026-10-07: «الستيج بتاع الشحن تبقى البيرميشن بتاعها مع ناس
    #: محددين». Checked in `CarDeal._check_stage_permission` on every save, so
    #: the button, the kanban drag and the form all obey it.
    allowed_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name='+', verbose_name=_("Only these people move a deal here"),
        help_text=_("When set, nobody else can move a deal INTO this stage — the shipping stage, for "
                    "example. Empty: everyone who can edit deals"),
    )

    class Meta:
        ordering = ['sequence', 'id']
        verbose_name = _("Import Stage")
        verbose_name_plural = _("Import Stages")

    def __str__(self):
        return self.name or self.name_en or self.code
