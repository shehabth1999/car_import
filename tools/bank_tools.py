# -*- coding: utf-8 -*-
"""The one tool that may hand over a bank account — behind a person's yes.

The client's approval matrix: *"Bank account details for a payment —
Accountant's current template only — never decided by an agent or the AI."*
The outbound gate already stops an account number the model invents; this is
the other half. When a customer genuinely needs the details, the assistant
calls this, and this asks management through the same `ApprovalRequest` every
other money decision goes through. Until somebody approves, the tool returns
a refusal the assistant can say out loud, and the request sits in the queue
with the customer's name on it.

The text itself is the accountant's, verbatim, from one config key — not
assembled here from fields, because a transposed digit in an IBAN is a
transfer that goes to a stranger.
"""
import logging
from typing import Any, Dict

from modules.aistudio.tools import tool

logger = logging.getLogger(__name__)

#: The accountant's template, pasted once by management. Empty means "there is
#: nothing approved to send", which the tool says rather than improvising.
BANK_DETAILS_KEY = 'car_import.bank_details_text'


@tool(
    name="ka_share_bank_details",
    display_name="Share the company's bank details",
    description=(
        "Use this tool ONLY when the customer has an open deal, has agreed a price, and asks "
        "where to transfer the money. It returns the company's approved bank details, or a "
        "refusal you must relay if management has not yet approved sharing them with this "
        "customer. Before calling it you MUST have the customer's deal in context. Never type "
        "an account number, IBAN or bank name yourself — only ever relay what this tool returns."
    ),
    category="car_import",
    side_effect=True,
    parameters_schema={
        "type": "object",
        "properties": {
            "reason": {"type": "string",
                       "description": "One line, in Arabic: what the customer is paying for"},
        },
        "required": ["reason"],
    },
)
def ka_share_bank_details(context, reason: str) -> Dict[str, Any]:
    """Approved bank details, or a refusal the assistant can relay."""
    try:
        from django.core.exceptions import ValidationError

        from car_import.models.approval import require
        from car_import.tools.deal_tools import _deal_for

        partner = getattr(context, 'partner', None)
        deal = _deal_for(context)
        if deal is None:
            return {"success": False, "error": "No open deal for this customer",
                    "error_type": "not_found",
                    "say_to_customer_ar": "قبل ما أبعت بيانات الحساب لازم يكون فيه صفقة مفتوحة لحضرتك — زميلي هيتابع معاك."}

        text = _template()
        if not text:
            return {"success": False, "error": "No approved bank details on file",
                    "error_type": "not_configured",
                    "say_to_customer_ar": "بيانات الحساب زميلي هو اللي هيبعتها لحضرتك — ثانية واحدة وهوصّلك بيه."}

        try:
            from car_import.services import policy
            # The client's decision of 2026-09-20: the assistant sends the
            # accountant's approved template itself. The text is still the
            # accountant's, verbatim — what went away is the per-customer ask.
            if not policy.ai_first():
                require('bank_details', None, deal=deal, partner=partner,
                        reason=reason or 'سؤال عن بيانات الحساب',
                        user=getattr(context, 'user', None))
        except ValidationError as exc:
            # Asked, not answered yet. The request is in the queue with the
            # customer's name on it; the assistant says a person will send it.
            return {"success": False, "error": "; ".join(exc.messages),
                    "error_type": "approval_pending",
                    "must_escalate": True,
                    "say_to_customer_ar": "بيانات الحساب بتتبعت بعد مراجعة سريعة من الإدارة — هوصّلك بزميلي وهو هيبعتهالك."}

        deal.message_post(body=f"بيانات الحساب اتبعتت للعميل. السبب: {reason}")
        return {"success": True, "data": {"bank_details_ar": text, "deal_reference": deal.name,
                                          "note": "Relay the text exactly. Do not add, shorten or reformat it."}}
    except Exception as e:
        logger.exception("ka_share_bank_details failed")
        return {"success": False, "error": str(e), "error_type": "unknown"}


def _template():
    try:
        from modules.base.models import ConfigParameter
        row = ConfigParameter.objects.filter(key=BANK_DETAILS_KEY).values('value').first()
    except Exception:
        return ''
    return str((row or {}).get('value') or '').strip()
