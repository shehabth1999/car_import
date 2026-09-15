# -*- coding: utf-8 -*-
"""
Moving a deal from one stage to the next, with the gates the SOP asks for.

Every move goes through here, so the log and the customer message are never
skipped by accident. The stage list itself is data (`ImportStage`), so ops can
reorder or rename without touching this file.
"""
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


def stages():
    from car_import.models import ImportStage
    return list(ImportStage.objects.filter(active=True).order_by('sequence', 'id'))


def next_stage(stage):
    """The stage after this one, or None at the end of the pipeline."""
    ordered = stages()
    if stage is None:
        return ordered[0] if ordered else None
    for current, following in zip(ordered, ordered[1:]):
        if current.pk == stage.pk:
            return following
    return None


def move_to_next(deal, reason=''):
    """Advance one stage. The log and the customer's message follow from the save."""
    target = next_stage(deal.import_stage)
    if target is None:
        raise ValidationError(_("This deal is already at the last stage."))
    return set_stage(deal, target, reason=reason)


def set_stage(deal, stage, reason=''):
    """
    Jump to any stage, forwards or back, with a reason.

    Moving backwards is allowed on purpose — ops sometimes correct a mistake —
    and the log keeps both the old and the new stage so the history stays honest.
    """
    check_gates(deal, stage)
    deal.import_stage = stage
    if reason:
        deal.blocked_reason = reason
    deal.save()
    return deal


def check_gates(deal, stage):
    """
    Refuse a move the business would refuse.

    Only the gates the client has actually confirmed live here. Anything still
    open (the customs gate for financed deals, F4) stays out until they answer,
    because a wrong gate stops real cars.
    """
    if deal.state in ('cancelled',):
        raise ValidationError(_("This deal is cancelled. Reopen it before moving stages."))
    if stage is None:
        raise ValidationError(_("Choose a stage."))
    if deal.stage_is_blocked:
        raise ValidationError(
            _("This deal is blocked: %(reason)s") % {'reason': deal.blocked_reason or _("no reason given")}
        )
