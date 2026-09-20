# -*- coding: utf-8 -*-
"""Give a customer back to the assistant when no person came.

A hand-over is a promise that a human will answer. On 2026-09-20 the client
himself was handed over — by a false alarm in the outbound gate — and wrote
into silence for an hour and a half: "لا انا مش عايزك تحوليني على حد انا عايز
اتكلم معك انت". The chaser warned the team twice. Nobody was there.

Under the selling policy (`services/policy.py`) staff monitor; they are not
sitting on the queue. So when a hand-over goes unanswered the conversation
returns to the assistant, which then actually ANSWERS the messages the customer
already sent — the platform only runs the AI on a new inbound message, so the
unanswered ones are put back through the same batching entry point a webhook
uses.

What never comes back by itself: refunds, cancellations, complaints, anything
legal, a specific instalment amount. Those were handed over because a person
must decide them; silence does not change that.
"""
import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

#: Topics a person must handle, however long it takes.
HUMAN_ONLY_TOPICS = {'refund', 'cancellation', 'complaint', 'legal', 'instalment_amount'}
RESUME_AFTER_KEY = 'car_import.ai_resume_after_minutes'
DEFAULT_RESUME_AFTER = 10
MAX_RESUMES_PER_DAY = 3
#: Past this, the customer is a person's to win back.
MAX_WAIT_MINUTES = 120


def resume_after_minutes():
    try:
        from modules.base.models import ConfigParameter
        row = ConfigParameter.objects.filter(key=RESUME_AFTER_KEY).values('value').first()
        return max(1, int(str((row or {}).get('value') or DEFAULT_RESUME_AFTER).strip()))
    except Exception:
        return DEFAULT_RESUME_AFTER


def may_resume(conversation):
    data = conversation.social_platform_data if isinstance(conversation.social_platform_data, dict) else {}
    topic = str(data.get('car_import_escalation_topic') or 'other').strip().lower()
    if topic in HUMAN_ONLY_TOPICS:
        return False
    today = timezone.localdate().isoformat()
    count = data.get('car_import_resumes', {})
    return int((count or {}).get(today, 0)) < MAX_RESUMES_PER_DAY


def unanswered_inbound(conversation, hours=12, limit=6):
    """The customer's messages since the last thing we said to them."""
    from modules.chat.models import Message
    rows = list(Message.objects.filter(conversation=conversation, is_internal=False,
                                       created_at__gte=timezone.now() - timedelta(hours=hours))
                .order_by('-created_at')[:30])
    pending = []
    for message in rows:                      # newest first
        if message.direction != 'inbound':
            break
        pending.append(message)
    return list(reversed(pending))[-limit:]


def give_back_to_ai(conversation, waited_minutes=None, reason=''):
    """Switch the assistant back on and let it answer what is waiting."""
    from car_import.services import internal_note
    from car_import.tasks import _owner_users_for_partner

    data = conversation.social_platform_data if isinstance(conversation.social_platform_data, dict) else {}
    today = timezone.localdate().isoformat()
    counts = dict(data.get('car_import_resumes') or {})
    counts = {today: int(counts.get(today, 0)) + 1}
    data['car_import_resumes'] = counts
    data['car_import_resumed_at'] = timezone.now().isoformat()
    conversation.handled_by_ai = True
    conversation.social_platform_data = data
    conversation.save(update_fields=['handled_by_ai', 'social_platform_data'])

    waiting = unanswered_inbound(conversation)
    queued = 0
    for message in waiting:
        try:
            message.handle_inbound_message_batching()
            queued += 1
        except Exception:
            logger.exception('car_import: could not re-queue message %s', message.pk)

    body = ('🤖 المحادثة رجعت للمساعد'
            + (f' بعد {waited_minutes} دقيقة من غير رد من الفريق' if waited_minutes else '')
            + (f' ({reason})' if reason else '') + '.\n'
            + (f'هيرد دلوقتي على {queued} رسالة كانت مستنية.' if queued
               else 'هيرد على رسالة العميل الجاية.')
            + '\nعايز تكمّل بنفسك؟ اقفل زرار الروبوت في هيدر الشات.')
    try:
        internal_note.post(conversation, body,
                           recipients=_owner_users_for_partner(conversation.social_partner),
                           subject='المحادثة رجعت للمساعد')
    except Exception:
        logger.exception('car_import: could not note the resume')
    logger.info('car_import: conversation %s given back to the assistant (%d queued)',
                conversation.pk, queued)
    return queued
