# -*- coding: utf-8 -*-
"""What the agent is told about this customer and this thread, every turn.

The `prepare_turn` function node calls these and puts the text into the
uncached `<dynamic_context>` system message. They live here rather than in
the node's code box for two reasons: the box caps near 10,000 characters,
and a function in the package is reviewable and importable. The trade is the
usual one for import-time code — a change here needs a Celery restart.

Nothing here reaches for the national ID or the passport. They are on the
contact for the paperwork, not for a chat prompt.
"""
from django.utils import timezone

CHANNEL_NAMES = {
    'whatsapp': 'واتساب', 'messenger': 'ماسنجر', 'instagram': 'إنستجرام',
    'tiktok': 'تيك توك', 'webbot': 'شات الموقع', 'web': 'شات الموقع',
}

MEDIA_KINDS = {
    'image': '[صورة]', 'document': '[ملف]', 'file': '[ملف]', 'audio': '[صوت]',
    'voice': '[صوت]', 'video': '[فيديو]', 'sticker': '[ستيكر]',
}


def channel_label(conversation):
    """'واتساب', 'ماسنجر', … — the voice adapts to the channel."""
    channel = str(getattr(conversation, 'type', '') or '').lower()
    return CHANNEL_NAMES.get(channel) or channel or 'غير معروفة'


def partner_facts(partner):
    """Who the customer is: the contact's own fields, then the latest lead's
    qualification (programme, the car they want, budget, eligibility)."""
    lines = []
    if partner is None:
        return 'مفيش بيانات مسجّلة عن العميل.'

    lines.append('الاسم: %s' % (getattr(partner, 'name', None) or '-'))
    if getattr(partner, 'phone', None):
        lines.append('الرقم: %s' % partner.phone)
    if getattr(partner, 'residence_country', None):
        lines.append('بلد الإقامة: %s%s' % (
            partner.residence_country, ' (مصري بالخارج)' if getattr(partner, 'is_expat', False) else ''))
    if getattr(partner, 'initiative_status', None):
        lines.append('حالة المبادرة: %s' % partner.initiative_status)
    if getattr(partner, 'budget_band', None):
        lines.append('الميزانية: %s' % partner.budget_band)
    if getattr(partner, 'kyc_complete', False):
        lines.append('المستندات: مكتملة')
    created = getattr(partner, 'created_at', None)
    if created:
        lines.append('عميل عندنا من: %s' % timezone.localtime(created).date())

    try:
        from modules.crm.models import Lead
        lead = Lead.all_objects.filter(partner_id=partner.pk).order_by('-id').first()
    except Exception:
        lead = None
    if lead is not None:
        if getattr(lead, 'ka_program', None):
            lines.append('البرنامج: %s%s' % (
                lead.ka_program, ' / ' + lead.ka_initiative_type if getattr(lead, 'ka_initiative_type', None) else ''))
        wanted = ' '.join(str(x) for x in [
            getattr(lead, 'ka_model_wanted', None), getattr(lead, 'ka_model_year_wanted', None),
            getattr(lead, 'ka_trim_wanted', None), getattr(lead, 'ka_colour_wanted', None)] if x)
        if wanted:
            lines.append('العربية المطلوبة: %s%s' % (
                wanted, ' (%s)' % lead.ka_condition_wanted if getattr(lead, 'ka_condition_wanted', None) else ''))
        if getattr(lead, 'ka_budget_eur', None):
            lines.append('ميزانيته باليورو: %s' % lead.ka_budget_eur)
        if getattr(lead, 'ka_funds_ready_on', None):
            lines.append('الفلوس جاهزة من: %s' % lead.ka_funds_ready_on)
        if getattr(lead, 'ka_eligibility_verdict', None):
            lines.append('الأهلية: %s%s' % (
                lead.ka_eligibility_verdict,
                ' — ' + lead.ka_eligibility_reason if getattr(lead, 'ka_eligibility_reason', None) else ''))
        stage = getattr(lead, 'stage', None)
        if stage is not None:
            lines.append('مرحلة العميل في الـCRM: %s' % stage)
    return '\n'.join(lines)


def recent_messages(conversation, partner, limit=6):
    """The last few messages as a one-line-each digest, oldest first.

    The platform injects the full recent history into the user turn already;
    this is the thread's *shape* — who said what last, when — so the model
    keeps it even when the injected history is long or has been summarised.
    Internal notes never appear: they are the staff's, not the customer's.
    """
    if conversation is None:
        return 'دي أول رسالة في المحادثة.'
    try:
        from modules.chat.models import Message
        rows = list(Message.objects.filter(conversation=conversation, is_internal=False)
                    .order_by('-created_at')[:limit])
    except Exception:
        return 'دي أول رسالة في المحادثة.'
    if not rows:
        return 'دي أول رسالة في المحادثة.'

    partner_id = getattr(partner, 'pk', None)
    lines = []
    for m in reversed(rows):
        content = getattr(m, 'content', None)
        body = (content.get('text') if isinstance(content, dict) else str(content or '')) or ''
        body = ' '.join(str(body).split())
        if not body:
            body = MEDIA_KINDS.get(str(getattr(m, 'type', '') or ''), '[رسالة]')
        mine = getattr(m, 'sender_id', None) == partner_id
        created = getattr(m, 'created_at', None)
        stamp = timezone.localtime(created).strftime('%d/%m %H:%M') if created else ''
        lines.append('%s %s: %s' % (stamp, 'العميل' if mine else 'إحنا', body[:220]))
    return '\n'.join(lines)


# ── where the sale stands, and what this message calls for ───────────────────
def sales_facts(partner, deal):
    """The open quotation, the proforma, a receipt waiting for the accountant,
    and what the contract still needs — so the assistant never re-prices a car
    it already quoted or asks twice for a national ID it already has."""
    if partner is None:
        return 'مفيش.'
    lines = []
    try:
        from car_import.models import PaymentReceipt, ProformaInvoice, Quote
        quote = (Quote.all_objects.filter(partner_id=partner.pk, state__in=['sent', 'accepted'])
                 .exclude(total_eur=0).order_by('-id').first())
        if quote is not None:
            state = 'العميل وافق عليه' if quote.state == 'accepted' else 'اتبعت ومستني رد العميل'
            lines.append('عرض السعر %s (%s): %s — الإجمالي %s € — الجدية %s%% = %s €%s' % (
                quote.name, state, quote.car_label or (str(quote.vehicle) if quote.vehicle_id else '-'),
                f'{quote.total_eur:,.2f}', f'{float(quote.deposit_pct):g}', f'{quote.deposit_eur:,.2f}',
                (' — ساري لحد %s' % quote.valid_until) if quote.valid_until else ''))
            if quote.paid_eur:
                lines.append('المؤكَّد استلامه: %s € — المتبقي %s €' % (
                    f'{quote.paid_eur:,.2f}', f'{quote.remaining_eur:,.2f}'))
        invoice = (ProformaInvoice.all_objects.filter(partner_id=partner.pk)
                   .exclude(state='cancelled').order_by('-id').first())
        if invoice is not None:
            lines.append('الفاتورة المبدئية %s: %s — المطلوب %s €' % (
                invoice.name, invoice.get_state_display(), f'{invoice.remaining_due:,.2f}'))
        waiting = PaymentReceipt.all_objects.filter(partner_id=partner.pk, state='pending').count()
        if waiting:
            lines.append('فيه %d تحويل مستني تأكيد المحاسب — متأكدش للعميل إن الفلوس وصلت.' % waiting)
        if deal is not None:
            from car_import.models import Contract
            from car_import.services import sales_flow
            contract = (Contract.all_objects.filter(deal_id=deal.pk).exclude(state='cancelled')
                        .order_by('-id').first())
            if contract is None or contract.state == 'draft':
                missing = (sales_flow.missing_contract_fields(contract) if contract is not None
                           else ['customer_name', 'customer_national_id'])
                ask = [sales_flow.CONTRACT_DETAIL_LABELS[m] for m in missing
                       if m in ('customer_name', 'customer_national_id')]
                if ask and invoice is not None:
                    lines.append('العقد ناقصه من العميل: ' + '، '.join(ask))
            elif contract.sent_at:
                lines.append('العقد اتبعت للعميل (%s).' % contract.get_state_display())
    except Exception:
        return 'مفيش.'
    return '\n'.join(lines) if lines else 'مفيش عرض سعر ولا فاتورة لسه.'


#: Every way a customer asks where to send the money.
BANK_WORDS = ['رقم الحساب', 'رقم حساب', 'الحسابات', 'حساباتك', 'حسابتك', 'حسابكم', 'حسابكو',
              'الحساب البنكي', 'بيانات التحويل', 'iban', 'ايبان', 'أحوّل', 'احول', 'احوّل',
              'التحويل على', 'انستاباي', 'إنستاباي', 'instapay', 'wise']

#: How our own bank-details message begins (tools/bank_tools.py, sales_flow.send_proforma).
BANK_MESSAGE_PREFIX = 'بيانات التحويل:'


def bank_details_pending(conversation, hours=6):
    """The customer asked where to transfer and has not been given the details.

    Looked up, not inferred: a hint keyed on the current message alone died the
    moment the customer followed up with "؟" or "ابعتها هنا" — two messages
    with no bank word in them — and the assistant answered from old history
    instead of calling the tool (live, 2026-09-20).
    """
    if conversation is None:
        return False
    try:
        from datetime import timedelta
        from modules.chat.models import Message
        rows = (Message.objects.filter(conversation=conversation, is_internal=False,
                                       created_at__gte=timezone.now() - timedelta(hours=hours))
                .order_by('-created_at')[:30])
        for m in rows:                          # newest first
            content = getattr(m, 'content', None)
            body = str((content.get('text') if isinstance(content, dict) else content) or '')
            if m.direction == 'outbound' and body.lstrip().startswith(BANK_MESSAGE_PREFIX):
                return False                    # already given, after the question
            if m.direction == 'inbound' and any(w in body.lower() for w in BANK_WORDS):
                return True
    except Exception:
        return False
    return False


def turn_warnings(message, deal, conversation=None):
    """What this particular message calls for. Short, and only when it applies:
    a warning raised on every turn gets read as standing orders."""
    from car_import.services import policy

    text = str(message or '').lower()
    ai_first = policy.ai_first()
    warnings = []

    if ai_first:
        # A standing order, on purpose. Long threads are full of replies written
        # under the old policy, and the model copies its own past sentences.
        warnings.append('السياسة اتغيّرت: إنت اللي بتسعّر العربية وتبعت عرض السعر والفاتورة المبدئية وبيانات '
                        'التحويل بنفسك بالأدوات. أي رد قديم في المحادثة بيقول «زميلي هيسعّر» أو «بيانات التحويل '
                        'مع الفاتورة» أو «الحسابات هتبعتها» اتلغى — متكررهوش.')

    if deal is not None and deal.program == 'initiative' and deal.customer_is_initiative_holder:
        warnings.append('العميل صاحب المبادرة: التقسيط مش متاح ليه.')

    clearance = ['جمارك', 'جمركي', 'تخليص', 'إفراج', 'افراج', 'سداد', 'المتبقي', 'الباقي']
    if deal is not None and deal.payment_state != 'fully_paid' and any(m in text for m in clearance):
        warnings.append('الصفقة مش مدفوعة بالكامل والعميل بيسأل عن التخليص: التخليص مبيبدأش قبل '
                        'سداد المتبقي. قول كده بوضوح، والمتبقي من «حالة البيع» تحت.')

    if 'كوريا' in text or 'korea' in text:
        warnings.append('العميل ذكر كوريا: الشركة أوروبا بس — اعتذر بذوق واقترح بديل أوروبي.')

    if ai_first:
        if any(m in text for m in ['خصم', 'تخفيض', 'آخر سعر', 'اخر سعر', 'نزّل', 'نزل السعر']):
            warnings.append('العميل بيطلب خصم: الخصم قرار الإدارة. استخدم ka_request_discount وكمّل '
                            'معاه — متوعدش بأي خصم ومتحوّلش المحادثة.')
        if any(m in text for m in ['استرداد', 'ارجاع فلوس', 'إلغاء', 'الغاء', 'ألغي', 'الغي']):
            warnings.append('استرداد أو إلغاء: ده قرار بني آدم — حوّل لزميل.')
        if any(m in text for m in BANK_WORDS) or bank_details_pending(conversation):
            warnings.append('العميل سأل يحوّل على أنهي حساب ولسه مخدش البيانات: استخدم ka_share_bank_details '
                            'دلوقتي حالاً، من غير شروط ومن غير ما تستنى عرض سعر أو فاتورة — الأداة بتبعتله '
                            'بيانات التحويل المعتمدة بنفسها. متكتبش رقم حساب ولا اسم بنك من عندك أبداً.')
        if any(m in text for m in ['حولت', 'حوّلت', 'دفعت', 'التحويل تم', 'بعت الفلوس']):
            warnings.append('العميل بيقول إنه حوّل: اطلب صورة التحويل لو مبعتهاش، وسجّلها بـ '
                            'ka_record_payment_receipt. تأكيد وصول الفلوس للمحاسب بس.')
    else:
        money = ['رقم الحساب', 'رقم حساب', 'iban', 'لينك الدفع', 'حولت', 'حوّلت', 'استرداد',
                 'ارجاع فلوس', 'خصم', 'قسط', 'تقسيط', 'مصاريف', 'رسوم', 'بكام', 'سعر']
        if any(m in text for m in money):
            warnings.append('المساعد مش مفعّل للبيع دلوقتي: أي سؤال فلوس → حوّل لزميل من غير أي رقم.')

    if not any('حوّل لزميل' in w for w in warnings):
        warnings.append('الرسالة دي مفيهاش حاجة تستدعي زميل: جاوب بنفسك من الأدوات.')
    return warnings


def build(partner, conversation, message):
    """Everything `prepare_turn` hands the model, in one call. In Arabic: a
    worker has no active language, and "Paid" in the middle of an Arabic
    briefing is a word the model repeats to the customer."""
    from django.utils import translation
    with translation.override('ar'):
        return _build(partner, conversation, message)


def _build(partner, conversation, message):
    deal = None
    partner_id = getattr(partner, 'pk', None)
    try:
        from car_import.models import CarDeal
        if partner_id:
            deal = (CarDeal.all_objects.select_related('vehicle', 'import_stage')
                    .filter(partner_id=partner_id).exclude(state='cancelled').order_by('-id').first())
    except Exception:
        deal = None

    facts = []
    if deal is not None:
        facts.append('رقم الصفقة: %s' % (deal.name or '-'))
        if deal.vehicle_id:
            facts.append('العربية: %s' % deal.vehicle)
        if deal.import_stage_id:
            facts.append('المرحلة: %s' % (deal.import_stage.name or deal.import_stage.name_en))
        if deal.eta:
            facts.append('الوصول المتوقع: %s' % deal.eta)
        if deal.arrival_port:
            facts.append('الميناء: %s' % deal.arrival_port)
        facts.append('حالة الدفع المسجّلة: %s' % deal.get_payment_state_display())

    warnings = turn_warnings(message, deal, conversation)
    return {
        'deal_reference': deal.name if deal is not None else '',
        'channel_label': channel_label(conversation),
        'partner_facts': partner_facts(partner),
        'recent_messages': recent_messages(conversation, partner),
        'deal_facts': '\n'.join(facts) if facts else 'مفيش صفقة مفتوحة للعميل ده.',
        'sales_facts': sales_facts(partner, deal),
        'warnings': '\n'.join('- ' + w for w in warnings),
    }
