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

**What the customer sees is not the whole calculation** (owner, 2026-09-29,
three times in one chat): the advert's gross price and the German VAT taken
off it are the company's arithmetic. A line reading "VAT 19% (refunded after
export)" makes the customer think the refund is his — on a tax he never paid.
The customer sees the car's price (the net), the company's lines and the
total. `customer_lines` is the one place that decides it, for the quote, the
proforma and the figures the assistant is given to say.

The offer goes out as a PDF (`attach`), with the name, number and address of
the customer's national ID when the assistant has read the card
(`services/identity.py`), the deposit to transfer and the bank details — the
document the owner asked for, one file the customer can act on.
"""
import logging

from django.core.files.base import ContentFile
from django.utils import timezone

logger = logging.getLogger(__name__)

#: Egyptian pounds and euros are never mixed into one total, so the document
#: has two blocks and says plainly what each one is for.
EUR = 'EUR'
EGP = 'EGP'

SYMBOLS = {EUR: '€', EGP: 'ج.م'}

#: Calculation lines the customer never sees, and the words for the ones they do.
HIDDEN_FROM_CUSTOMER = ('gross', 'vat')
CUSTOMER_LABELS = {'net': 'سعر العربية'}


def customer_lines(lines):
    """[(label, amount, code)] fit for a customer, from QuoteLine rows or the
    calculator's dicts. Zero rows go too, except the car's own price."""
    out = []
    for line in lines:
        code = line['code'] if isinstance(line, dict) else line.code
        label = line.get('label_ar') if isinstance(line, dict) else line.label
        amount = line['amount'] if isinstance(line, dict) else line.amount
        if code in HIDDEN_FROM_CUSTOMER or not (amount or code == 'net'):
            continue
        out.append((CUSTOMER_LABELS.get(code, label), amount, code))
    return out


def _amount(value, currency):
    return f"{value:,.2f} {SYMBOLS.get(currency, currency)}"


def _pct(value):
    """15, not 15.00. A Decimal column keeps its trailing zeros; an offer
    should not."""
    return f'{float(value):g}'


def _visible_lines(quote, currency):
    """[(label, amount, code)] worth showing a customer, in one currency.

    Zero rows are dropped: an offer that lists "EUR 1 certificate — 0.00 €" is
    an offer that invites a question about a service nobody bought.
    """
    return customer_lines(line for line in quote.lines.all()
                          if getattr(line.currency, 'code', None) == currency)


def _customer(quote):
    from car_import.services import identity
    return identity.id_details(quote.partner) if quote.partner_id else {
        'name': '', 'national_id': '', 'address': '', 'from_id': False}


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
            f'مقدم التعاقد {_pct(option.deposit_pct)}% ({_amount(option.deposit_eur, EUR)})')
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
            '<td class="n">سعر الإعلان</td><td class="n">الإجمالي</td><td class="n">مقدم التعاقد</td></tr>'
            f'{body}</table>{chosen_note}')


def car_label(quote):
    """The car in words: the Vehicle when there is one, else what was quoted."""
    if quote.vehicle_id:
        return str(quote.vehicle)
    return getattr(quote, 'car_label', '') or ''


def _programme_line(quote):
    """«مبادرة — ميناء الإسكندرية», or '' for a quotation made before programmes."""
    from car_import.services import programme as rules
    if quote.programme not in rules.PORTS:
        return ''
    return f'{rules.PROGRAMME_AR[quote.programme]} — {rules.PORT_AR.get(quote.port, quote.port)}'


def _programme_block(quote):
    """(title, [(label, value)], footnote) of what the programme adds to the
    offer outside the EUR total — the customs of a personal import, the
    initiative's deposit — or None. When the owner's table has no figure the
    block still says the charge exists; it never shows a number nobody gave."""
    from car_import.services import programme as rules
    if quote.programme == rules.PERSONAL:
        if quote.customs_eur is not None:
            return ('الجمارك والضرائب (استيراد شخصي)',
                    [('جمارك وضرائب العربية دي', rules.eur(quote.customs_eur))],
                    'مش داخلة في إجمالي سعر البيع.')
        return ('الجمارك والضرائب (استيراد شخصي)', [],
                'العربية دي عليها جمارك وضرائب، وقيمتها بتتأكد من الشركة قبل التعاقد. '
                'مش داخلة في إجمالي سعر البيع.')
    if quote.programme == rules.INITIATIVE:
        rows = [(rules.deposit_label(r), rules.usd(r['usd'])) for r in (quote.initiative_deposits or [])]
        # The company provides the initiative: its price is the car + the
        # initiative + the powers of attorney + the port fees (owner, 2026-09-30).
        poa = [(POA_LABEL, rules.usd(quote.poa_usd))] if quote.poa_usd is not None else []
        if rows:
            return ('قيمة المبادرة (الوديعة الدولارية)', rows + poa,
                    'بتتدفع بالدولار وبترجع بعد 5 سنين، ومش داخلة في إجمالي سعر البيع.')
        return ('قيمة المبادرة (الوديعة الدولارية)', poa,
                'قيمة المبادرة للعربية دي بتتأكد من الشركة قبل التعاقد، وبتتدفع بالدولار وبترجع بعد 5 سنين.')
    return None


POA_LABEL = 'ثمن التوكيلات'


def _programme_html(quote):
    """The programme block for the PDF, kept to a few lines: the offer is one A4
    page (91747f8) and it has to stay one with this block in it. The four
    initiative figures are a 2×2 grid — tier by residence — not four rows."""
    from car_import.services import programme as rules
    from car_import.services.initiative_values import REGION_AR, TIER_AR

    block = _programme_block(quote)
    if not block:
        return ''
    title, rows, footnote = block
    head = f'<h2>{_escape(title)} <span class="meta">— {_escape(footnote)}</span></h2>'
    deposits = quote.initiative_deposits or []
    tiers = [t for t in TIER_AR if any(r.get('tier') == t for r in deposits)]
    regions = [g for g in REGION_AR if any(r.get('region') == g for r in deposits)]
    if quote.programme == rules.INITIATIVE and len(tiers) * len(regions) > 1:
        value = {(r.get('tier'), r.get('region')): rules.usd(r['usd']) for r in deposits}
        header = ''.join(f'<td class="n">{_escape(REGION_AR[g])}</td>' for g in regions)
        body = ''.join(
            f'<tr><td>{_escape(TIER_AR[t])}</td>'
            + ''.join(f'<td class="n">{_escape(value.get((t, g), "—"))}</td>' for g in regions) + '</tr>'
            for t in tiers)
        if quote.poa_usd is not None:
            body += (f'<tr><td>{_escape(POA_LABEL)}</td>'
                     f'<td class="n" colspan="{len(regions)}">{_escape(rules.usd(quote.poa_usd))}</td></tr>')
        return f'{head}<table class="grid"><tr class="head"><td></td>{header}</tr>{body}</table>'
    if rows:
        table = ''.join(f'<tr><td>{_escape(label)}</td><td class="n">{_escape(value)}</td></tr>'
                        for label, value in rows)
        return f'{head}<table>{table}</table>'
    return head


def as_text(quote):
    """The offer as a WhatsApp message, in Arabic — the fallback when no PDF
    could be made."""
    who = _customer(quote)
    car = car_label(quote)

    out = ['عرض سعر سيارة']
    if who['name']:
        out.append(f'الاسم: {who["name"]}')
    if who['national_id']:
        out.append(f'الرقم القومي: {who["national_id"]}')
    if car:
        out.append(f'العربية: {car}')
    if _programme_line(quote):
        out.append(f'البرنامج: {_programme_line(quote)}')
    out.append(f'التاريخ: {quote.quote_date:%Y-%m-%d}')
    if quote.name:
        out.append(f'رقم العرض: {quote.name}')
    out.append('')
    out.extend(_options_text(quote))

    for label, amount, _code in _visible_lines(quote, EUR):
        out.append(f'{label}: {_amount(amount, EUR)}')

    out.append('')
    out.append(f'إجمالي سعر البيع: {_amount(quote.total_eur, EUR)}')
    out.append(f'مقدم التعاقد ({_pct(quote.deposit_pct)}%): {_amount(quote.deposit_eur, EUR)}')
    out.append(f'الباقي: {_amount(quote.balance_eur, EUR)}')

    block = _programme_block(quote)
    if block:
        title, rows, footnote = block
        out.append('')
        out.append(f'{title}:')
        for label, value in rows:
            out.append(f'{label}: {value}')
        out.append(footnote)

    egp_lines = _visible_lines(quote, EGP)
    if egp_lines:
        out.append('')
        out.append('مصاريف بتتحصّل في مصر عند الوصول:')
        for label, amount, _code in egp_lines:
            out.append(f'{label}: {_amount(amount, EGP)}')

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
        # Two of the sheet's notes on one line — same words, one line less, so
        # the offer with its programme block stays on one page.
        'التحويل لحساب الشركة من الخارج. طرق الدفع: نقداً أو تحويل بنكي.',
    ]
    # The sheet says "about 50,000 EGP" for every port. The owner's message of
    # 2026-09-16 gives two different figures, and the difference between them
    # is 50,000 EGP — too much to leave inside the word "about". The port's own
    # line in the "due on arrival" block states it — and the showroom saving
    # and the total under it; the notes only repeated them, and the one-page
    # offer needs those lines back.
    if not quote.port_fee_egp:
        notes.append('الأسعار باليورو مش شاملة مصاريف الميناء في مصر.')
    notes.append(f'نسبة مقدم التعاقد من إجمالي سعر البيع: {_pct(quote.deposit_pct)}%.')
    if quote.programme:
        from car_import.services import programme as rules
        notes.append(rules.contract_term_ar(quote.programme))
    if quote.total_egp_indicative:
        notes.append(
            f'أي رقم بالجنيه تقريبي بسعر اليوم ({quote.fx_rate_egp:,.2f}) وعليه عمولة تحويل '
            f'من 1.5% لـ 2%، والشركة مش بتضمن سعر صرف.')
    if quote.notes:
        notes.append(quote.notes.strip())
    return notes


def as_html(quote):
    """The offer as the customer's file — A4, the same look as the proforma.

    It carries what the owner asked for on 2026-09-29: the customer as their ID
    names them (name, national ID, address), the car, the price, the deposit
    to transfer now with the bank details, and the notes.
    """
    from car_import.services import proforma_document, sales_flow

    who = _customer(quote)
    issuer = proforma_document._issuer()
    company = _escape(getattr(issuer, 'name', '') or 'Khaled Automobile')

    rows_eur = ''.join(
        f'<tr><td>{_escape(label)}</td><td class="n">{_amount(amount, EUR)}</td></tr>'
        for label, amount, _code in _visible_lines(quote, EUR))

    egp_lines = _visible_lines(quote, EGP)
    block_egp = ''
    if egp_lines:
        rows_egp = ''.join(
            f'<tr><td>{_escape(label)}</td><td class="n">{_amount(amount, EGP)}</td></tr>'
            for label, amount, _code in egp_lines)
        # A total under a single line is the same number twice.
        total_egp = (f'<tr class="total"><td>الإجمالي بالجنيه</td>'
                     f'<td class="n">{_amount(quote.egp_due_on_arrival, EGP)}</td></tr>'
                     if len(egp_lines) > 1 else '')
        block_egp = f'<h2>مصاريف بتتحصّل في مصر عند الوصول</h2><table>{rows_egp}{total_egp}</table>'

    customer_rows = (f'<tr><td>الاسم{" (زي البطاقة)" if who["from_id"] else ""}</td>'
                     f'<td class="v">{_escape(who["name"] or "—")}</td></tr>')
    if who['national_id']:
        customer_rows += (f'<tr><td>الرقم القومي</td>'
                          f'<td class="n"><bdi>{_escape(who["national_id"])}</bdi></td></tr>')
    if who['address']:
        customer_rows += f'<tr><td>العنوان</td><td class="v">{_escape(who["address"])}</td></tr>'

    bank_text = sales_flow.bank_details_text()
    bank = (f'<h2>بيانات التحويل</h2><pre>{_escape(bank_text)}</pre>'
            f'<p class="meta">برجاء كتابة رقم العرض <bdi>{_escape(quote.name or "")}</bdi> في بيان '
            'التحويل، وابعت صورة التحويل على الواتساب.</p>') if bank_text else ''

    notes = ''.join(f'<li>{_escape(note)}</li>' for note in _notes(quote))
    car = _escape(car_label(quote) or '—')
    if _programme_line(quote):
        # One row, not two: the car and the programme it goes by.
        car += f'<br><span class="meta">{_escape(_programme_line(quote))}</span>'
    block_programme = _programme_html(quote)
    valid = (f'<tr><td>العرض ساري لحد</td><td class="n">{quote.valid_until:%Y-%m-%d}</td></tr>'
             if quote.valid_until else '')

    return f"""<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<title>عرض سعر {_escape(quote.name or '')}</title>
<style>
 {proforma_document._font_face()}
 /* One A4 page: the customer forwards it to a bank or a brother, not a printer. The spacing
    is tight on purpose: the programme block (2026-09-30) has to fit on the same page. */
 @page {{ size: A4; margin: 12mm 14mm; }}
 body {{ font-family: 'Cairo', 'Noto Naskh Arabic', 'Noto Sans Arabic', 'DejaVu Sans', sans-serif;
        color: #16324f; font-size: 10pt; line-height: 1.35; }}
 h1 {{ font-size: 15pt; margin: 0 0 0.5mm; }}
 h2 {{ font-size: 11pt; margin: 3mm 0 1mm; color: #55708c; }}
 .head {{ border-bottom: 2px solid #16324f; padding-bottom: 1.5mm; margin-bottom: 2mm; }}
 .meta {{ color: #55708c; font-size: 9pt; }}
 table {{ width: 100%; border-collapse: collapse; }}
 td {{ padding: 0.8mm 1mm; border-bottom: 1px solid #dfe6ee; }}
 td.n {{ text-align: left; direction: ltr; white-space: nowrap; }}
 td.v {{ text-align: left; }}
 /* A date or a reference is a left-to-right run inside Arabic text. Without
    an isolate it is reordered — the right characters in the wrong order. */
 bdi {{ unicode-bidi: isolate; }}
 tr.total td {{ font-weight: 700; border-top: 2px solid #16324f; border-bottom: none; }}
 table.options tr.head td {{ font-weight: 700; color: #55708c; font-size: 9pt; }}
 table.options tr.chosen td {{ background: #eef6f1; font-weight: 600; }}
 table.options a {{ color: #55708c; font-size: 8pt; text-decoration: none; }}
 table.grid tr.head td {{ color: #55708c; font-size: 8.5pt; }}
 h2 span.meta {{ font-weight: 400; font-size: 8pt; }}
 .due {{ margin: 2.5mm 0 1mm; padding: 1.8mm 4mm; background: #eef6f1; border-right: 4px solid #1f7a4d;
         font-size: 12pt; font-weight: 700; }}
 p {{ margin: 1.5mm 0; }}
 /* Each line finds its own direction: the IBAN left to right, a name right to left. */
 pre {{ font-family: inherit; white-space: pre-wrap; margin: 0; padding: 1.5mm 3mm; line-height: 1.25;
        background: #f6f8fb; unicode-bidi: plaintext; text-align: start; font-size: 8.5pt;
        page-break-inside: avoid; }}
 ol {{ color: #55708c; font-size: 8.5pt; line-height: 1.4; padding-right: 5mm; margin: 0; }}
</style></head><body>
<div class="head">
  <h1>عرض سعر — Quotation</h1>
  <div class="meta">{company}</div>
</div>
<table>
  <tr><td>رقم العرض</td><td class="n"><bdi>{_escape(quote.name or '—')}</bdi></td></tr>
  <tr><td>التاريخ</td><td class="n">{quote.quote_date:%Y-%m-%d}</td></tr>
  {valid}
  {customer_rows}
  <tr><td>العربية</td><td class="v">{car}</td></tr>
</table>
{_options_html(quote)}
<h2>السعر</h2>
<table>{rows_eur}
<tr class="total"><td>إجمالي سعر البيع</td><td class="n">{_amount(quote.total_eur, EUR)}</td></tr>
</table>
<div class="due">مقدم التعاقد المطلوب للحجز (<bdi>{_pct(quote.deposit_pct)}%</bdi>): <bdi>{_amount(quote.deposit_eur, EUR)}</bdi></div>
<p>الباقي: <bdi>{_amount(quote.balance_eur, EUR)}</bdi> — مستحق خلال 5 أيام عمل من التعاقد مع المورد.</p>
{block_programme}
{block_egp}
{bank}
<h2>ملاحظات</h2>
<ol>{notes}</ol>
</body></html>"""


def attach(quote):
    """Render the offer as a PDF and store it on the quote. Never raises;
    False when no file could be made (the caller then sends `as_text`)."""
    try:
        from car_import.services import proforma_document
        pdf = proforma_document.to_pdf(as_html(quote))
        if not pdf:
            return False
        reference = (quote.name or f'quote-{quote.pk}').replace('/', '-')
        stamp = timezone.now().strftime('%Y%m%d%H%M%S')
        quote.document.save(f'{reference}-{stamp}.pdf', ContentFile(pdf), save=False)
        type(quote)._base_manager.filter(pk=quote.pk).update(document=quote.document.name)
        return True
    except Exception:
        logger.exception('car_import: could not attach the quotation PDF')
        return False


def _escape(value):
    from django.utils.html import escape
    return escape(value)
