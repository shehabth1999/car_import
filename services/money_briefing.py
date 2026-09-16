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

    lines.append('⚠️ للمراجعة الداخلية — متتبعتش للعميل زي ما هي.')
    lines.append('العميل سأل سؤال فلوس والمساعد حوّل من غير ما يقول أي رقم.')
    lines.append('دي الأرقام المعتمدة في النظام دلوقتي. **تأكد إنها لسه صح قبل ما تقولها.**')
    lines.append('')

    if quote:
        lines.append(f'— آخر عرض سعر للعميل ده ({quote["name"]}, {quote["date"]}):')
        lines.append(f'   الإجمالي {quote["total"]} € · المقدم {quote["deposit"]} € '
                     f'({quote["deposit_pct"]}%) · الباقي {quote["balance"]} €')
        if quote['paid']:
            lines.append(f'   المدفوع {quote["paid"]} €'
                         + (f' · **دفع زيادة {quote["overpaid"]} €**' if quote['overpaid'] else ''))
        lines.append('')

    if fees:
        lines.append('— المصاريف المعتمدة:')
        lines.extend(f'   {label}: {value}' for label, value in fees)
        lines.append('')

    if instalments:
        lines.append('— شروط التقسيط المعتمدة:')
        lines.extend(f'   {label}: {value}' for label, value in instalments)
        lines.append('')

    lines.append('لو أي رقم فيهم بقى قديم: الإعدادات ← جدول المصاريف / فئات التسعير.')
    return '\n'.join(lines).strip()


def notify(partner, conversation=None, topic=None, reason=''):
    """Send the briefing to whoever owns this customer. Never raises."""
    if not is_money_topic(topic):
        return False
    try:
        body = build(partner, topic=topic, reason=reason)
        if not body:
            return False

        from car_import.tasks import _recipients_for_partner
        recipients = _recipients_for_partner(partner)
        if not recipients:
            return False

        from modules.notifications.services.post_notification import post_notification
        # `subject`, not `title`. The wrong keyword here raised on every call
        # once before, and the except swallowed it while the caller reported
        # success — a notification that reaches nobody and says so to no one.
        post_notification(
            partner_ids=recipients,
            subject='سؤال فلوس محوّل — راجع الأرقام',
            body=body,
            url=('/chat/?chat=%s' % conversation.pk) if conversation is not None else '/chat/',
            category='car_import',
        )
        return True
    except Exception:
        logger.exception('car_import: could not brief the team on a money escalation')
        return False


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
        out.append((row.name or row.code, f'{row.amount:,.0f} {row.currency or ""}'.strip()))
    return out


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
