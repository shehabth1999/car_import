# -*- coding: utf-8 -*-
"""A page the client can read on their phone, to sign off the stage messages.

Asked for on 2026-09-16, in these words: *"ممكن تبعتلي اللينك ابعتهاله يراجعها
لو سمحت مش تكتبها هنا خالص"* — a link to forward, not fourteen messages pasted
into a chat thread.

That constraint shapes the output. The reviewer is reading on a phone, they are
not a developer, and they are being asked one question per stage: **is this what
you want a customer to receive?** So the page shows each message the way the
customer will actually see it — placeholders filled with a real example, in a
chat bubble — and puts the machinery (code, delay, template) underneath in
small print where it does not compete.

It is written into the tenant's own media directory rather than published
anywhere else: their domain, their server, their customers' wording. The page
carries no login, so treat the URL as the secret it is — regenerate it after
sign-off and the old one stops matching.

    uv run python manage.py export_stage_messages
    uv run python manage.py export_stage_messages --lang en
"""
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.html import escape


class _Example:
    """A deal that does not exist, so the page can be generated on an empty
    tenant and still show what a customer would read."""

    name = 'KA/2026/0042'
    arrival_port = 'الإسكندرية'
    vessel = 'MSC Rania'
    bl_number = 'MSCU7761234'
    acid_number = '3120260042'
    tracking_url = 'https://khaled-test.genie-erp.com/track/42'
    currency_note = 'EUR'
    amount_paid_marked = None
    amount_due_marked = None

    class vehicle:
        make, model, trim = 'Mercedes-Benz', 'C200', 'AMG Line'
        model_year, colour_exterior = 2024, 'أسود'
        vin = 'W1K2060461F123456'

    class partner:
        name = 'أحمد محمد'

    class assigned_to:
        name = 'آية'

    class _Date:
        def strftime(self, fmt):
            return '2026-10-12'

    eta = _Date()


class Command(BaseCommand):
    help = "Build a review page for the stage messages and print its URL"

    def add_arguments(self, parser):
        parser.add_argument('--lang', choices=['ar', 'en'], default='ar')

    def handle(self, *args, **options):
        from car_import.models import ImportStage
        from car_import.services import stage_notifier

        language = options['lang']
        stages = list(ImportStage.objects.order_by('sequence', 'id'))
        if not stages:
            self.stderr.write('No stages. Run seed_import_stages first.')
            return

        example = _Example()
        cards, on, off = [], 0, 0
        for index, stage in enumerate(stages, 1):
            raw = (stage.fallback_text_ar if language == 'ar' else stage.fallback_text_en) or ''
            rendered = stage_notifier.render_stage_message(example, stage, language=language)
            # What the reviewer needs is what will happen *after* they approve,
            # not today's kill-switch state. Every stage is seeded with
            # `notify_customer=False` until somebody signs off, so reporting
            # the live flag would print "no message" fourteen times and leave
            # them thinking we had not written any.
            will_send = bool(raw.strip())
            if will_send:
                on += 1
            else:
                off += 1
            cards.append(_card(index, stage, rendered, will_send))

        # "Is anything reaching my customers right now?" is the reviewer's
        # first question, and the honest answer is per-stage, not the global
        # kill switch: that switch defaults to ON, while every stage ships with
        # `notify_customer=False`. Reading the switch alone would print a
        # reassurance that was false, or withhold one that was true.
        live = any(stage.notify_customer for stage in stages)
        html = _page(cards, len(stages), on, off, live, language)
        stamp = timezone.now().strftime('%Y%m%d%H%M%S')
        path = default_storage.save(f'car_import/review/stage-messages-{language}-{stamp}.html',
                                    ContentFile(html.encode('utf-8')))
        url = default_storage.url(path)

        self.stdout.write(self.style.SUCCESS(
            f'\n{len(stages)} stage(s): {on} carry a message for the customer, '
            f'{off} have no text yet.'))
        self.stdout.write(f'\n  {url}\n')
        self.stdout.write('Prefix it with the tenant domain and send that link. '
                          'The page has no login — regenerate after sign-off.')


def _card(index, stage, rendered, will_send):
    name = escape(stage.name or stage.name_en or stage.code)
    body = escape(rendered).replace('\n', '<br>') if rendered.strip() else \
        '<span class="empty">— لسه مفيش نص للمرحلة دي —</span>'

    facts = []
    if not will_send:
        facts.append('<span class="tag off">مفيش نص، يعني مفيش رسالة</span>')
    elif stage.notify_customer:
        facts.append('<span class="tag on">بتتبعت دلوقتي</span>')
    else:
        facts.append('<span class="tag on">هتتبعت بعد الموافقة</span>')
    if stage.requires_agent_approval:
        facts.append('<span class="tag hold">الموظف بيدوس إرسال</span>')
    if stage.send_delay_minutes:
        facts.append(f'<span class="tag">تأخير {stage.send_delay_minutes} دقيقة</span>')
    if stage.attach_media:
        facts.append('<span class="tag">معاها صور/فيديو</span>')
    if stage.whatsapp_template_id:
        facts.append('<span class="tag">فيه قالب واتساب</span>')
    else:
        facts.append('<span class="tag warn">مفيش قالب واتساب</span>')

    return f"""
<article class="stage">
  <header><span class="num">{index}</span><h2>{name}</h2></header>
  <div class="tags">{''.join(facts)}</div>
  <div class="bubble">{body}</div>
  <p class="code">{escape(stage.code)}</p>
</article>"""


def _page(cards, total, on, off, live, language):
    warning = '' if live else (
        '<div class="banner">🔒 كل الرسايل دلوقتي <b>مقفولة</b> على النظام. '
        'مفيش حاجة بتتبعت لأي عميل لحد ما حضرتك توافق.</div>')

    return f"""<!doctype html>
<html lang="{language}" dir="{'rtl' if language == 'ar' else 'ltr'}"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>مراجعة رسايل المراحل</title>
<style>
 :root {{ --ink:#16324f; --muted:#55708c; --line:#e3eaf2; --bg:#f6f9fc;
          --bubble:#dcf8c6; --on:#1b7f4b; --off:#8a94a6; --warn:#b4530a; }}
 * {{ box-sizing: border-box; }}
 body {{ font-family:'Cairo','Segoe UI',sans-serif; margin:0; background:var(--bg);
         color:var(--ink); line-height:1.7; }}
 .wrap {{ max-width:720px; margin:0 auto; padding:1.5rem 1rem 4rem; }}
 h1 {{ font-size:1.4rem; margin:.5rem 0 .25rem; }}
 .lede {{ color:var(--muted); font-size:.95rem; margin:0 0 1.25rem; }}
 .counts {{ display:flex; gap:.5rem; flex-wrap:wrap; margin-bottom:1.25rem; }}
 .counts span {{ background:#fff; border:1px solid var(--line); border-radius:999px;
                 padding:.25rem .8rem; font-size:.85rem; }}
 .banner {{ background:#fff6e5; border:1px solid #f0d9a8; border-radius:12px;
            padding:.85rem 1rem; font-size:.9rem; margin-bottom:1.25rem; }}
 .stage {{ background:#fff; border:1px solid var(--line); border-radius:14px;
           padding:1rem 1.1rem 1.25rem; margin-bottom:1rem; }}
 .stage header {{ display:flex; align-items:center; gap:.6rem; }}
 .num {{ background:var(--ink); color:#fff; width:1.8rem; height:1.8rem; flex:none;
         border-radius:50%; display:grid; place-items:center; font-size:.85rem; }}
 .stage h2 {{ font-size:1.05rem; margin:0; }}
 .tags {{ margin:.6rem 0 .8rem; display:flex; gap:.4rem; flex-wrap:wrap; }}
 .tag {{ font-size:.75rem; color:var(--muted); border:1px solid var(--line);
         border-radius:999px; padding:.1rem .6rem; }}
 .tag.on {{ color:var(--on); border-color:#bfe6cd; }}
 .tag.off {{ color:var(--off); }}
 .tag.warn {{ color:var(--warn); border-color:#f0d9a8; }}
 .tag.hold {{ color:var(--warn); }}
 /* The message shown the way a customer meets it. A reviewer asked "is this
    right?" answers better looking at a chat bubble than at a form field. */
 .bubble {{ background:var(--bubble); border-radius:14px; padding:.85rem 1rem;
            font-size:.98rem; white-space:normal; }}
 .empty {{ color:var(--warn); font-style:italic; }}
 .code {{ color:var(--off); font-size:.72rem; margin:.6rem 0 0;
          font-family:ui-monospace,Menlo,Consolas,monospace; direction:ltr; }}
 footer {{ color:var(--muted); font-size:.85rem; margin-top:2rem;
           border-top:1px solid var(--line); padding-top:1rem; }}
 @media print {{ body {{ background:#fff; }} .stage {{ break-inside:avoid; }} }}
</style></head><body><div class="wrap">
<h1>رسايل المراحل — للمراجعة والموافقة</h1>
<p class="lede">دي كل رسالة العميل هيستلمها لما عربيته تتنقل من مرحلة للي بعدها،
معروضة بالظبط زي ما هيشوفها على الواتساب. الأسماء والأرقام اللي جوه الرسايل
دي <b>مثال</b> — النظام بيحطّ بيانات كل عميل مكانها لوحده.</p>
{warning}
<div class="counts">
  <span>{total} مرحلة</span>
  <span>{on} فيها رسالة للعميل</span>
  {'<span>' + str(off) + ' من غير رسالة</span>' if off else ''}
</div>
{''.join(cards)}
<footer>
لو أي صياغة محتاجة تتغيّر، ابعتلنا رقم المرحلة والنص الجديد وهنعدّله.
مفيش أي رسالة بتتبعت لأي عميل قبل موافقتك.
</footer>
</div></body></html>"""
