# -*- coding: utf-8 -*-
"""The offer, as something you can actually send.

The client's spreadsheet already had the right shape for this — a title, the
customer's name, a short stack of lines, the deposit, and five notes — so this
follows sheet2 of `New Quotation.xlsx` rather than inventing a house style. The
notes are theirs, word for word, with the two corrections the owner gave in the
message that came with the workbook: the port fee is not "about 50,000 EGP" for
every port, and there is a charge for collecting the car from the showroom.

Two renderers, one source of truth:

* ``as_text`` — for WhatsApp, where a customer actually reads it. Plain text,
  no markdown: the channels render asterisks literally and a quote covered in
  stars looks like spam;
* ``as_html`` — for printing and for the PDF a customer wants to show a bank.

Neither renderer computes anything. Both read the lines the quote froze when it
was calculated, which is the point: the document a customer holds and the row
the company can audit are the same numbers, not two renderings of a formula
that has since moved on.
"""
from django.utils.translation import gettext as _

#: Egyptian pounds and euros are never mixed into one total, so the document
#: has two blocks and says plainly what each one is for.
EUR = 'EUR'
EGP = 'EGP'

SYMBOLS = {EUR: '€', EGP: 'ج.م'}


def _amount(value, currency):
    return f"{value:,.2f} {SYMBOLS.get(currency, currency)}"


def _pct(value):
    """15, not 15.00. A Decimal column keeps its trailing zeros; an offer
    should not."""
    return f'{float(value):g}'


def _visible_lines(quote, currency):
    """The rows worth showing a customer.

    Zero rows are dropped: an offer that lists "EUR 1 certificate — 0.00 €" is
    an offer that invites a question about a service nobody bought.
    """
    return [line for line in quote.lines.all()
            if getattr(line.currency, 'code', None) == currency
            and (line.amount or line.code in ('gross', 'net'))]


def _options(quote):
    """The candidate cars, when the offer compares more than one."""
    if not quote.pk:
        return []
    rows = list(quote.options.select_related('vehicle').order_by('sequence', 'id'))
    return rows if len(rows) > 1 else []


def _option_label(option, index):
    car = option.label or (str(option.vehicle) if option.vehicle_id else '')
    return car or f'عربية {index}'


def _options_text(quote):
    rows = _options(quote)
    if not rows:
        return []
    out = ['العربيات المرشحة (كل واحدة بسعرها الكامل):']
    for index, option in enumerate(rows, 1):
        mark = ' ✅' if option.is_accepted else ''
        if option.pricing_error or not option.total_eur:
            out.append(f'{index}- {_option_label(option, index)}: {option.pricing_error or "مفيش سعر"}')
            continue
        out.append(
            f'{index}- {_option_label(option, index)}{mark}: الإجمالي {_amount(option.total_eur, EUR)} — '
            f'الوديعة {_pct(option.deposit_pct)}% ({_amount(option.deposit_eur, EUR)})')
        if option.listing_url:
            out.append(f'   {option.listing_url}')
    if any(o.is_accepted for o in rows):
        out.append('التفاصيل تحت للعربية المختارة ✅.')
    out.append('')
    return out


def _options_html(quote):
    rows = _options(quote)
    if not rows:
        return ''
    body = ''
    for index, option in enumerate(rows, 1):
        mark = ' ✅' if option.is_accepted else ''
        link = (f'<br><a href="{_escape(option.listing_url)}">{_escape(option.listing_url)}</a>'
                if option.listing_url else '')
        cls = ' class="chosen"' if option.is_accepted else ''
        if option.pricing_error or not option.total_eur:
            body += (f'<tr><td>{index}</td><td>{_escape(_option_label(option, index))}{mark}{link}</td>'
                     f'<td class="n" colspan="3">{_escape(option.pricing_error or "مفيش سعر")}</td></tr>')
            continue
        body += (f'<tr{cls}><td>{index}</td>'
                 f'<td>{_escape(_option_label(option, index))}{mark}{link}</td>'
                 f'<td class="n">{_amount(option.gross_price_eur or 0, EUR)}</td>'
                 f'<td class="n">{_amount(option.total_eur, EUR)}</td>'
                 f'<td class="n">{_pct(option.deposit_pct)}% — {_amount(option.deposit_eur, EUR)}</td></tr>')
    chosen_note = ('<p class="meta">التفاصيل تحت للعربية المختارة ✅.</p>'
                   if any(o.is_accepted for o in rows) else '')
    return ('<h2>العربيات المرشحة</h2>'
            '<table class="options"><tr class="head"><td>#</td><td>العربية</td>'
            '<td class="n">سعر الإعلان</td><td class="n">الإجمالي</td><td class="n">الوديعة</td></tr>'
            f'{body}</table>{chosen_note}')


def as_text(quote):
    """The offer as a WhatsApp message, in Arabic."""
    customer = getattr(quote.partner, 'name', '') or ''
    car = str(quote.vehicle) if quote.vehicle_id else ''

    out = ['عرض سعر سيارة']
    if customer:
        out.append(f'الاسم: {customer}')
    if car:
        out.append(f'العربية: {car}')
    out.append(f'التاريخ: {quote.quote_date:%Y-%m-%d}')
    if quote.name:
        out.append(f'رقم العرض: {quote.name}')
    out.append('')
    out.extend(_options_text(quote))

    for line in _visible_lines(quote, EUR):
        out.append(f'{line.label}: {_amount(line.amount, EUR)}')

    out.append('')
    out.append(f'إجمالي سعر البيع: {_amount(quote.total_eur, EUR)}')
    out.append(f'مقدم جدية الحجز ({_pct(quote.deposit_pct)}%): {_amount(quote.deposit_eur, EUR)}')
    out.append(f'الباقي: {_amount(quote.balance_eur, EUR)}')

    egp_lines = _visible_lines(quote, EGP)
    if egp_lines:
        out.append('')
        out.append('مصاريف بتتحصّل في مصر عند الوصول:')
        for line in egp_lines:
            out.append(f'{line.label}: {_amount(line.amount, EGP)}')

    out.append('')
    out.append('ملاحظات:')
    for index, note in enumerate(_notes(quote), 1):
        out.append(f'{index}- {note}')

    if quote.valid_until:
        out.append('')
        out.append(f'العرض ساري لغاية {quote.valid_until:%Y-%m-%d}.')

    return '\n'.join(out)


def _notes(quote):
    """The client's own five notes, corrected where the owner corrected them."""
    notes = [
        'السيارة فابريكة من الداخل والخارج.',
        'التحويل لحساب الشركة من الخارج.',
        'طرق الدفع: نقداً أو تحويل بنكي.',
    ]
    # The sheet says "about 50,000 EGP" for every port. The owner's message of
    # 2026-09-16 gives two different figures, and the difference between them
    # is 50,000 EGP — too much to leave inside the word "about".
    if quote.port_fee_egp:
        port = 'ميناء الإسكندرية' if quote.port == 'alexandria' else 'ميناء بورسعيد'
        notes.append(
            f'الأسعار باليورو مش شاملة مصاريف {port}، وهي '
            f'{quote.port_fee_egp:,.0f} جنيه بتتدفع عند الوصول.')
    else:
        notes.append('الأسعار باليورو مش شاملة مصاريف الميناء في مصر.')
    if quote.showroom_fee_egp:
        notes.append(
            f'الاستلام من المعرض عليه {quote.showroom_fee_egp:,.0f} جنيه إضافية.')
    notes.append(f'نسبة مقدم جدية الحجز من إجمالي سعر البيع: {_pct(quote.deposit_pct)}%.')
    if quote.total_egp_indicative:
        notes.append(
            f'أي رقم بالجنيه تقريبي بسعر اليوم ({quote.fx_rate_egp:,.2f}) وعليه عمولة تحويل '
            f'من 1.5% لـ 2%، والشركة مش بتضمن سعر صرف.')
    if quote.notes:
        notes.append(quote.notes.strip())
    return notes


def as_html(quote):
    """The same offer, for printing."""
    rows_eur = ''.join(
        f'<tr><td>{_escape(line.label)}</td>'
        f'<td class="n">{_amount(line.amount, EUR)}</td></tr>'
        for line in _visible_lines(quote, EUR))

    egp_lines = _visible_lines(quote, EGP)
    block_egp = ''
    if egp_lines:
        rows_egp = ''.join(
            f'<tr><td>{_escape(line.label)}</td>'
            f'<td class="n">{_amount(line.amount, EGP)}</td></tr>'
            for line in egp_lines)
        block_egp = (
            '<h2>مصاريف بتتحصّل في مصر عند الوصول</h2>'
            f'<table>{rows_egp}'
            f'<tr class="total"><td>الإجمالي</td>'
            f'<td class="n">{_amount(quote.egp_due_on_arrival, EGP)}</td></tr></table>')

    notes = ''.join(f'<li>{_escape(note)}</li>' for note in _notes(quote))
    customer = _escape(getattr(quote.partner, 'name', '') or '—')
    car = _escape(str(quote.vehicle) if quote.vehicle_id else '—')

    return f"""<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<title>{_escape(quote.name or 'عرض سعر')}</title>
<style>
 body {{ font-family: 'Cairo', 'Segoe UI', sans-serif; margin: 2.5rem; color: #16324f; }}
 h1 {{ font-size: 1.5rem; margin-bottom: .25rem; }}
 h2 {{ font-size: 1.05rem; margin-top: 2rem; }}
 .meta {{ color: #55708c; font-size: .9rem; margin-bottom: 1.5rem; }}
 table {{ width: 100%; border-collapse: collapse; }}
 td {{ padding: .5rem .25rem; border-bottom: 1px solid #e3eaf2; }}
 td.n {{ text-align: left; direction: ltr; white-space: nowrap; }}
 /* A date or a reference is a left-to-right run inside Arabic text. Without
    an isolate the browser reorders "2026-09-16" into "16-09-2026" on the page
    — the right characters in the wrong order, which is worse than either. */
 bdi {{ unicode-bidi: isolate; }}
 tr.total td {{ font-weight: 700; border-top: 2px solid #16324f; border-bottom: none; }}
 table.options tr.head td {{ font-weight: 700; color: #55708c; font-size: .85rem; }}
 table.options tr.chosen td {{ background: #eef6f1; font-weight: 600; }}
 table.options a {{ color: #55708c; font-size: .8rem; text-decoration: none; }}
 ol {{ color: #55708c; font-size: .9rem; line-height: 1.8; }}
 /* Printed on A4 by a salesman with a customer waiting. One page, no chrome. */
 @media print {{ body {{ margin: 1.2cm; }} }}
</style></head><body>
<h1>عرض سعر سيارة</h1>
<div class="meta">
  الاسم: <bdi>{customer}</bdi> &nbsp;·&nbsp; العربية: <bdi>{car}</bdi> &nbsp;·&nbsp;
  التاريخ: <bdi>{quote.quote_date:%Y-%m-%d}</bdi> &nbsp;·&nbsp;
  رقم العرض: <bdi>{_escape(quote.name or '—')}</bdi>
</div>
{_options_html(quote)}
<table>{rows_eur}
<tr class="total"><td>إجمالي سعر البيع</td><td class="n">{_amount(quote.total_eur, EUR)}</td></tr>
<tr><td>مقدم جدية الحجز <bdi>({_pct(quote.deposit_pct)}%)</bdi></td>
    <td class="n">{_amount(quote.deposit_eur, EUR)}</td></tr>
<tr><td>الباقي</td><td class="n">{_amount(quote.balance_eur, EUR)}</td></tr>
</table>
{block_egp}
<h2>ملاحظات</h2>
<ol>{notes}</ol>
</body></html>"""


def _escape(value):
    from django.utils.html import escape
    return escape(value)
