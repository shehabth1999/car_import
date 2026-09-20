# -*- coding: utf-8 -*-
"""The proforma invoice, as a file a customer can hand to their bank.

A quotation says what the car costs. A proforma says what to pay NOW, to
which account, against which offer — it is the document a bank clerk asks for
before releasing a foreign-currency transfer, which is why it is a PDF and not
a chat message.

Rendered through WeasyPrint when the host has it (Pango shapes Arabic
correctly, which the older PDF engines did not). Where it does not, the same
HTML is stored instead and opens in any browser; and `as_text` is what goes to
the chat if no file could be made at all. One source, three fallbacks, and
none of them computes anything: every figure is read off the frozen invoice.
"""
import logging

from django.core.files.base import ContentFile
from django.utils import timezone

logger = logging.getLogger(__name__)


def _money(value):
    return f'{(value or 0):,.2f} €'


def _pct(value):
    return f'{float(value or 0):g}'


def _escape(value):
    return (str(value or '').replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def _issuer():
    try:
        from car_import.models import ContractIssuer
        return ContractIssuer.default()
    except Exception:
        return None


def as_text(invoice):
    out = [f'فاتورة مبدئية {invoice.name}',
           f'التاريخ: {invoice.invoice_date:%Y-%m-%d}',
           f'العميل: {getattr(invoice.partner, "name", "") or ""}']
    if invoice.car_label:
        out.append(f'العربية: {invoice.car_label}')
    if invoice.quote_id:
        out.append(f'على عرض السعر: {invoice.quote.name}')
    out += ['',
            f'إجمالي سعر البيع: {_money(invoice.total_amount)}',
            f'الجدية ({_pct(invoice.deposit_pct)}%) — المطلوب دلوقتي: {_money(invoice.amount_due)}',
            f'الباقي بعد الجدية: {_money((invoice.total_amount or 0) - (invoice.amount_due or 0))}']
    if invoice.valid_until:
        out.append(f'الفاتورة سارية لحد: {invoice.valid_until:%Y-%m-%d}')
    out += ['', 'الفاتورة دي طلب دفع مش إيصال استلام. استلام المبلغ بيتأكد من الحسابات بعد التحويل.']
    return '\n'.join(out)


def _font_face():
    """The system's own typeface, from the file the web app already ships.
    No host package, nothing to install: if the file is not there the page
    falls back to whatever Arabic face the host has."""
    import os

    from django.conf import settings
    path = os.path.join(str(settings.BASE_DIR), 'project', 'web', 'src', 'assets', 'css',
                        'fonts', 'cairo', 'Cairo-Variable.woff2')
    if not os.path.exists(path):
        return ''
    url = 'file://' + path.replace(os.sep, '/')
    return ("@font-face { font-family: 'Cairo'; font-weight: 200 1000; "
            f"src: url('{url}') format('woff2'); }}")


def as_html(invoice):
    issuer = _issuer()
    lines = ''
    if invoice.quote_id:
        for line in invoice.quote.lines.select_related('currency').all():
            if getattr(line.currency, 'code', '') != 'EUR' or not (line.amount or line.code in ('gross', 'net')):
                continue
            lines += f'<tr><td>{_escape(line.label)}</td><td class="n">{_money(line.amount)}</td></tr>'
    bank = (f'<h2>بيانات التحويل</h2><pre>{_escape(invoice.bank_details_text)}</pre>'
            f'<p class="meta">برجاء كتابة رقم الفاتورة <bdi>{_escape(invoice.name)}</bdi> في بيان التحويل.</p>'
            if invoice.bank_details_text else
            '<p class="meta">بيانات التحويل هتوصل حضرتك من الحسابات.</p>')
    company = _escape(getattr(issuer, 'name', '') or 'K&T')
    legal = ' · '.join(_escape(x) for x in [
        f'س.ت {issuer.commercial_register}' if getattr(issuer, 'commercial_register', '') else '',
        f'ب.ض {issuer.tax_card}' if getattr(issuer, 'tax_card', '') else '',
        getattr(issuer, 'address', '') or ''] if x)
    return f"""<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<title>فاتورة مبدئية {_escape(invoice.name)}</title>
<style>
 {_font_face()}
 @page {{ size: A4; margin: 18mm 16mm; }}
 body {{ font-family: 'Cairo', 'Noto Naskh Arabic', 'Noto Sans Arabic', 'DejaVu Sans', sans-serif;
        color: #16324f; font-size: 11.5pt; line-height: 1.7; }}
 h1 {{ font-size: 19pt; margin: 0 0 2mm; }}
 h2 {{ font-size: 12.5pt; margin: 7mm 0 2mm; color: #55708c; }}
 .head {{ border-bottom: 2px solid #16324f; padding-bottom: 4mm; margin-bottom: 5mm; }}
 .meta {{ color: #55708c; font-size: 10pt; }}
 table {{ width: 100%; border-collapse: collapse; }}
 td {{ padding: 2.2mm 1mm; border-bottom: 1px solid #dfe6ee; }}
 td.n {{ text-align: left; direction: ltr; white-space: nowrap; }}
 tr.total td {{ font-weight: 700; border-top: 2px solid #16324f; border-bottom: none; }}
 .due {{ margin: 6mm 0; padding: 4mm 5mm; background: #eef6f1; border-right: 4px solid #1f7a4d;
         font-size: 13.5pt; font-weight: 700; }}
 pre {{ font-family: inherit; white-space: pre-wrap; margin: 0; padding: 3mm 4mm;
        background: #f6f8fb; direction: ltr; text-align: left; }}
</style></head><body>
<div class="head">
  <h1>فاتورة مبدئية — Proforma Invoice</h1>
  <div class="meta">{company}{(' — ' + legal) if legal else ''}</div>
</div>
<table>
  <tr><td>رقم الفاتورة</td><td class="n"><bdi>{_escape(invoice.name)}</bdi></td></tr>
  <tr><td>التاريخ</td><td class="n">{invoice.invoice_date:%Y-%m-%d}</td></tr>
  <tr><td>العميل</td><td class="n" style="direction:rtl">{_escape(getattr(invoice.partner, 'name', '') or '')}</td></tr>
  <tr><td>العربية</td><td class="n" style="direction:rtl">{_escape(invoice.car_label or '—')}</td></tr>
  <tr><td>على عرض السعر</td><td class="n"><bdi>{_escape(invoice.quote.name if invoice.quote_id else '—')}</bdi></td></tr>
  {f'<tr><td>سارية لحد</td><td class="n">{invoice.valid_until:%Y-%m-%d}</td></tr>' if invoice.valid_until else ''}
</table>
<h2>تفاصيل السعر</h2>
<table>{lines}
  <tr class="total"><td>إجمالي سعر البيع</td><td class="n">{_money(invoice.total_amount)}</td></tr>
</table>
<div class="due">المطلوب دلوقتي — الجدية ({_pct(invoice.deposit_pct)}%): <bdi>{_money(invoice.amount_due)}</bdi></div>
<p>الباقي بعد الجدية: <bdi>{_money((invoice.total_amount or 0) - (invoice.amount_due or 0))}</bdi>،
   ومستحق خلال 5 أيام عمل من التعاقد مع المورد.</p>
{bank}
<p class="meta">الفاتورة دي طلب دفع مش إيصال استلام. استلام المبلغ بيتأكد من الحسابات بعد التحويل،
وبعدها العقد بيتبعت لحضرتك.</p>
</body></html>"""


def to_pdf(html):
    """PDF bytes, or None when the host cannot make one."""
    try:
        from weasyprint import HTML
        return HTML(string=html).write_pdf()
    except Exception:
        logger.exception('car_import: could not render the proforma as PDF; storing HTML instead')
        return None


def attach(invoice):
    """Render and store the file on the invoice. Never raises."""
    try:
        html = as_html(invoice)
        reference = (invoice.name or f'proforma-{invoice.pk}').replace('/', '-')
        stamp = timezone.now().strftime('%Y%m%d%H%M%S')
        pdf = to_pdf(html)
        if pdf:
            invoice.document.save(f'{reference}-{stamp}.pdf', ContentFile(pdf), save=False)
        else:
            invoice.document.save(f'{reference}-{stamp}.html', ContentFile(html.encode('utf-8')),
                                  save=False)
        type(invoice)._base_manager.filter(pk=invoice.pk).update(document=invoice.document.name)
        return True
    except Exception:
        logger.exception('car_import: could not attach the proforma file')
        return False
