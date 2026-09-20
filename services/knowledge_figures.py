# -*- coding: utf-8 -*-
"""The knowledge documents that are GENERATED, not written.

`knowledge/*.md` is prose a person maintains, and it carries no figures — a
hand-edited price list is a price list that drifts. But published fees,
instalment terms and the eligibility rules are knowledge too, and keeping them
as three agent tools was part of how the assistant ended up with 21 tools and a
habit of picking the wrong one.

So they are rendered here, from the same tables the quotation screen reads,
into documents `build_ka_knowledge` indexes next to the prose. One source of
truth: management edits a fee in الإعدادات, the save re-indexes
(`tasks.rebuild_ka_knowledge`), and the assistant's next search returns the new
number. A fee marked "never quote to a customer" is simply not rendered.

Written for retrieval, not for reading: one topic per short section, each
opening with the words a customer would actually use, so a search for "رسوم"
or "مصاريف" or "أتعاب" lands on the same paragraph.
"""
import logging

logger = logging.getLogger(__name__)


def _n(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f'{int(number):,}' if number == int(number) else f'{number:,.2f}'


def may_publish():
    """The figures follow the same switches the fee tools did."""
    try:
        from car_import.tools.deal_tools import _may_quote_published_fees
        return _may_quote_published_fees()
    except Exception:
        return False


def fees_document():
    from car_import.tools.deal_tools import _fees_from_tables
    fees = _fees_from_tables()
    if not fees:
        return ''
    confirmed = fees.get('confirmed_on') or ''
    lines = ['# المصاريف والرسوم والأتعاب المعلنة (أسعار ثابتة من جدول المصاريف)',
             f'آخر تأكيد: {confirmed}' if confirmed else '', '']
    rows = (
        ('company_fee_eur', 'أتعاب الشركة / عمولة الشركة / مصاريف الشركة على الاستيراد', 'يورو'),
        ('company_fee_with_eur1_eur', 'أتعاب الشركة لما العربية معاها شهادة يورو 1 (EUR 1)', 'يورو'),
        ('port_and_clearance_egp', 'مصاريف الميناء والتخليص الجمركي في مصر (بتتدفع بالجنيه عند الوصول)', 'جنيه'),
        ('powers_of_attorney_usd', 'رسوم التوكيلات', 'دولار'),
        ('licensing_service_egp', 'خدمة مندوب الترخيص (خدمة المندوب بس، مش تكلفة الرخصة)', 'جنيه'),
        ('protection_film_egp', 'فيلم الحماية (اختياري)', 'جنيه'),
    )
    for key, label, currency in rows:
        if fees.get(key) in (None, ''):
            continue
        lines += [f'## {label}', f'{label}: {_n(fees[key]) if not isinstance(fees[key], str) else fees[key]} {currency}.', '']
    try:
        from car_import.services.pricing import SHOWROOM_FEE, _fee
        saving = _fee(SHOWROOM_FEE, None)
    except Exception:
        saving = None
    if saving:
        lines += ['## الاستلام من المعرض بدل التوصيل لحد البيت',
                  f'مصاريف الميناء والتخليص شاملة التوصيل لحد باب البيت. لو العميل هيستلم العربية بنفسه من '
                  f'المعرض، بيتخصم {_n(abs(saving))} جنيه من مصاريف الميناء — يعني بيدفع أقل، مش أكتر.', '']
    lines += ['## تكلفة الرخصة نفسها',
              'تكلفة الرخصة نفسها مش بتتقال: بتختلف حسب العربية والمرور. وجّه العميل لمكتب الترخيص. '
              'الترخيص مش شامل في سعر العربية، وممكن يبدأ بعد أسبوعين من خروج العربية من الميناء.', '',
              '## السعر الكامل لعربية معيّنة',
              'الأرقام دي مصاريف منفصلة. السعر الكامل لعربية معيّنة (الإجمالي والجدية والباقي) '
              'بيتحسب بأداة التسعير، مش بالجمع من هنا.']
    return '\n'.join(line for line in lines if line is not None)


def instalments_document():
    from car_import.tools.deal_tools import _instalments_from_tables
    plan = _instalments_from_tables()
    if not plan:
        return ''
    lines = ['# التقسيط — شروط القسط المباشر من الشركة', '']
    if plan.get('available') is False:
        lines += ['التقسيط المباشر مش متاح حالياً.', '']
    if plan.get('down_payment_pct'):
        lines += ['## المقدم في التقسيط', f'المقدم في التقسيط: {_n(plan["down_payment_pct"])}% من إجمالي السعر.', '']
    if plan.get('terms_months'):
        months = ' أو '.join(f'{m} شهر' for m in plan['terms_months'])
        lines += ['## مدة التقسيط', f'مدة التقسيط: {months}.', '']
    if plan.get('rate_pct_per_year_flat'):
        lines += ['## فايدة التقسيط', f'الفايدة: {_n(plan["rate_pct_per_year_flat"])}% في السنة، ثابتة.', '']
    for title, key in (('أول قسط', 'first_instalment'), ('الشيكات', 'cheques'),
                       ('التقسيط شامل إيه', 'covers'), ('إمتى التقسيط مش متاح', 'not_available_when')):
        if plan.get(key):
            lines += [f'## {title}', str(plan[key]), '']
    lines += ['## قيمة القسط الشهري',
              'قيمة القسط المحددة لعميل معيّن مش بتتحسب في الشات: بيحسبها زميل بعد ما السعر يتحدد. '
              + (str(plan.get('amount_policy') or '')), '',
              '## التقسيط وصاحب المبادرة',
              'لو العميل هو نفسه صاحب المبادرة، التقسيط مش متاح: التخليص بيتم باسمه فالشركة ملهاش '
              'حق امتياز على العربية. البديل عربية من المعرض.']
    return '\n'.join(lines)


#: The same rules `tools.deal_tools.ka_check_import_eligibility` applies, in the
#: owner's words (confirmed 2026-09-14). Change one, change the other.
ELIGIBILITY_DOCUMENT = '''# مين يقدر يستورد إيه — قواعد الأهلية (مؤكدة من الإدارة 2026-09-14)

## المبادرة (المصريين بالخارج) — موديل وسنة العربية
المبادرة بتسمح بعربية موديل 2023 وأحدث. أقدم من كده مرفوض. التسجيل في المبادرة مقفول من 2024:
اللي معاه مبادرة قديمة بس هو اللي يقدر يستخدمها، أو يشتري مبادرة من حد.

## مبادرة خليجي وحجم الموتور (cc)
مبادرة خليجي على موتور أكبر من 1600cc: الوديعة بتعدّي 60 إلى 70 ألف دولار لأن مفيش شهادة يورو 1.
الأفضل موديل أقل من 1600cc.

## المبادرة والعداد (الكيلومترات)
عداد أعلى من 20 ألف كم مسموح في المبادرة، بس الشركة بتنصح بأقل من كده.

## الاستيراد الشخصي — زيرو بس
الاستيراد الشخصي لازم عربية زيرو موديل السنة الحالية، أوروبية المنشأ عشان تاخد شهادة يورو 1.
عربية مستعملة أو موديل سنة قديمة: مرفوض في الاستيراد الشخصي.

## الاستيراد التجاري
الاستيراد التجاري على رخصة الشركة متاح، زيرو موديل السنة الحالية، وبموافقة الإدارة لكل حالة —
اعرضه وحوّل لزميل للموافقة.

## ذوي الهمم
قانون ذوي الهمم متوقف حالياً والحكومة بتعدّل فيه. الشركة مش بتشتغل عليه دلوقتي.

## أقل ميزانية
الشركة بتشتغل على ميزانية من 2 مليون جنيه وأكتر. أقل من كده: اعتذر بذوق، والأنسب وكيل أو معرض في مصر.

## المرفوض دايماً
العربيات الكورية، والكهربا الصيني، والموتوسيكلات، وأي منشأ غير أوروبا إلا بموافقة الإدارة.
عربيات صنع أمريكا (GLE، GLS، X5) جمركها عالي — انصح العميل يشتريها من مصر.

## المستندات المطلوبة للمبادرة
صورة البطاقة وش وضهر، الباسبور، الإقامة، كشف حساب 6 شهور فيه تحويل الوديعة، إيصالات الوديعة،
الموافقة الاستيرادية، توكيل المخلص الجمركي.

## المستندات المطلوبة للاستيراد الشخصي
صورة البطاقة والباسبور.
'''


def schedule_rebuild():
    """Re-index shortly after the save commits. Best effort, and debounced: a
    manager editing five fees in a row triggers one rebuild, not five."""
    try:
        from django.core.cache import cache
        from django.db import transaction
        if not cache.add('car_import:knowledge_rebuild_pending', 1, timeout=30):
            return
        from car_import.tasks import rebuild_ka_knowledge
        transaction.on_commit(lambda: rebuild_ka_knowledge.apply_async(countdown=30))
    except Exception:
        logger.exception('car_import: could not schedule the knowledge rebuild')


def documents():
    """{filename: text} for every generated document worth indexing today."""
    out = {'92_eligibility_rules.md': ELIGIBILITY_DOCUMENT}
    if may_publish():
        for name, builder in (('90_published_fees.md', fees_document),
                              ('91_instalment_terms.md', instalments_document)):
            try:
                text = builder()
            except Exception:
                logger.exception('car_import: could not render %s', name)
                text = ''
            if text.strip():
                out[name] = text
    return out
