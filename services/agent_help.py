# -*- coding: utf-8 -*-
"""What the assistant leans on when it does not know — and what it must not forget.

Four small things, all from one test chat (the client's GM, 2026-10-01):

* **A figure the tables do not have is a colleague's to supply, now.** The
  assistant told him "a colleague confirms it" three times and nobody was ever
  told. `ask_staff` tags the people who own the tables in the thread, once per
  car, with exactly what is missing.
* **«معاك مبادرة؟» is asked once.** He answered "لا" and was asked again twenty
  minutes later. The answer is kept on the contact (`initiative_status`).
* **The car just priced is the car the offer is for.** Asked to send the offer,
  the assistant invented a mobile.de link and then asked for the screenshot it
  already had. The last priced inputs are kept and reused.
* **A link is the customer's or it is nothing.** `customer_sent_link` checks.
"""
import logging
import re

logger = logging.getLogger(__name__)

#: Who owns the customs table and the deposit sheet.
TABLE_OWNERS = ['car_import.management', 'car_import.sales_manager']
HELP_REPEAT_HOURS = 6
PRICING_MEMORY_HOURS = 72

KIND_AR = {
    'customs': ('قيمة الجمارك', 'Link Tracker ← الجمارك والمبادرات ← قيم الجمارك'),
    'initiative': ('قيمة المبادرة (الوديعة)', 'Link Tracker ← الجمارك والمبادرات ← قيم المبادرات'),
    'eu_origin': ('منشأ العربية', 'Link Tracker ← العربيات ← ماركات صناعة الاتحاد الأوروبي'),
}


def _cache():
    from django.core.cache import cache
    return cache


def ask_staff(partner, conversation, kind, car, year=None):
    """Tag the table's owners in the thread: this figure is missing, the
    customer is waiting. True when a note went out (once per car per few hours —
    a customer who asks three times is one request, not three)."""
    if partner is None:
        return False
    label, where = KIND_AR.get(kind, (kind, ''))
    car_text = ' '.join(str(x) for x in [car or 'عربية مش معروفة في الكتالوج', f'موديل {year}' if year else ''] if x)
    key = 'car_import:help:%s:%s:%s' % (partner.pk, kind, re.sub(r'\W+', '', car_text.lower()))
    try:
        if not _cache().add(key, 1, timeout=HELP_REPEAT_HOURS * 3600):
            return False
    except Exception:  # noqa: BLE001 — no cache is not a reason to stay silent
        logger.exception('car_import: help de-duplication is unavailable')
    try:
        from car_import.services import sales_flow
        from car_import.tasks import _users_in_groups
        recipients, seen = [], set()
        for user in list(_users_in_groups(TABLE_OWNERS)) + list(sales_flow.owners(partner)):
            if user.pk not in seen:
                seen.add(user.pk)
                recipients.append(user)
        if kind == 'eu_origin':
            body = (f'🙋 المساعد سعّر {car_text}، والماركة مش في قايمة ماركات صناعة الاتحاد الأوروبي. '
                    f'شهادة يورو 1 محتاجة عربية متصنعة في الاتحاد الأوروبي، وأي منشأ تاني بموافقة الإدارة.\n'
                    f'المساعد قال للعميل إن زميل بيأكد المنشأ. أكّده للعميل هنا، ولو الماركة أوروبية ضيفها في '
                    f'{where}.')
        else:
            body = (f'🙋 المساعد محتاج مساعدة: {label} لـ {car_text} مش موجودة في الجدول، والعميل مستني الرقم.\n'
                    f'المساعد قاله إن زميل بيأكدها. ردّ على العميل بالرقم هنا'
                    + (f'، وضيفه في {where} عشان المساعد يقوله لوحده بعد كده.' if where else '.'))
        return bool(sales_flow.note(partner, body, recipients=recipients, conversation=conversation,
                                    subject=f'المساعد محتاج {label}'))
    except Exception:
        logger.exception('car_import: could not ask staff for the missing figure')
        return False


# ── does the customer hold an initiative? ────────────────────────────────────
_NO_INITIATIVE = ('none', 'no', 'لا', 'معندوش')


def known_initiative(partner):
    """True / False as the customer already told us, else None."""
    status = str(getattr(partner, 'initiative_status', None) or '').strip().lower()
    if not status:
        return None
    return status not in _NO_INITIATIVE


def remember_initiative(partner, has_own_initiative):
    """Keep the answer on the contact. An existing «gulf» / «european» is never
    downgraded to a bare yes."""
    if partner is None or has_own_initiative is None:
        return
    current = str(getattr(partner, 'initiative_status', None) or '').strip().lower()
    if has_own_initiative:
        if current and current not in _NO_INITIATIVE:
            return
        value = 'yes'
    else:
        if current in _NO_INITIATIVE:
            return
        value = 'none'
    try:
        type(partner)._base_manager.filter(pk=partner.pk).update(initiative_status=value)
        partner.initiative_status = value
    except Exception:
        logger.exception('car_import: could not keep the initiative answer on the contact')


# ── the car that was just priced ─────────────────────────────────────────────
def _pricing_key(partner):
    return 'car_import:last_priced:%s' % partner.pk


def remember_pricing(partner, **inputs):
    if partner is None:
        return
    try:
        _cache().set(_pricing_key(partner), {k: v for k, v in inputs.items() if v not in (None, '')},
                     timeout=PRICING_MEMORY_HOURS * 3600)
    except Exception:
        logger.exception('car_import: could not remember the last priced car')


def last_pricing(partner):
    if partner is None:
        return {}
    try:
        return dict(_cache().get(_pricing_key(partner)) or {})
    except Exception:
        return {}


# ── a link is the customer's, or it is nothing ───────────────────────────────
def customer_sent_link(conversation, link, days=7):
    """Did the customer send this link (or its advert id) in this chat? True
    when there is no conversation to check — a staff test, not a customer."""
    if conversation is None:
        return True
    from car_import.services import mobile_de
    needles = [str(link or '').strip().lower()]
    ad_id = mobile_de.ad_id_from_link(link)
    if ad_id:
        needles.append(str(ad_id).lower())
    try:
        from datetime import timedelta

        from django.utils import timezone

        from modules.chat.models import Message
        rows = (Message.objects.filter(conversation=conversation, direction='inbound',
                                       created_at__gte=timezone.now() - timedelta(days=days))
                .values_list('content', flat=True))
        for content in rows:
            text = str(content or '').lower()
            if any(n and n in text for n in needles):
                return True
    except Exception:
        logger.exception('car_import: could not check the link against the chat')
        return True
    return False
