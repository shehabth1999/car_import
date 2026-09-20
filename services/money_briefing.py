# -*- coding: utf-8 -*-
"""What a colleague sees the moment the assistant hands over a money question.

The client's decision of 2026-09-16, in their own words:

    "بفضل يبقى مقفول في الاول مع اضهار اقتراح لمطابقة الارقام هل هي صحيحة ام لا"

Two halves, and only the first was built. The assistant stays closed — it says
no number to a customer and hands over, which is what it already did. The
second half is this file: when it hands over, the colleague who picks the
conversation up is shown the approved figures **as a proposal to check**, not
as an answer to forward.

The distinction matters. An agent who has to go and look the numbers up either
does not, or finds a different copy of them. An agent shown the numbers with
"are these still right?" next to them either confirms in a second or catches a
stale figure before it reaches a customer — which is the whole reason the
switch is closed in the first place.

Nothing here is sent to a customer. It is an internal notification and it says
so at the top, because a figure that could be pasted straight through is a
figure that eventually will be.
"""
import logging

logger = logging.getLogger(__name__)

#: Topics where the numbers are worth putting in front of a person. A complaint
#: about a scratched bumper does not need the fee schedule attached to it.
MONEY_TOPICS = {'money', 'discount', 'refund', 'instalment_amount', 'price', 'fees'}

#: What to call each topic in the note. The colleague opening the thread should
#: know why it was handed over before they read a word of the customer's.
TOPIC_LABELS = {
    'money': 'سؤال فلوس',
    'price': 'سؤال عن السعر',
    'fees': 'سؤال عن المصاريف',
    'discount': 'طلب خصم',
    'refund': 'طلب استرداد',
    'instalment_amount': 'سؤال عن قيمة القسط',
    'cancellation': 'طلب إلغاء',
    'complaint': 'شكوى',
    'legal': 'موضوع قانوني',
    'other': 'محتاج زميل',
}


def is_money_topic(topic):
    return (topic or 'other').strip().lower() in MONEY_TOPICS


def build(partner, topic=None, reason=''):
    """The Arabic briefing text, or '' when there is nothing worth showing."""
    lines = []
    fees = _fees()
    instalments = _instalments()
    quote = _latest_quote(partner)

    if not (fees or instalments or quote):
        return ''

    # No markdown. The chat renders the text as it is stored, so `**bold**`
    # arrives at the agent as literal asterisks — emphasis has to be words and
    # placement, not syntax.
    lines.append('⚠️ ملاحظة داخلية — العميل مش شايفها.')
    lines.append('سأل سؤال فلوس، والمساعد حوّل من غير ما يقول أي رقم.')
    lines.append('دي الأرقام المعتمدة في النظام دلوقتي.')
    lines.append('❗ تأكد إنها لسه صح قبل ما تقولها للعميل.')
    lines.append('')

    if quote:
        lines.append(f'— آخر عرض سعر للعميل ده ({quote["name"]}, {quote["date"]}):')
        lines.append(f'   الإجمالي {quote["total"]} € · مقدم التعاقد {quote["deposit"]} € '
                     f'({quote["deposit_pct"]}%) · الباقي {quote["balance"]} €')
        if quote['paid']:
            lines.append(f'   المدفوع {quote["paid"]} €'
                         + (f' · ❗ دفع زيادة {quote["overpaid"]} €' if quote['overpaid'] else ''))
        lines.append('')

    if fees:
        lines.append('— المصاريف المعتمدة:')
        lines.extend(f'   {label}: {value}' for label, value in fees)
        lines.append('')

    for collision in _collisions(fees):
        # This IS the "اقتراح لمطابقة الارقام" the client asked for. Two rows
        # carrying the same money under different names is not a display bug to
        # hide — it is the question somebody has to answer, and the agent about
        # to quote one of them is the right person to be asked.
        lines.append(f'❗ نفس الرقم ({collision["value"]}) مكتوب تحت اسمين: '
                     + ' / '.join(collision['labels']))
        lines.append('   أنهي واحد الصح؟ لو الاتنين نفس الحاجة، لازم واحد يتقفل.')
        lines.append('')

    if instalments:
        lines.append('— شروط التقسيط المعتمدة:')
        lines.extend(f'   {label}: {value}' for label, value in instalments)
        lines.append('')

    lines.append('لو أي رقم فيهم بقى قديم: الإعدادات ← جدول المصاريف / فئات التسعير.')
    return '\n'.join(lines).strip()


def notify(partner, conversation=None, topic=None, reason=''):
    """Leave a note in the conversation saying why it was handed over.

    Every escalation gets one, not only the money ones — the colleague opening
    the thread should know why it arrived before they read a word of the
    customer's. A money topic gets the approved figures attached; a complaint
    about a scratched bumper does not need the fee schedule stapled to it.

    The note goes IN the thread, not only in a notification bell. A bell says
    "someone needs you" and sends you somewhere to work out why; a note sits
    next to the customer's own question with the answer already in it, and it
    is still there tomorrow for whoever picks the conversation up next.

    Never raises: a note that fails must not take the escalation with it.
    """
    try:
        body = _note_body(partner, topic, reason)
        if not body:
            return False

        from car_import.services import internal_note
        from car_import.tasks import _owner_users_for_partner

        owners = _owner_users_for_partner(partner)
        subject = _subject(topic)
        if conversation is not None:
            return internal_note.post(conversation, body, recipients=owners,
                                      subject=subject)

        # No conversation to write into — a record trigger, a test, a tool
        # called directly. Fall back to the notification alone rather than
        # dropping the figures on the floor.
        partner_ids = [u.partner_id for u in owners if getattr(u, 'partner_id', None)]
        if not partner_ids:
            return False
        from modules.notifications.services.post_notification import post_notification
        post_notification(partner_ids=partner_ids, subject=subject, body=body,
                          url='/chat/', category='car_import')
        return True
    except Exception:
        logger.exception('car_import: could not brief the team on an escalation')
        return False


def _subject(topic):
    label = TOPIC_LABELS.get((topic or 'other').strip().lower(), TOPIC_LABELS['other'])
    return (f'{label} محوّل — راجع الأرقام' if is_money_topic(topic)
            else f'{label} — محادثة محوّلة')


def _note_body(partner, topic, reason):
    """The header every escalation gets, plus the figures when money is in it."""
    label = TOPIC_LABELS.get((topic or 'other').strip().lower(), TOPIC_LABELS['other'])
    lines = [f'🔁 المساعد حوّل المحادثة — {label}.']
    if (reason or '').strip():
        lines.append(f'السبب: {reason.strip()}')

    if is_money_topic(topic):
        figures = build(partner, topic=topic, reason=reason)
        if figures:
            lines.append('')
            lines.append(figures)
            return '\n'.join(lines)

    lines.append('محتاج حد يكمّل مع العميل من هنا. المساعد وقف ومش هيرد تاني.')
    return '\n'.join(lines)


# ── the pieces ─────────────────────────────────────────────────────────────
def _fees():
    """The fee schedule in force today, as (label, value) pairs."""
    try:
        from car_import.models import FeeSchedule
        rows = list(FeeSchedule.in_force().order_by('code'))
    except Exception:
        return []
    out = []
    for row in rows:
        if row.amount is None:
            continue
        out.append((row.name or row.code, f'{row.amount:,.0f} {getattr(row.currency, "code", "") or ""}'.strip()))
    return out


def _collisions(fees):
    """Fees that carry the same amount under different names.

    The old fee schedule and the calculator's own fees now live in one table,
    and two of them collide: 4,750 € is both "the company fee" and "shipping",
    55,000 EGP is both "port and clearance" and "Alexandria port". Until the
    client says which name is right, the honest thing is to put the collision
    in front of the person about to quote one of them.
    """
    by_value = {}
    for label, value in fees:
        by_value.setdefault(value, []).append(label)
    return [{'value': value, 'labels': labels}
            for value, labels in by_value.items() if len(labels) > 1]


def _instalments():
    try:
        from car_import.models import FinancingPlan
        plan = FinancingPlan.in_force(code='direct_instalments').first()
    except Exception:
        return []
    if plan is None or not plan.available:
        return []
    out = []
    if plan.down_payment_pct:
        out.append(('المقدم', f'{float(plan.down_payment_pct):g}%'))
    if plan.term_months:
        out.append(('المدة', ' / '.join(f'{m} شهر' for m in plan.term_months)))
    if plan.rate_pct_flat:
        out.append(('الفايدة', f'{float(plan.rate_pct_flat):g}% سنوياً ثابتة'))
    if plan.not_available_when:
        out.append(('مش متاح لما', plan.not_available_when))
    return out


def _latest_quote(partner):
    """The newest quotation for this customer, if there is one.

    Included because the commonest money question is about a price this
    company already gave, and an agent answering from the fee schedule when a
    quote exists will contradict a document the customer is holding.
    """
    if partner is None:
        return None
    try:
        from car_import.models import Quote
        quote = (Quote.all_objects.filter(partner=partner)
                 .exclude(state='declined').order_by('-id').first())
    except Exception:
        return None
    if quote is None or not quote.total_eur:
        return None
    return {
        'name': quote.name or f'#{quote.pk}',
        'date': f'{quote.quote_date:%Y-%m-%d}',
        'total': f'{quote.total_eur:,.2f}',
        'deposit': f'{quote.deposit_eur:,.2f}',
        'deposit_pct': f'{float(quote.deposit_pct):g}',
        'balance': f'{quote.balance_eur:,.2f}',
        'paid': f'{quote.paid_eur:,.2f}' if quote.paid_eur else '',
        'overpaid': f'{quote.overpaid_eur:,.2f}' if quote.overpaid_eur else '',
    }
