# -*- coding: utf-8 -*-
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.base.models.base import BaseModel


class StageChangeLog(BaseModel):
    """
    One row per stage transition: who moved it, when, and what happened to the
    customer's message. It is the audit trail, the source of days-in-stage, and
    the proof that a customer was actually told.
    """

    NOTIFICATION_STATE = [
        ('pending', _("Pending")),
        ('queued', _("Queued")),
        ('sent', _("Sent")),
        ('failed', _("Failed")),
        ('skipped', _("Skipped — the stage does not notify")),
        ('suppressed', _("Suppressed — migration or opt-out")),
        ('awaiting_approval', _("Waiting for an agent to send")),
    ]

    deal = models.ForeignKey(
        'car_import.CarDeal', on_delete=models.CASCADE,
        related_name='stage_logs', verbose_name=_("Deal"),
    )
    from_stage = models.ForeignKey(
        'car_import.ImportStage', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name=_("From stage"),
    )
    to_stage = models.ForeignKey(
        'car_import.ImportStage', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name=_("To stage"),
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name=_("Moved by"),
    )
    changed_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Moved at"))
    reason = models.CharField(max_length=255, blank=True, verbose_name=_("Reason"))

    notification_state = models.CharField(
        max_length=24, choices=NOTIFICATION_STATE, default='pending',
        verbose_name=_("Message"),
    )
    channel_used = models.CharField(max_length=32, blank=True, verbose_name=_("Channel"))
    message_id = models.CharField(max_length=128, blank=True, verbose_name=_("Message id"))
    message_text = models.TextField(blank=True, verbose_name=_("What was sent"))
    error = models.TextField(blank=True, verbose_name=_("Error"))

    class Meta:
        ordering = ['-changed_at', '-id']
        verbose_name = _("Stage Change")
        verbose_name_plural = _("Stage Changes")
        indexes = [
            models.Index(fields=['deal', '-changed_at']),
            models.Index(fields=['notification_state']),
        ]

    def __str__(self):
        return f"{self.deal_id}: {self.from_stage or '—'} → {self.to_stage or '—'}"
