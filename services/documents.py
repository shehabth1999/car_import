# -*- coding: utf-8 -*-
"""Building and reading a deal's document checklist."""
import logging

logger = logging.getLogger(__name__)


def requirements_for(deal):
    """Every requirement that applies to this deal's programme.

    A requirement with no programme applies to all of them — the national ID is
    wanted whichever route the car takes.
    """
    from django.db.models import Q

    from car_import.models import DocumentRequirement, ImportProgram

    program = ImportProgram.objects.filter(code=deal.program).first()
    rows = DocumentRequirement.in_force().filter(Q(program=program) | Q(program__isnull=True))
    return rows.order_by('sequence', 'code')


def build_checklist(deal):
    """Create the missing lines for a deal, leaving the existing ones alone.

    Idempotent on purpose: it runs when the deal is created, again when the
    programme changes, and again whenever somebody presses the button — and it
    must never wipe a document the customer already sent because the programme
    was corrected afterwards.
    """
    from car_import.models import DealDocument

    created = []
    have = set(DealDocument.objects.filter(deal=deal).values_list('requirement_id', flat=True))
    for requirement in requirements_for(deal):
        if requirement.pk in have:
            continue
        created.append(DealDocument.create(
            deal=deal, requirement=requirement, name=requirement.name, state='missing'))
    return created


def checklist_status(deal):
    """What is still outstanding, in a shape both a screen and a tool can use."""
    from car_import.models import DealDocument

    rows = list(DealDocument.objects.filter(deal=deal).select_related('requirement'))
    blocking = [r for r in rows
                if r.state in DealDocument.BLOCKING
                and (r.requirement is None or r.requirement.mandatory)]
    return {
        'total': len(rows),
        'verified': sum(1 for r in rows if r.state == 'verified'),
        'waiting_check': sum(1 for r in rows if r.state == 'uploaded'),
        'outstanding': [
            {'name': r.name,
             'state': r.state,
             'reason': r.rejection_reason or '',
             'sensitive': bool(r.requirement and r.requirement.is_sensitive)}
            for r in blocking
        ],
        'complete': not blocking and bool(rows),
    }
