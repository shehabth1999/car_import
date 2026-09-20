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
        "Use this tool whenever the customer asks which account to transfer to, asks for the bank "
        "details, the account number or the IBAN — with or without an open deal. It sends the company's "
        "approved bank details to the customer BY ITSELF, word for word as the accountant wrote them. "
        "Before calling it you MUST have a one-line reason. After it succeeds, write ONE short line: ask "
        "them to send a screenshot of the transfer here once it is done. Never type an account number, "
        "IBAN or bank name yourself, and never repeat the details from memory — call this tool again."
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
    """Send the accountant's bank details, verbatim."""
    try:
        from django.core.exceptions import ValidationError

        from car_import.models.approval import require
        from car_import.services import policy, sales_flow
        from car_import.tools.deal_tools import _deal_for

        partner = getattr(context, 'partner', None)
        conversation = getattr(context, 'conversation', None)
        if partner is None:
            return {"success": False, "error": "No customer in context", "error_type": "no_partner"}
        deal = _deal_for(context)
        ai_first = policy.ai_first()

        # Under the old policy the details followed a deal and a person's yes.
        # The client's decision of 2026-09-20: "which account do I transfer to?"
        # is answered on the spot, deal or no deal.
        if deal is None and not ai_first:
            return {"success": False, "error": "No open deal for this customer",
                    "error_type": "not_found",
                    "say_to_customer_ar": "قبل ما أبعت بيانات الحساب لازم يكون فيه صفقة مفتوحة لحضرتك — زميلي هيتابع معاك."}

        text = _template()
        if not text:
            # Nothing approved to send. Say so to the people who can fix it —
            # once per question, in the thread — and never improvise an account.
            sales_flow.note(
                partner,
                '\n'.join([
                    '🏦 العميل سأل عن حساب التحويل ومفيش بيانات بنكية متسجّلة.',
                    'ابعتها له بنفسك دلوقتي، وسجّلها في الإعدادات ← مفاتيح التشغيل ← '
                    'car_import.bank_details_text عشان المساعد يبعتها بعد كده.',
                    f'السبب: {reason}',
                ]),
                recipients=(sales_flow.accountants() or sales_flow.owners(partner)),
                conversation=conversation, subject='العميل محتاج بيانات التحويل')
            return {"success": False, "error": "No approved bank details on file",
                    "error_type": "not_configured",
                    "say_to_customer_ar": "بيانات التحويل هتوصل حضرتك من الحسابات حالاً 🙏"}

        if not ai_first:
            try:
                require('bank_details', None, deal=deal, partner=partner,
                        reason=reason or 'سؤال عن بيانات الحساب',
                        user=getattr(context, 'user', None))
            except ValidationError as exc:
                return {"success": False, "error": "; ".join(exc.messages),
                        "error_type": "approval_pending", "must_escalate": True,
                        "say_to_customer_ar": "بيانات الحساب بتتبعت بعد مراجعة سريعة من الإدارة — هوصّلك بزميلي وهو هيبعتهالك."}

        # Sent from here, not relayed by the model: a transposed digit in an
        # IBAN is a transfer that goes to a stranger.
        lines = ['بيانات التحويل:', text]
        if deal is not None:
            lines += ['', f'برجاء كتابة رقم الصفقة {deal.name} في بيان التحويل.']
        body = '\n'.join(lines)
        sent = sales_flow.send_text(partner, body)
        if deal is not None:
            deal.message_post(body=f"بيانات الحساب اتبعتت للعميل. السبب: {reason}")
        sales_flow.note(partner, f'🏦 المساعد بعت بيانات التحويل للعميل. السبب: {reason}',
                        recipients=sales_flow.owners(partner), conversation=conversation,
                        subject='بيانات التحويل اتبعتت')
        if not sent.get('sent'):
            # The channel refused; let the model relay the exact text instead.
            return {"success": True, "data": {"sent_to_customer": False, "bank_details_ar": text,
                                              "note": "Relay the text exactly. Do not add, shorten or reformat it."}}
        return {"success": True, "data": {
            "sent_to_customer": True,
            "deal_reference": deal.name if deal is not None else None,
            "next_step": "The details are already in the chat. Write ONE short line asking them to send "
                         "a screenshot of the transfer here. Do not repeat the details.",
        }}
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
