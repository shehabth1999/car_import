# -*- coding: utf-8 -*-
"""The customer's paperwork: what is required, and what has actually arrived.

The eligibility tool has always been able to LIST the documents a route needs.
Nothing tracked whether any of them turned up, who checked them, or whether the
residence permit expired three weeks before the contract was signed — which is
the kind of thing that stops a car at the port.

Two tables, deliberately:

* `DocumentRequirement` — the checklist per programme. Configuration, edited by
  management, dated like every other rule in this module.
* `DealDocument` — one line per deal per requirement, with the file, the state
  and who verified it.

The states are `missing → uploaded → verified`, with `rejected` and `expired`
as the two ways it goes backwards. `expired` is not a synonym for `rejected`:
a rejected document was wrong, an expired one was right and stopped being so,
and the customer needs a different sentence for each.
"""
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from modules.base.fields import AttachmentForeignKeyField
from modules.base.models.base import BaseModel

from .reference_data import EffectiveMixin


class DocumentRequirement(BaseModel, EffectiveMixin):
    """One document a programme asks for."""

    code = models.CharField(max_length=64, verbose_name=_("Code"))
    name = models.CharField(max_length=190, verbose_name=_("Name"))
    name_en = models.CharField(max_length=190, blank=True, verbose_name=_("Name (English)"))
    program = models.ForeignKey('car_import.ImportProgram', null=True, blank=True,
                                on_delete=models.CASCADE, related_name='document_requirements',
                                verbose_name=_("Programme"),
                                help_text=_("Leave empty to ask for it on every route"))
    sequence = models.PositiveIntegerField(default=10, verbose_name=_("Sequence"))
    mandatory = models.BooleanField(default=True, verbose_name=_("Mandatory"))
    # A residence permit and a passport expire; a birth certificate does not.
    expires = models.BooleanField(default=False, verbose_name=_("Has an expiry date"))
    # Some of these are national IDs and passports. The brief treats them as
    # confidential, so the checklist itself records which lines are sensitive.
    is_sensitive = models.BooleanField(default=False, verbose_name=_("Confidential"))
    ask_at_stage = models.ForeignKey('car_import.ImportStage', null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='document_requirements',
                                     verbose_name=_("Ask for it at"),
                                     help_text=_("Empty means: as soon as the deal exists"))
    notes = models.TextField(blank=True, verbose_name=_("Notes"))

    class Meta:
        verbose_name = _("Document requirement")
        verbose_name_plural = _("Document requirements")
        ordering = ['program', 'sequence', 'code']
        constraints = [
            models.UniqueConstraint(fields=['code', 'program'], name='uniq_doc_requirement'),
        ]

    def __str__(self):
        return f'{self.name} ({self.program or "all routes"})'


class DealDocument(BaseModel):
    """One required document, for one deal, in whatever state it is in."""

    STATE = [
        ('missing', _("Not received")),
        ('uploaded', _("Received, not checked")),
        ('verified', _("Verified")),
        ('rejected', _("Rejected")),
        ('expired', _("Expired")),
    ]
    #: The two states that mean the deal cannot proceed on this line.
    BLOCKING = ('missing', 'rejected', 'expired')

    deal = models.ForeignKey('car_import.CarDeal', on_delete=models.CASCADE,
                             related_name='documents', verbose_name=_("Deal"))
    requirement = models.ForeignKey(DocumentRequirement, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='deal_documents',
                                    verbose_name=_("Requirement"))
    name = models.CharField(max_length=190, verbose_name=_("Document"))
    state = models.CharField(max_length=16, choices=STATE, default='missing',
                             verbose_name=_("State"))
    file = AttachmentForeignKeyField(
        upload_to='car_import/documents', null=True, blank=True,
        verbose_name=_("File"), help_text=_("The scan or photo the customer sent"))
    received_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Received"))
    verified_by = models.ForeignKey('base.User', null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='car_import_verified_documents',
                                    verbose_name=_("Checked by"))
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Checked on"))
    expires_on = models.DateField(null=True, blank=True, verbose_name=_("Expires on"))
    rejection_reason = models.CharField(max_length=255, blank=True,
                                        verbose_name=_("Why it was rejected"))
    note = models.TextField(blank=True, verbose_name=_("Note"))

    class Meta:
        verbose_name = _("Deal document")
        verbose_name_plural = _("Deal documents")
        ordering = ['deal', 'requirement__sequence', 'id']
        constraints = [
            models.UniqueConstraint(fields=['deal', 'requirement'], name='uniq_deal_document'),
        ]
        indexes = [models.Index(fields=['deal', 'state'])]

    def __str__(self):
        return f'{self.name}: {self.get_state_display()}'

    def pre_save(self):
        super().pre_save()
        # An expiry date that has passed outranks whatever the row says: a
        # document verified in March is not verified in June if it ran out in
        # May, and nobody is going to re-check it by hand.
        if self.expires_on and self.expires_on < timezone.localdate() \
                and self.state in ('uploaded', 'verified'):
            self.state = 'expired'
        if self.state == 'verified' and self.verified_at is None:
            self.verified_at = timezone.now()
        if self.state in ('uploaded', 'verified') and self.received_at is None:
            self.received_at = timezone.now()
