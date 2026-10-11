# -*- coding: utf-8 -*-
"""The stage messages as WhatsApp templates — drafted here, submitted by a person.

Outside WhatsApp's 24-hour window only a template Meta has approved may be
sent, so each stage that messages the customer needs one. This builds them as
DRAFTS in the platform's own template table and stops there: **nothing in this
module talks to Meta.** A draft is submitted when somebody presses Review on
the template's own screen, and not before.

How the platform's templates work, which is what shapes everything below
(`modules/whatsapp/models/template.py`, read 2026-10-11):

* a variable is written `{{name}}` and filled with `getattr(record, name)` from
  the record the template is sent for. For a stage message that record is the
  DEAL, so every variable is an attribute of `CarDeal` — a field that already
  carries the name (`vessel`, `bl_number`, `eta`, `tracking_url`) or one of the
  three properties added for this (`customer_name`, `car_full`, `port`);
* a template belongs to ONE WhatsApp number — its account, and behind it that
  number's own WhatsApp Business Account — so a set is created per number;
* binding the template to the deal (`content_type`) keeps it off the "send a
  template" list of every other screen, where its variables do not exist;
* when a template IS submitted, the platform takes each variable's example from
  the newest record of that model. The newest deal usually has no vessel and no
  bill of lading yet, and an empty example is a rejected template, so for these
  templates the examples are the ones below (`patches.apply_template_patches`).
"""
import re

#: What each placeholder means, and the sample Meta's reviewer will see. The
#: samples are deliberately plausible: a reviewer reading "XXXX" assumes the
#: template is a spam vehicle, and the review takes days either way.
VARIABLES = {
    'customer_name': ('اسم العميل', 'أحمد محمد'),
    'model': ('الماركة والموديل', 'Mercedes-Benz C200'),
    'car_full': ('العربية كاملة', 'Mercedes-Benz C200 2024'),
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

#: The variables a deal can fill today. A stage text that uses another
#: placeholder still becomes a draft, with a warning: it cannot be sent until
#: `CarDeal` has an attribute of that name.
DEAL_VARIABLES = ('customer_name', 'car_full', 'port', 'vessel', 'bl_number', 'eta', 'tracking_url',
                  'acid_number')


def body_for(stage):
    """(body, variables, warnings) — the stage's Arabic text in a template's shape."""
    text = (stage.fallback_text_ar or '').strip()
    variables = []
    for token in re.findall(r'\{(\w+)\}', text):
        if token not in variables:
            variables.append(token)
    body = re.sub(r'\{(\w+)\}', r'{{\1}}', text)

    closing = CLOSING_SENTENCE.get(stage.code)
    if closing and not body.endswith(closing):
        body = f'{body} {closing}'

    warnings = []
    unknown = [name for name in variables if name not in DEAL_VARIABLES]
    if unknown:
        warnings.append('uses ' + ', '.join(unknown) + ', which a deal cannot fill yet — it cannot be sent as it is')
    # A price inside a UTILITY template is what gets one reclassified as
    # MARKETING, and a reclassified template is a rejected template.
    if re.search(r'\d[\d,]{2,}\s*(جنيه|يورو|€|ج\.م)', body):
        warnings.append('states a price — Meta may treat it as marketing rather than a utility update')
    if len(body) > BODY_LIMIT:
        warnings.append(f'is longer than {BODY_LIMIT} characters')
    return body, variables, warnings


def deal_content_type():
    from django.contrib.contenttypes.models import ContentType

    from car_import.models import CarDeal
    return ContentType.objects.get_for_model(CarDeal)


def is_stage_template(template):
    """A template bound to the deal — one of these."""
    return bool(template.content_type_id) and template.content_type_id == deal_content_type().pk


def sample(name):
    """The example Meta's reviewer reads for this variable."""
    return VARIABLES.get(name, (name, name))[1]


def create_drafts(account, prefix='ka', link=True, dry_run=False):
    """One draft per stage that has a text, on this WhatsApp number.

    Creates the row, or rewrites it while it is still a draft nobody has
    submitted; a template that has been to Meta is left exactly as it is.
    With `link` each stage is pointed at its template — harmless while it is a
    draft, because the notifier only sends a template Meta has approved.

    Returns one dict per stage. Submits nothing.
    """
    from django.core.exceptions import ValidationError

    from car_import.models import ImportStage
    from modules.base.models import Language
    from modules.whatsapp.models import WhatsAppTemplate

    language = Language.objects.filter(code='ar').first()
    if language is None:
        raise ValueError('There is no Arabic language row (code "ar") to file the templates under')
    content_type = deal_content_type()

    results = []
    for stage in ImportStage.objects.order_by('sequence', 'id'):
        if not (stage.fallback_text_ar or '').strip():
            results.append({'stage': stage, 'outcome': 'no_text'})
            continue
        body, variables, warnings = body_for(stage)
        name = f'{prefix}_{stage.code}'.lower()
        template = WhatsAppTemplate.objects.filter(
            whatsapp_account=account, name=name, language=language).first()
        result = {'stage': stage, 'name': name, 'body': body, 'variables': variables,
                  'warnings': warnings, 'template': template}

        if template is not None and (template.template_id or template.status != 'draft'):
            # It has been to Meta: its wording is changed from its own screen
            # (Edit → Submit changes), never rewritten underneath a review.
            result['outcome'] = 'submitted_untouched'
        elif dry_run:
            result['outcome'] = 'would_update' if template is not None else 'would_create'
        else:
            result['outcome'] = 'updated' if template is not None else 'created'
            if template is None:
                template = WhatsAppTemplate(whatsapp_account=account, name=name, language=language)
            template.category = 'utility'
            template.status = 'draft'
            template.header_format = 'TEXT'
            template.body_text = body
            template.content_type = content_type
            try:
                template.save()
            except ValidationError as exc:
                result['outcome'] = 'refused'
                result['error'] = '; '.join(exc.messages)
                results.append(result)
                continue
            result['template'] = template
            if link and stage.whatsapp_template_id != template.pk:
                type(stage)._base_manager.filter(pk=stage.pk).update(whatsapp_template=template)
        results.append(result)
    return results
