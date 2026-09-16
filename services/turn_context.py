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
