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

#: The last-resort copy of what the client confirmed on 2026-09-14/15.
#:
#: These used to BE the source. They are now only what answers when the
#: reference tables are empty — on a fresh install before
#: `seed_reference_data` has run. Management edits the tables; nobody
#: should have to edit Python to change a price.
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



# ───────────────────────────────────────────────────────────────────────────
# the figures, from the tables when they exist
# ───────────────────────────────────────────────────────────────────────────
def _fees_from_tables():
    """The fee schedule in force today, or None when the table is empty."""
    try:
        from car_import.models import FeeSchedule
    except Exception:
        return None
    rows = list(FeeSchedule.in_force())
    if not rows:
        return None
    by_code = {row.code: row for row in rows}

    # code in the table -> key in what the agent receives. One map, used both
    # to build the payload AND to honour "never quote", because the two used to
    # disagree: the drop looped over table codes ('licence_cost') while the
    # payload was keyed by payload names ('licensing_service_egp'), so marking a
    # fee non-quotable silently did nothing while the comment claimed it did.
    PAYLOAD_KEY = {
        'company_fee': 'company_fee_eur',
        'company_fee_eur1': 'company_fee_with_eur1_eur',
        'port_and_clearance': 'port_and_clearance_egp',
        'powers_of_attorney': 'powers_of_attorney_usd',
        'licensing_service': 'licensing_service_egp',
        'protection_film': 'protection_film_egp',
    }

    def amount(row):
        if row is None or row.amount is None:
            return None
        value = float(row.amount)
        return int(value) if value == int(value) else value

    data = {
        'confirmed_on': str(min((r.effective_from for r in rows if r.effective_from),
                                default='') or ''),
        'source': 'fee schedule table',
    }
    for code, key in PAYLOAD_KEY.items():
        row = by_code.get(code)
        if row is None or not row.quotable_to_customer:
            continue          # absent from the payload; it cannot be read out
        if code == 'protection_film' and row.amount is not None:
            data[key] = (f"{int(row.amount):,}–{int(row.amount_to):,}" if row.amount_to
                         else f"{int(row.amount):,}")
        else:
            data[key] = amount(row)
    return {k: v for k, v in data.items() if v is not None}


def _instalments_from_tables():
    """The direct-instalment plan in force today, or None."""
    try:
        from car_import.models import FinancingPlan
    except Exception:
        return None
    plan = FinancingPlan.in_force(code='direct_instalments').first()
    if plan is None:
        return None
    return {
        'down_payment_pct': float(plan.down_payment_pct) if plan.down_payment_pct else None,
        'terms_months': plan.term_months or [],
        'rate_pct_per_year_flat': float(plan.rate_pct_flat) if plan.rate_pct_flat else None,
        'first_instalment': plan.first_instalment_note,
        'cheques': ("monthly cheques in EGP from an Egyptian bank account in the customer's own name"
                    if plan.cheques_required else ''),
        'covers': plan.covers,
        'not_available_when': plan.not_available_when,
        'available': plan.available,
        'amount_policy': plan.amount_policy,
        'confirmed_on': str(plan.effective_from or ''),
        'source': 'financing plan table',
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


#: Whether the assistant may state the company's published money figures at all.
#: The owner had not decided as of 2026-09-15, so the default is NO.
#:
#: Enforced HERE, in the tool, not in the prompt. A prompt rule lost this
#: argument twice on the tenant: told "escalate without a number" in the
#: per-turn warning and "use these tools" in the lane rules, the model used
#: the tools and read the price list out. A tool that returns no numbers
#: cannot be talked into it.
FEE_DISCLOSURE_KEY = 'car_import.ai_may_quote_published_fees'


def _may_quote_published_fees() -> bool:
    from car_import.services import policy
    if policy.ai_first():
        return True          # the assistant sells; published fees are the least of it
    try:
        from modules.base.models import ConfigParameter
        row = ConfigParameter.objects.filter(key=FEE_DISCLOSURE_KEY).values('value').first()
    except Exception:
        return False
    return bool(row) and str(row['value']).strip().lower() in ('1', 'true', 'yes', 'on')


def _quoting_refused() -> Dict[str, Any]:
    """What a money tool returns while disclosure is switched off."""
    return {
        "success": False,
        "error": "Fee disclosure is switched off for this tenant",
        "error_type": "disclosure_off",
        "data": {
            "must_escalate": True,
            "say_to_customer_ar": "الأرقام دي زميلي هو اللي يقولها لحضرتك — ثانية واحدة وهوصّلك بيه.",
            "note": "Do NOT state any figure. Call ka_escalate_conversation_to_staff.",
        },
    }


#: What the CUSTOMER is told, in Egyptian Arabic, independent of the active
#: language. Never build customer text out of a model's choice labels: those
#: are gettext strings resolved against the active language, and a tool runs in
#: Celery with no request — so the customer read "Not paid" in the middle of an
#: Arabic sentence.
PAYMENT_STATE_AR = {
    'not_paid': 'لسه مش مدفوعة',
    'deposit_paid': 'مقدم التعاقد اتدفع',
    'partially_paid': 'مدفوعة جزئياً',
    'fully_paid': 'مدفوعة بالكامل',
}


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
    payment = PAYMENT_STATE_AR.get(deal.payment_state)
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
        if not _may_quote_published_fees():
            return _quoting_refused()
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
        data = _instalments_from_tables() or dict(INSTALMENTS)
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
        if not _may_quote_published_fees():
            return _quoting_refused()
        return {
            "success": True,
            "data": {
                **(_fees_from_tables() or FEES),
                "licence_cost": "not quoted — refer the customer to the licensing office",
                "egp_note": "any EGP figure is indicative at today's rate and carries a 1.5–2% conversion commission",
            },
        }
    except Exception as e:
        logger.exception("ka_get_fee_and_licensing_costs failed")
        return {"success": False, "error": str(e), "error_type": "unknown"}


def _file_discount_request(partner, context, reason):
    """One pending fee-discount request per customer; the amount is management's
    to fill in when they decide. Returns the request id, or None."""
    try:
        from car_import.models.approval import ApprovalPolicy, ApprovalRequest
        pending = (ApprovalRequest.objects
                   .filter(subject='fee_discount', partner=partner, state='pending')
                   .order_by('-id').first())
        if pending is not None:
            return pending.pk
        deal = _deal_for(context)
        deal = deal if getattr(deal, 'pk', None) else None
        policy = ApprovalPolicy.for_subject('fee_discount')
        request = ApprovalRequest.objects.create(
            subject='fee_discount', policy=policy, deal=deal, partner=partner,
            currency=getattr(policy, 'currency', None),
            reason=f'طلب خصم جاي من الشات (المساعد): {reason}')
        return request.pk
    except Exception:
        logger.exception("car_import: could not file the discount approval request")
        return None


@tool(
    name="ka_escalate_conversation_to_staff",
    display_name="Hand the customer to a colleague",
    description=(
        "Use this tool the moment a conversation touches money, a discount, a refund or cancellation, the exact "
        "instalment amount, a complaint about the car's condition, anything legal or about the contract, or any "
        "request you are not certain about. It hands the conversation to a human, sends the customer a short "
        "holding message and notifies the team. Before calling it you MUST have a one-line reason. After it "
        "succeeds, reply with an EMPTY message: the platform sends the customer the holding line itself, and "
        "anything you write would reach them as a second message. Never send an account number or confirm "
        "that a transfer arrived — use this tool instead."
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
            # Stamp WHEN we handed over. `handled_by_ai=False` alone cannot be
            # the signal: it is also the resting state of every conversation
            # that never had an assistant, which is most of an imported
            # history. The chaser uses this to tell the two apart.
            from django.utils import timezone as _tz
            data = conversation.social_platform_data
            if not isinstance(data, dict):
                data = {}
            data['car_import_escalated_at'] = _tz.now().isoformat()
            data['car_import_escalation_topic'] = topic or 'other'
            conversation.social_platform_data = data
            conversation.save(update_fields=['handled_by_ai', 'social_platform_data'])

        # The holding line is NOT sent from here. It is the turn's reply, and
        # the outbound gate (`patches._gate`) emits it exactly once when it
        # sees this run handed over. Sending it here as well made the bridge
        # see an empty reply, re-run the turn, escalate again and send the
        # sentence twice — live on 2026-09-17, two notes and two messages.
        from car_import.services.supervisor import HOLDING_TEXT
        holding = HOLDING_TEXT

        # The client's decision of 2026-09-16: the assistant stays closed AND
        # the colleague picking this up is shown the approved figures to check
        # — "مع اضهار اقتراح لمطابقة الارقام هل هي صحيحة ام لا". It lands as an
        # INTERNAL NOTE in the thread, so the reason and the numbers sit next to
        # the customer's own question rather than in a bell somebody clears.
        # Every escalation leaves one; only the money ones carry figures.
        from car_import.services import money_briefing
        briefed = money_briefing.notify(partner, conversation=conversation,
                                        topic=topic, reason=reason)

        # A discount is management's decision, and the customer just asked for
        # one. File the request now, in the queue management already watches,
        # so the agent does not have to ask in chat and then again in a form.
        approval_id = None
        if (topic or '').strip().lower() == 'discount':
            approval_id = _file_discount_request(partner, context, reason)

        logger.info("car_import: escalated conversation for partner %s (%s): %s", partner.pk, topic, reason)
        return {
            "success": True,
            "data": {
                "escalated": True,
                "handled_by_ai": False,
                "topic": topic or 'other',
                "reason": reason,
                "approval_request_id": approval_id,
                "customer_will_receive": holding,
                "next_step": "Reply with an empty message. The platform sends the holding line; do not write it yourself.",
                "team_briefed_with_figures": briefed,
                "note": "A human must switch the AI back on when the case is resolved.",
            },
        }
    except Exception as e:
        logger.exception("ka_escalate_conversation_to_staff failed")
        return {"success": False, "error": str(e), "error_type": "unknown"}


@tool(
    name="ka_get_document_checklist",
    display_name="Document checklist",
    description=(
        "Use this tool when the customer asks what papers they need, or when you need to chase "
        "missing documents. Before calling it you MUST be talking to a customer who has a deal. "
        "Returns which documents are still missing, which were rejected and why, and which have "
        "expired. Do NOT ask for a document this tool did not list, and do NOT ask the customer "
        "to send a national ID or passport into the chat — say a colleague will arrange it."
    ),
    category="car_import",
    parameters_schema={"type": "object", "properties": {}, "required": []},
)
def ka_get_document_checklist(context) -> Dict[str, Any]:
    """What paperwork is still outstanding on this customer's deal."""
    try:
        deal = _deal_for(context)
        if deal is None:
            return {"success": False, "error": "No open deal for this customer",
                    "error_type": "not_found"}
        from car_import.services.documents import checklist_status
        status = checklist_status(deal)
        # A confidential document is named but flagged: the assistant may say
        # "we need your ID" and must not invite it into a WhatsApp thread.
        return {"success": True, "data": dict(status, deal_reference=deal.name)}
    except Exception as e:
        logger.exception("ka_get_document_checklist failed")
        return {"success": False, "error": str(e), "error_type": "unknown"}
