# -*- coding: utf-8 -*-
"""Turn the stage messages into WhatsApp templates Meta will actually accept.

Asked for on 2026-09-16: *"لو في مسودة جاهزة عندكم ابعتهالي وهنراجعها ولو مفيش
حددلي بس تبقا القوالب لانهي تفاصيل"* — send the draft if there is one, otherwise
say which details each template should carry.

There is one, because the wording already exists on the stages. What did not
exist is the translation into Meta's shape, and that translation is not
cosmetic — Meta rejects things the stage text does happily:

* **a body may not begin or end with a placeholder.** `shipped_bl` ends with
  `{tracking_url}`, which is an instant rejection. Rewritten with a closing
  sentence rather than by dropping the link;
* **two placeholders may not touch.** `{model} {model_year}` is fine (a space
  between them); `{a}{b}` is not;
* **every variable needs a sample value**, and the sample is what a reviewer
  reads — so these are real: a real vessel name, a real-looking B/L, a date;
* **UTILITY, not MARKETING.** A shipping update is a utility message. One
  template here is borderline and is flagged rather than quietly submitted.

Submission stays a human's job. This produces the draft, the JSON, and a page
the client can read — it does not talk to Meta.

    uv run python manage.py export_whatsapp_templates
"""
import json
import re

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.html import escape

#: What each placeholder means, and the sample Meta's reviewer will see. The
#: samples are deliberately plausible: a reviewer reading "XXXX" assumes the
#: template is a spam vehicle, and the review takes days either way.
VARIABLES = {
    'customer_name': ('اسم العميل', 'أحمد محمد'),
    'model': ('الماركة والموديل', 'Mercedes-Benz C200'),
    'model_year': ('سنة الموديل', '2024'),
    'vessel': ('اسم الباخرة', 'MSC Rania'),
    'bl_number': ('رقم بوليصة الشحن', 'MSCU7761234'),
    'eta': ('تاريخ الوصول المتوقع', '2026-10-12'),
    'port': ('ميناء الوصول', 'الإسكندرية'),
    'tracking_url': ('لينك تتبع الشحنة', 'https://khaledautomobile.de/track/42'),
    'deal_ref': ('رقم الصفقة', 'KA/2026/0042'),
    'stage_name': ('اسم المرحلة', 'الشحن الدولي'),
    'agent_name': ('اسم المندوب', 'آية'),
    'colour': ('اللون', 'أسود'),
    'vin': ('رقم الشاسيه', 'W1K2060461F123456'),
    'acid_number': ('رقم ACID', '3120260042'),
    'trim': ('الفئة', 'AMG Line'),
    'amount_paid': ('المدفوع', '11,574 €'),
    'amount_due': ('المستحق', '34,722 €'),
}

#: Bodies that would be rejected for ending on a placeholder get a closing
#: sentence. Keyed by stage code, so the fix is visible and reviewable rather
#: than a regex guessing at Arabic.
CLOSING_SENTENCE = {
    'shipped_bl': 'وهنفضل نطمّن حضرتك أول بأول.',
}

BODY_LIMIT = 1024


class Command(BaseCommand):
    help = "Draft the WhatsApp templates for the stage messages"

    def add_arguments(self, parser):
        parser.add_argument('--prefix', default='ka',
                            help="Template name prefix (default: ka)")

    def handle(self, *args, **options):
        from car_import.models import ImportStage

        stages = list(ImportStage.objects.order_by('sequence', 'id'))
        if not stages:
            self.stderr.write('No stages. Run seed_import_stages first.')
            return

        drafts = [_draft(stage, options['prefix']) for stage in stages
                  if (stage.fallback_text_ar or '').strip()]

        payload = [{'name': d['name'], 'language': 'ar', 'category': d['category'],
                    'components': [{'type': 'BODY', 'text': d['body'],
                                    'example': {'body_text': [[v['sample'] for v in d['variables']]]}}]
                                  if d['variables'] else
                                  [{'type': 'BODY', 'text': d['body']}]}
                   for d in drafts]

        stamp = timezone.now().strftime('%Y%m%d%H%M%S')
        json_path = default_storage.save(
            f'car_import/review/whatsapp-templates-{stamp}.json',
            ContentFile(json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')))
        html_path = default_storage.save(
            f'car_import/review/whatsapp-templates-{stamp}.html',
            ContentFile(_page(drafts).encode('utf-8')))

        flagged = sum(1 for d in drafts if d['warnings'])
        self.stdout.write(self.style.SUCCESS(
            f'\n{len(drafts)} template(s) drafted, {flagged} with something to check.'))
        for d in drafts:
            for warning in d['warnings']:
                self.stdout.write(self.style.WARNING(f'  {d["name"]}: {warning}'))
        self.stdout.write(f'\n  review page: {default_storage.url(html_path)}')
        self.stdout.write(f'  submission JSON: {default_storage.url(json_path)}\n')
        self.stdout.write('Send the review page. Nothing here has been submitted to Meta.')


def _draft(stage, prefix):
    text = (stage.fallback_text_ar or '').strip()
    name = f'{prefix}_{stage.code}'.lower()[:512]

    # Positional placeholders, in the order they first appear — which is what
    # Meta numbers them by, and what the example array must match.
    order, body = [], text
    for token in re.findall(r'\{(\w+)\}', text):
        if token not in order:
            order.append(token)
    for index, token in enumerate(order, 1):
        body = body.replace('{%s}' % token, '{{%d}}' % index)

    warnings = []
    unknown = [t for t in order if t not in VARIABLES]
    if unknown:
        warnings.append('متغيرات مش معروفة: ' + ', '.join(unknown))

    closing = CLOSING_SENTENCE.get(stage.code)
    if closing and not body.rstrip().endswith(closing):
        body = f'{body.rstrip()} {closing}'

    stripped = body.strip()
    if re.match(r'^\{\{\d+\}\}', stripped):
        warnings.append('بيبدأ بمتغير — ميتا بترفض كده.')
    if re.search(r'\{\{\d+\}\}$', stripped):
        warnings.append('بينتهي بمتغير — ميتا بترفض كده.')
    if re.search(r'\}\}\s*\{\{', stripped):
        warnings.append('متغيرين ورا بعض من غير كلام بينهم — ميتا بترفض كده.')
    if len(stripped) > BODY_LIMIT:
        warnings.append(f'النص أطول من {BODY_LIMIT} حرف.')
    # A price inside a UTILITY template is what gets one reclassified as
    # MARKETING, and a reclassified template is a rejected template.
    if re.search(r'\d[\d,]{2,}\s*(جنيه|يورو|€|ج\.م)', stripped):
        warnings.append('فيه سعر جوه القالب — ممكن ميتا تعتبره تسويقي. '
                        'يا إما نشيل الرقم يا إما نبعته كرسالة عادية جوه الـ24 ساعة.')

    return {
        'name': name,
        'stage': stage.name or stage.code,
        'sequence': stage.sequence,
        'category': 'UTILITY',
        'body': stripped,
        'variables': [{'index': i, 'token': t,
                       'label': VARIABLES.get(t, (t, ''))[0],
                       'sample': VARIABLES.get(t, (t, t))[1]}
                      for i, t in enumerate(order, 1)],
        'warnings': warnings,
        'preview': _preview(stripped, order),
    }


def _preview(body, order):
    """The body with the samples substituted — what the customer would read."""
    out = body
    for index, token in enumerate(order, 1):
        out = out.replace('{{%d}}' % index, VARIABLES.get(token, (token, token))[1])
    return out


def _page(drafts):
    cards = []
    for draft in drafts:
        variables = ''.join(
            f'<tr><td>{{{{{v["index"]}}}}}</td><td>{escape(v["label"])}</td>'
            f'<td class="s">{escape(v["sample"])}</td></tr>'
            for v in draft['variables'])
        table = (f'<table class="vars"><tr><th>#</th><th>البيان</th><th>مثال</th></tr>'
                 f'{variables}</table>') if variables else \
            '<p class="none">مفيش متغيرات — نص ثابت.</p>'
        warnings = ''.join(f'<li>{escape(w)}</li>' for w in draft['warnings'])
        warn_block = f'<ul class="warn">{warnings}</ul>' if warnings else ''
        cards.append(f"""
<article class="tpl">
  <header><h2>{escape(draft['stage'])}</h2>
    <code>{escape(draft['name'])}</code>
    <span class="cat">{draft['category']}</span></header>
  <div class="bubble">{escape(draft['preview']).replace(chr(10), '<br>')}</div>
  {warn_block}
  <details><summary>النص اللي هيتبعت لميتا</summary>
    <pre>{escape(draft['body'])}</pre>{table}</details>
</article>""")

    return f"""<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>قوالب واتساب — مسودة للمراجعة</title>
<style>
 :root {{ --ink:#16324f; --muted:#55708c; --line:#e3eaf2; --bg:#f6f9fc;
          --bubble:#dcf8c6; --warn:#b4530a; }}
 * {{ box-sizing:border-box; }}
 body {{ font-family:'Cairo','Segoe UI',sans-serif; margin:0; background:var(--bg);
         color:var(--ink); line-height:1.7; }}
 .wrap {{ max-width:720px; margin:0 auto; padding:1.5rem 1rem 4rem; }}
 h1 {{ font-size:1.4rem; margin:.5rem 0 .25rem; }}
 .lede {{ color:var(--muted); font-size:.95rem; margin:0 0 1.25rem; }}
 .tpl {{ background:#fff; border:1px solid var(--line); border-radius:14px;
         padding:1rem 1.1rem 1.25rem; margin-bottom:1rem; }}
 .tpl header {{ display:flex; align-items:center; gap:.6rem; flex-wrap:wrap; }}
 .tpl h2 {{ font-size:1.05rem; margin:0; }}
 code {{ font-size:.75rem; color:var(--muted); direction:ltr;
         font-family:ui-monospace,Menlo,Consolas,monospace; }}
 .cat {{ font-size:.7rem; border:1px solid var(--line); border-radius:999px;
         padding:.1rem .6rem; color:var(--muted); }}
 .bubble {{ background:var(--bubble); border-radius:14px; padding:.85rem 1rem;
            margin:.8rem 0; }}
 ul.warn {{ color:var(--warn); font-size:.88rem; background:#fff6e5;
            border:1px solid #f0d9a8; border-radius:10px; padding:.6rem 1.6rem; }}
 details {{ margin-top:.6rem; font-size:.85rem; color:var(--muted); }}
 summary {{ cursor:pointer; }}
 pre {{ background:#f2f6fa; padding:.7rem; border-radius:8px; white-space:pre-wrap;
        font-size:.8rem; }}
 table.vars {{ width:100%; border-collapse:collapse; margin-top:.5rem; }}
 table.vars td, table.vars th {{ border-bottom:1px solid var(--line);
        padding:.3rem .4rem; text-align:right; font-size:.8rem; }}
 td.s {{ direction:ltr; text-align:left; }}
 .none {{ font-size:.8rem; }}
 footer {{ color:var(--muted); font-size:.85rem; margin-top:2rem;
           border-top:1px solid var(--line); padding-top:1rem; }}
</style></head><body><div class="wrap">
<h1>قوالب واتساب — مسودة للمراجعة</h1>
<p class="lede">دي القوالب اللي هنقدّمها لواتساب عشان نقدر نبعت تحديث للعميل
<b>بعد ما يعدّي 24 ساعة</b> من آخر رسالة منه. جوه الـ24 ساعة بنبعت نص عادي
من غير قوالب. المكتوب في الأخضر هو اللي العميل هيقراه، والأسماء والأرقام
اللي جواه <b>مثال</b>.</p>
<p class="lede">القوالب كلها <b>UTILITY</b> (تحديث شحنة)، مش تسويقية — ده
بيخلي الموافقة أسرع وبيمنع إن العميل يقدر يوقفها.</p>
{''.join(cards)}
<footer>لو أي صياغة محتاجة تتغيّر، ابعتلنا اسم المرحلة والنص الجديد.
مفيش حاجة اتقدّمت لواتساب لحد دلوقتي — دي مسودة بس.</footer>
</div></body></html>"""
