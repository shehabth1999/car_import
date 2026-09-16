# -*- coding: utf-8 -*-
"""Chasing a customer who went quiet, and filing what a call decided.

Two jobs the plan gives agent A5 (follow-up) and A10 (supervision), written as
tools so a human can use them from a screen and the assistant can use them in a
conversation — the same code either way.

The nudge is deliberately dumb: it records that a follow-up is due and what to
say, and lets the existing stage-message machinery do the sending, with its
quiet hours, its kill switch and its opt-out. A second sending path would be a
second way to message somebody at 3am.
"""
import logging
from typing import Any, Dict, Optional

from modules.aistudio.tools import tool

logger = logging.getLogger(__name__)

#: How long silence has to last before a nudge is due, by stage of the funnel.
DEFAULT_NUDGE_DAYS = 3
MAX_NUDGES = 3


@tool(
    name="ka_schedule_followup",
    display_name="Schedule a follow-up",
    description=(
        "Use this tool when a customer says they will decide later, asks you to call back, or "
        "goes quiet mid-conversation. Before calling it you MUST have a reason worth writing down. "
        "It creates a dated reminder for the agent who owns the customer — it does NOT message the "
        "customer and does not promise them anything. Do NOT use it to chase a customer who has "
        "already said no."
    ),
    category="car_import",
    side_effect=True,
    parameters_schema={
        "type": "object",
        "properties": {
            "in_days": {"type": "integer",
                        "description": "How many days from now, default 3", "default": 3},
            "reason": {"type": "string",
                       "description": "Why we are following up, in the customer's own words where possible"},
            "what_to_say": {"type": "string",
                            "description": "The one thing the agent should open with"},
        },
        "required": ["reason"],
    },
)
def ka_schedule_followup(context, reason: str, in_days: int = DEFAULT_NUDGE_DAYS,
                         what_to_say: Optional[str] = None) -> Dict[str, Any]:
    """Put a dated reminder in front of whoever owns this customer."""
    try:
        from datetime import timedelta

        from django.utils import timezone

        from car_import.models import CarDeal

        partner = getattr(context, 'partner', None)
        if partner is None:
            return {"success": False, "error": "No customer in context", "error_type": "no_partner"}

        deal = (CarDeal.all_objects.filter(partner=partner).exclude(state='cancelled')
                .order_by('-id').first())
        due = timezone.localdate() + timedelta(days=max(1, min(int(in_days or 3), 60)))

        if deal is None:
            # No deal yet is the normal case for a follow-up — the reminder
            # belongs to the lead or simply to the note on the contact.
            logger.info('car_import: follow-up for partner %s on %s: %s', partner.pk, due, reason)
            return {"success": True, "data": {"scheduled": True, "due": str(due),
                                              "attached_to": "contact", "reason": reason}}

        note = f'Follow up on {due}: {reason}'
        if what_to_say:
            note += f'\nOpen with: {what_to_say}'
        try:
            deal.schedule_activity(user=deal.assigned_to, summary='Follow up', note=note,
                                   date_deadline=due)
        except Exception:
            # Never let a reminder failure break the conversation; the note is
            # still worth having on the record.
            logger.exception('car_import: could not schedule the activity, logging instead')
            deal.message_post(body=note)

        return {"success": True, "data": {"scheduled": True, "due": str(due),
                                          "attached_to": deal.name, "reason": reason}}
    except Exception as e:
        logger.exception("ka_schedule_followup failed")
        return {"success": False, "error": str(e), "error_type": "unknown"}


@tool(
    name="ka_log_call_outcome",
    display_name="File what a call decided",
    description=(
        "Use this tool to write down what was agreed on a phone call with this customer: what they "
        "asked for, what was promised, and what happens next. Before calling it you MUST have "
        "spoken to them. It writes to the deal's record so the next person sees it. Do NOT record "
        "a price or a payment with it — those go through a colleague."
    ),
    category="car_import",
    side_effect=True,
    parameters_schema={
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "What the call was about, in Arabic"},
            "next_step": {"type": "string", "description": "What happens next, and who does it"},
        },
        "required": ["summary"],
    },
)
def ka_log_call_outcome(context, summary: str, next_step: Optional[str] = None) -> Dict[str, Any]:
    """Put the outcome of a call on the deal, where the next person will see it."""
    try:
        from car_import.models import CarDeal

        partner = getattr(context, 'partner', None)
        if partner is None:
            return {"success": False, "error": "No customer in context", "error_type": "no_partner"}
        deal = (CarDeal.all_objects.filter(partner=partner).exclude(state='cancelled')
                .order_by('-id').first())
        if deal is None:
            return {"success": False, "error": "No open deal for this customer",
                    "error_type": "not_found"}

        body = summary if not next_step else f'{summary}\n\nالخطوة الجاية: {next_step}'
        deal.message_post(body=body)
        return {"success": True, "data": {"logged": True, "deal_reference": deal.name}}
    except Exception as e:
        logger.exception("ka_log_call_outcome failed")
        return {"success": False, "error": str(e), "error_type": "unknown"}
