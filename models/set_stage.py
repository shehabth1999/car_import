# -*- coding: utf-8 -*-
"""The modal behind "Set stage…".

Its own object because the wizard needs two inputs the deal form has nowhere to
put: which stage, and why. A reason is required, and that is the point of the
whole feature — a deal that moved backwards with nothing written down is the
row somebody argues about at the end of the month.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _

from modules.base.models.mixins import TransientModel


class SetStage(TransientModel):
    """Which stage to jump to, and the reason it is being done by hand."""

    import_stage = models.ForeignKey(
        'car_import.ImportStage', on_delete=models.CASCADE,
        verbose_name=_("Stage"))
    reason = models.CharField(max_length=255, verbose_name=_("Why"))
    #: Off by default, and deliberately so. Ops correcting a mis-click must not
    #: tell a customer their car has un-shipped.
    notify_customer = models.BooleanField(
        default=False, verbose_name=_("Tell the customer too"),
        help_text=_("Off for corrections. On only when the customer really "
                    "should hear about this move"))

    class Meta:
        verbose_name = _("Set stage")
        verbose_name_plural = _("Set stage")

    def __str__(self):
        return f'SetStage({self.import_stage_id})'
