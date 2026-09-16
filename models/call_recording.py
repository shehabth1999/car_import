# -*- coding: utf-8 -*-
"""Call recordings from Dropbox, and what we made of them.

The client's third stated priority, and the only one that touches every deal:
agents call customers all day, and none of it reaches the system.

**Why this lives inside car_import rather than in its own `car_call_summary`
module,** which is what the plan asked for: a deployment carries exactly ONE
extensions repository (`genie.Deployment.extensions_repo_url`, a single
CharField that converge hard-resets), so a second extension package cannot be
installed next to this one without displacing it. Splitting the code would buy
tidiness and cost the client the feature. It sits here, in its own files, and
can be lifted out unchanged the day the platform grows a second slot.

Dropbox is the only source. The Vodafone IVR route was dropped by the owner on
2026-09-14 — "we will never use the vodafone ivr, we will use dropbox only".
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.base.fields import AttachmentForeignKeyField
from modules.base.models.base import BaseModel


class CallRecording(BaseModel):
    """One audio file, and everything we could work out about it."""

    MATCH_STATE = [
        ('unmatched', _("No customer found")),
        ('ambiguous', _("Several customers match")),
        ('matched', _("Matched")),
        ('manual', _("Matched by hand")),
    ]
    PROCESS_STATE = [
        ('new', _("Downloaded")),
        ('transcribing', _("Being transcribed")),
        ('transcribed', _("Transcribed")),
        ('summarised', _("Summarised")),
        ('failed', _("Failed")),
        ('skipped', _("Skipped")),
    ]
    DIRECTION = [
        ('inbound', _("Incoming")),
        ('outbound', _("Outgoing")),
        ('unknown', _("Unknown")),
    ]

    # ── where it came from ──────────────────────────────────────────────────
    # The Dropbox file id, not the path: a file that is moved or renamed keeps
    # its id, and matching on the path re-imports the same call as a new one.
    dropbox_file_id = models.CharField(max_length=128, unique=True, db_index=True,
                                       verbose_name=_("Dropbox file id"))
    dropbox_path = models.CharField(max_length=500, blank=True, verbose_name=_("Path"))
    file_name = models.CharField(max_length=255, blank=True, verbose_name=_("File name"))
    size_bytes = models.PositiveBigIntegerField(null=True, blank=True, verbose_name=_("Size"))
    audio = AttachmentForeignKeyField(upload_to='car_import/calls', null=True, blank=True,
                                      verbose_name=_("Recording"))
    is_simulated = models.BooleanField(default=False, verbose_name=_("Simulated"),
                                       help_text=_("Came from the built-in simulator, not Dropbox"))

    # ── the call ────────────────────────────────────────────────────────────
    recorded_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Recorded at"))
    duration_seconds = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Length (s)"))
    direction = models.CharField(max_length=16, choices=DIRECTION, default='unknown',
                                 verbose_name=_("Direction"))
    customer_phone = models.CharField(max_length=32, blank=True, db_index=True,
                                      verbose_name=_("Customer number"))
    agent = models.ForeignKey('base.User', null=True, blank=True, on_delete=models.SET_NULL,
                              related_name='car_import_calls', verbose_name=_("Agent"))
    agent_folder = models.CharField(max_length=190, blank=True, verbose_name=_("Agent folder"))

    # ── who it was with ─────────────────────────────────────────────────────
    partner = models.ForeignKey('base.Partner', null=True, blank=True, on_delete=models.SET_NULL,
                                related_name='car_import_calls', verbose_name=_("Customer"))
    lead = models.ForeignKey('crm.Lead', null=True, blank=True, on_delete=models.SET_NULL,
                             related_name='car_import_calls', verbose_name=_("Lead"))
    deal = models.ForeignKey('car_import.CarDeal', null=True, blank=True, on_delete=models.SET_NULL,
                             related_name='calls', verbose_name=_("Deal"))
    match_state = models.CharField(max_length=16, choices=MATCH_STATE, default='unmatched',
                                   verbose_name=_("Match"))
    match_note = models.CharField(max_length=255, blank=True, verbose_name=_("Match note"))
    candidates = models.JSONField(default=list, blank=True, verbose_name=_("Possible customers"),
                                  help_text=_("When several numbers matched, rather than guessing"))

    # ── what we made of it ──────────────────────────────────────────────────
    process_state = models.CharField(max_length=16, choices=PROCESS_STATE, default='new',
                                     verbose_name=_("Processing"))
    transcript = models.TextField(blank=True, verbose_name=_("Transcript"))
    summary = models.TextField(blank=True, verbose_name=_("Summary"))
    action_items = models.JSONField(default=list, blank=True, verbose_name=_("Action items"))
    language = models.CharField(max_length=16, blank=True, default='ar', verbose_name=_("Language"))
    error = models.CharField(max_length=500, blank=True, verbose_name=_("Error"))

    # ── consent, because a recording is personal data ───────────────────────
    # Internal by default. The owner asked for summaries on the RECORD, and
    # sending one to the customer is a separate, deliberate act.
    consent_recorded = models.BooleanField(default=False, verbose_name=_("Consent on file"))
    sent_to_customer = models.BooleanField(default=False, verbose_name=_("Sent to the customer"))

    class Meta:
        verbose_name = _("Call recording")
        verbose_name_plural = _("Call recordings")
        ordering = ['-recorded_at', '-id']
        indexes = [
            models.Index(fields=['match_state', 'process_state']),
            models.Index(fields=['recorded_at']),
        ]

    def __str__(self):
        who = getattr(self.partner, 'name', '') or self.customer_phone or self.file_name
        when = self.recorded_at.strftime('%Y-%m-%d %H:%M') if self.recorded_at else '—'
        return f'{who} · {when}'

    @property
    def needs_review(self):
        """A human has to look: nobody matched, or too many did."""
        return self.match_state in ('unmatched', 'ambiguous')
