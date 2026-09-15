# -*- coding: utf-8 -*-
"""
Car-import tools for AI Studio workflows.

Two rules shape every tool here:

* **The agent never invents a number.** Figures come from these tools or they are
  not said at all — and the ones the client has not confirmed (an instalment
  amount, a down-payment percentage) are deliberately not computed anywhere.
* **Tools speak, the model stays quiet.** A tool that sends something to the
  customer says so in its description, and the agent adds nothing after it.
"""
import logging
from typing import Any, Dict, Optional

from modules.aistudio.tools import tool

logger = logging.getLogger(__name__)

#: Everything the client confirmed on 2026-09-14/15. Kept here, dated, so the
#: agent quotes the company's own figures instead of a model's memory.
FEES = {
    'company_fee_eur': 4750,
    'company_fee_with_eur1_eur': 5250,
    'port_and_clearance_egp': 55000,
    'powers_of_attorney_usd': 300,
    'licensing_service_egp': 3000,
    'protection_film_egp': '65,000–75,000',
    'confirmed_on': '2026-09-14',
}

INSTALMENTS = {
    'down_payment_pct': 50,
    'terms_months': [12, 24],
    'rate_pct_per_year_flat': 27,
    'first_instalment': 'one month after delivery',
    'cheques': 'monthly cheques in EGP from an Egyptian bank account in the customer\'s own name',
    'price_fixing': 'the price is fixed in EGP on the day the contract is signed',
    'covers': 'everything to the customer\'s door except licensing',
    'before_customs': 'the full down payment and every signed cheque must be with the company',
    'not_available_when': 'the customer is the initiative holder himself',
    'confirmed_on': '2026-09-14',
}


def _deal_for(context, deal_reference: Optional[str] = None):
    """The deal this conversation is about: by reference, else the customer's newest open one."""
    from car_import.models import CarDeal

    qs = CarDeal.all_objects.select_related('partner', 'vehicle', 'import_stage')
    if deal_reference:
        return qs.filter(name__iexact=deal_reference.strip()).first()
    partner = getattr(context, 'partner', None)
    if partner is None:
        return None
    return (qs.filter(partner=partner)
              .exclude(state='cancelled')
              .order_by('-id')
              .first())


def _status_text(deal) -> str:
    """What the customer may be told — never internal notes, never a cost price."""
    stage = deal.import_stage
    lines = [f"العربية: {deal.vehicle}" if deal.vehicle_id else "العربية: لسه مش متحددة"]
    if stage:
        lines.append(f"المرحلة الحالية: {stage.name or stage.name_en}")
    if deal.vessel:
        lines.append(f"الباخرة: {deal.vessel}")
    if deal.bl_number:
        lines.append(f"بوليصة الشحن: {deal.bl_number}")
    if deal.eta:
        lines.append(f"الوصول المتوقع: {deal.eta:%Y-%m-%d}")
    if deal.arrival_port:
        lines.append(f"الميناء: {deal.arrival_port}")
    if deal.tracking_url:
        lines.append(f"لينك التتبع: {deal.tracking_url}")
    payment = dict(deal.PAYMENT_STATE).get(deal.payment_state)
    if payment:
        lines.append(f"حالة الدفع حسب المسجّل عندنا: {payment}")
    return "\n".join(lines)


@tool(
    name="ka_get_deal_status",
    display_name="Car deal status",
    description=(
        "Use this tool to answer any question about where a customer's car is now — "
        "\"وصلت فين\", the stage, the vessel, the bill of lading, the ETA, the port, or the tracking link. "
        "Before calling this tool you MUST be talking to a customer who has a deal; pass deal_reference only "
        "if the customer named a specific reference. Returns the customer-safe stage, the shipping facts and "
        "the payment mark as recorded by the company. Do NOT state any figure this tool did not return, and "
        "do NOT promise a delivery date."
    ),
    category="car_import",
    parameters_schema={
        "type": "object",
        "properties": {
            "deal_reference": {
                "type": "string",
                "description": "The deal reference such as KA-2026-0001. Leave empty to use this customer's open deal.",
            },
        },
        "required": [],
    },
)
def ka_get_deal_status(context, deal_reference: Optional[str] = None) -> Dict[str, Any]:
    """Customer-safe status of one car deal."""
    try:
        deal = _deal_for(context, deal_reference)
        if deal is None:
            return {"success": False, "error": "No open deal for this customer", "error_type": "not_found"}
        return {
            "success": True,
            "data": {
                "deal_reference": deal.name,
                "state": deal.state,
                "stage": (deal.import_stage.name if deal.import_stage_id else None),
                "car": str(deal.vehicle) if deal.vehicle_id else None,
                "vessel": deal.vessel or None,
                "bl_number": deal.bl_number or None,
                "eta": deal.eta.isoformat() if deal.eta else None,
                "port": deal.arrival_port or None,
                "tracking_url": deal.tracking_url or None,
                "payment_state": deal.payment_state,
                "customer_text": _status_text(deal),
            },
        }
    except Exception as e:
        logger.exception("ka_get_deal_status failed")
        return {"success": False, "error": str(e), "error_type": "unknown"}


@tool(
    name="ka_send_deal_status_update",
    display_name="Send the car's status to the customer",
    description=(
        "Use this tool to SEND the customer an update about where their car is. It writes the message itself "
        "and delivers it on the customer's channel. Before calling this tool you MUST have confirmed the "
        "customer is asking about their own car. Returns what was sent. After this tool succeeds, say nothing "
        "else — the customer already received the message. Do NOT use it to send prices, promises or anything "
        "about money."
    ),
    category="car_import",
    side_effect=True,
    parameters_schema={
        "type": "object",
        "properties": {
            "deal_reference": {
                "type": "string",
                "description": "The deal reference such as KA-2026-0001. Leave empty to use this customer's open deal.",
            },
        },
        "required": [],
    },
)
def ka_send_deal_status_update(context, deal_reference: Optional[str] = None) -> Dict[str, Any]:
    """Send the current stage and shipping facts to the customer."""
    try:
        partner = getattr(context, 'partner', None)
        if partner is None:
            return {"success": False, "error": "No customer in context", "error_type": "no_partner"}

        deal = _deal_for(context, deal_reference)
        if deal is None:
            return {"success": False, "error": "No open deal for this customer", "error_type": "not_found"}

        from modules.chat.services.omnichannel_send_service import OmnichannelSendService
        text = _status_text(deal)
        result = OmnichannelSendService().send_and_broadcast(partner, {'text': text}, message_type='text') or {}
        if result.get('success') is False or result.get('status') is False:
            return {"success": False, "error": str(result.get('error') or 'send failed'), "error_type": "send_failed"}
        return {"success": True, "data": {"sent": True, "deal_reference": deal.name, "text": text}}
    except Exception as e:
        logger.exception("ka_send_deal_status_update failed")
        return {"success": False, "error": str(e), "error_type": "unknown"}


@tool(
    name="ka_check_import_eligibility",
    display_name="Check import eligibility",
    description=(
        "Use this tool before quoting anything, to check whether a customer may import the car they want. "
        "Before calling this tool you MUST have: 1) the route (initiative, personal, commercial, first_owner), "
        "2) the car's model year, and where possible the engine size in cc and whether the initiative is Gulf or "
        "European. Returns allowed or blocked, the reason in Arabic, and any warning to pass on. Do NOT offer the "
        "disability route, a Korean car, or anything sourced outside Europe — those are refused or unconfirmed."
    ),
    category="car_import",
    parameters_schema={
        "type": "object",
        "properties": {
            "program": {
                "type": "string",
                "description": "initiative, personal, commercial, first_owner, disability, showroom or shipping_only",
            },
            "initiative_region": {
                "type": "string",
                "description": "gulf or european — only when the route is the initiative",
            },
            "model_year": {"type": "integer", "description": "The car's model year, e.g. 2024"},
            "cc": {"type": "integer", "description": "Exact engine displacement in cc if known, e.g. 1499 or 1999"},
            "mileage_km": {"type": "integer", "description": "Odometer reading in km for a used car"},
            "customer_budget_egp": {"type": "integer", "description": "The customer's budget in EGP if they said one"},
            "customer_is_initiative_holder": {
                "type": "boolean",
                "description": "True when the customer holds the initiative in their own name",
            },
        },
        "required": ["program"],
    },
)
def ka_check_import_eligibility(
    context,
    program: str,
    initiative_region: Optional[str] = None,
    model_year: Optional[int] = None,
    cc: Optional[int] = None,
    mileage_km: Optional[int] = None,
    customer_budget_egp: Optional[int] = None,
    customer_is_initiative_holder: Optional[bool] = None,
) -> Dict[str, Any]:
    """The company's own rules, as confirmed by the owner."""
    try:
        program = (program or '').strip().lower()
        warnings, blocked_reason = [], None

        if program == 'disability':
            blocked_reason = "قانون ذوي الهمم متوقف حالياً، والحكومة بتعدّل فيه."
        elif customer_budget_egp is not None and customer_budget_egp < 2_000_000:
            blocked_reason = ("الميزانية دي أقل من اللي الشركة بتشتغل عليه؛ الأنسب وكيل أو معرض في مصر.")
        elif program == 'initiative':
            if model_year is not None and model_year < 2023:
                blocked_reason = "المبادرة بتسمح بموديل 2023 وأحدث."
            if (initiative_region or '').lower() == 'gulf' and cc and cc > 1600:
                warnings.append("مبادرة خليجي على موتور أكبر من 1600cc: الوديعة بتعدّي 60–70 ألف دولار "
                                "لأن مفيش شهادة يورو وان — الأفضل موديل أقل من 1600cc.")
            if mileage_km and mileage_km > 20000:
                warnings.append("العداد أعلى من 20 ألف كم: مسموح، بس الشركة بتنصح بأقل من كده.")
        elif program in ('personal', 'commercial'):
            if model_year is not None and model_year < 2026:
                blocked_reason = "الاستيراد الشخصي والتجاري لازم عربية زيرو موديل السنة الحالية."
            if program == 'commercial':
                warnings.append("الاستيراد التجاري متاح بموافقة الإدارة لكل حالة — لازم تتحوّل لموظف للموافقة.")

        if program == 'initiative' and customer_is_initiative_holder:
            warnings.append("العميل صاحب المبادرة: التقسيط مش متاح في الحالة دي.")

        allowed = blocked_reason is None
        return {
            "success": True,
            "data": {
                "allowed": allowed,
                "blocked_reason": blocked_reason,
                "warnings": warnings,
                "requires_management_approval": program == 'commercial',
                "documents_required": [
                    "صورة البطاقة وش وضهر", "الباسبور", "الإقامة",
                    "كشف حساب 6 شهور فيه تحويل الوديعة", "إيصالات الوديعة",
                    "الموافقة الاستيرادية", "توكيل المخلص الجمركي",
                ] if program == 'initiative' else ["صورة البطاقة", "الباسبور"],
                "rules_confirmed_on": "2026-09-14",
            },
        }
    except Exception as e:
        logger.exception("ka_check_import_eligibility failed")
        return {"success": False, "error": str(e), "error_type": "unknown"}


@tool(
    name="ka_get_instalment_plan_terms",
    display_name="Instalment terms",
    description=(
        "Use this tool whenever a customer asks about instalments or financing. Returns the company's confirmed "
        "terms in words — the down payment, the number of monthly cheques, the yearly rate, what the plan covers, "
        "and who cannot use it. It deliberately returns NO instalment amount: state the terms, then hand the "
        "customer to a colleague for the exact figure. Do NOT calculate a monthly payment yourself."
    ),
    category="car_import",
    parameters_schema={
        "type": "object",
        "properties": {
            "customer_is_initiative_holder": {
                "type": "boolean",
                "description": "True when the customer holds the initiative in their own name — they cannot use instalments",
            },
            "car_location": {
                "type": "string",
                "description": "import for a car being imported, egypt for a car already in the showroom",
            },
        },
        "required": [],
    },
)
def ka_get_instalment_plan_terms(
    context,
    customer_is_initiative_holder: Optional[bool] = None,
    car_location: Optional[str] = None,
) -> Dict[str, Any]:
    """The confirmed instalment terms — never an amount."""
    try:
        if customer_is_initiative_holder:
            return {
                "success": True,
                "data": {
                    "available": False,
                    "reason_ar": ("لو حضرتك صاحب المبادرة، التقسيط مش متاح — لأن الإفراج الجمركي بيتم باسم "
                                  "حضرتك فمفيش حظر بيع على العربية. ينفع نشوف عربية من المعرض بالتقسيط."),
                    "confirmed_on": INSTALMENTS['confirmed_on'],
                },
            }
        data = dict(INSTALMENTS)
        data['available'] = True
        data['bank_financing'] = (
            "عربيات مصر ممكن كمان تتمول من البنوك — البنك هو اللي بيجهّز الملف وبيكلّم العميل، "
            "والفوايد بتتغير من بنك لبنك."
        ) if (car_location or '').lower() == 'egypt' else None
        data['amount_policy'] = "The exact instalment amount is given by a colleague, never by the assistant."
        return {"success": True, "data": data}
    except Exception as e:
        logger.exception("ka_get_instalment_plan_terms failed")
        return {"success": False, "error": str(e), "error_type": "unknown"}


@tool(
    name="ka_get_fee_and_licensing_costs",
    display_name="Company fees and licensing costs",
    description=(
        "Use this tool whenever a customer asks what the company charges: the service fee, the EUR 1 figure, port "
        "and clearance, powers of attorney, the licensing service fee or protection film. Returns the company's "
        "dated official figures. The licence cost itself is never quoted — the tool returns the referral wording "
        "instead. Do NOT state any fee that this tool did not return."
    ),
    category="car_import",
    parameters_schema={"type": "object", "properties": {}, "required": []},
)
def ka_get_fee_and_licensing_costs(context) -> Dict[str, Any]:
    """The company's confirmed fee list."""
    try:
        return {
            "success": True,
            "data": {
                **FEES,
                "licence_cost": "not quoted — refer the customer to the licensing office",
                "egp_note": "any EGP figure is indicative at today's rate and carries a 1.5–2% conversion commission",
            },
        }
    except Exception as e:
        logger.exception("ka_get_fee_and_licensing_costs failed")
        return {"success": False, "error": str(e), "error_type": "unknown"}


@tool(
    name="ka_escalate_conversation_to_staff",
    display_name="Hand the customer to a colleague",
    description=(
        "Use this tool the moment a conversation touches money, a discount, a refund or cancellation, the exact "
        "instalment amount, a complaint about the car's condition, anything legal or about the contract, or any "
        "request you are not certain about. It hands the conversation to a human, sends the customer a short "
        "holding message and notifies the team. Before calling it you MUST have a one-line reason. After it "
        "succeeds, say nothing else. Never send an account number or confirm that a transfer arrived — use this "
        "tool instead."
    ),
    category="car_import",
    side_effect=True,
    parameters_schema={
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "One line, in Arabic, on what the customer asked for and why a human is needed",
            },
            "topic": {
                "type": "string",
                "description": "money, discount, refund, cancellation, instalment_amount, complaint, legal or other",
            },
        },
        "required": ["reason"],
    },
)
def ka_escalate_conversation_to_staff(context, reason: str, topic: Optional[str] = None) -> Dict[str, Any]:
    """Switch the conversation to a human and tell the customer someone is coming."""
    try:
        partner = getattr(context, 'partner', None)
        conversation = getattr(context, 'conversation', None)
        if partner is None:
            return {"success": False, "error": "No customer in context", "error_type": "no_partner"}

        if conversation is not None:
            conversation.handled_by_ai = False
            conversation.save(update_fields=['handled_by_ai'])

        holding = "تمام يا فندم 🙏 هحوّل حضرتك لزميلي وهو هيرد على حضرتك حالاً."
        from modules.chat.services.omnichannel_send_service import OmnichannelSendService
        OmnichannelSendService().send_and_broadcast(partner, {'text': holding}, message_type='text')

        logger.info("car_import: escalated conversation for partner %s (%s): %s", partner.pk, topic, reason)
        return {
            "success": True,
            "data": {
                "escalated": True,
                "handled_by_ai": False,
                "topic": topic or 'other',
                "reason": reason,
                "holding_message_sent": True,
                "note": "A human must switch the AI back on when the case is resolved.",
            },
        }
    except Exception as e:
        logger.exception("ka_escalate_conversation_to_staff failed")
        return {"success": False, "error": str(e), "error_type": "unknown"}
