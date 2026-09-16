# -*- coding: utf-8 -*-
"""Background work for car_import: sending the customer's stage message."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def notify_stage_change(self, log_id):
    """
    Send one stage message.

    Failure is never silent: the log row keeps the error, and the assigned agent
    gets an activity — a customer who was not told is a customer who will call.
    """
    from car_import.models import StageChangeLog
    from car_import.services.stage_notifier import deliver

    log = StageChangeLog.objects.filter(pk=log_id).select_related('deal', 'to_stage').first()
    if log is None:
        logger.warning("car_import: stage log %s vanished before sending", log_id)
        return {'success': False, 'error': 'log not found'}

    if log.notification_state not in ('pending', 'failed'):
        return {'success': True, 'skipped': log.notification_state}

    log = deliver(log)

    if log.notification_state == 'failed':
        _raise_activity(log)
        try:
            self.retry(exc=RuntimeError(log.error))
        except self.MaxRetriesExceededError:
            logger.error("car_import: gave up on stage log %s: %s", log_id, log.error)

    return {'success': log.notification_state == 'sent', 'state': log.notification_state}


def _raise_activity(log):
    """Put a failed message in front of the agent who owns the deal."""
    deal = log.deal
    user = deal.assigned_to
    if user is None:
        return
    try:
        deal.schedule_activity(
            user=user,
            summary=str(log.to_stage) if log.to_stage else 'Stage message',
            note=f"The customer was not told about this stage: {log.error}",
        )
    except Exception:  # noqa: BLE001 - never let the notifier die on the reminder
        logger.exception("car_import: could not raise an activity for stage log %s", log.pk)


# ───────────────────────────────────────────────────────────────────────────
# escalations that nobody picked up
# ───────────────────────────────────────────────────────────────────────────
#: How long a handed-over customer may sit unanswered before we chase it.
ESCALATION_SLA_KEY = 'car_import.escalation_sla_minutes'
DEFAULT_SLA_MINUTES = 30
#: How far back to look at all. Beyond this a silent thread is history, not a
#: customer waiting.
MAX_AGE_KEY = 'car_import.escalation_max_age_hours'
DEFAULT_MAX_AGE_HOURS = 48
#: Stamped onto the conversation by ka_escalate_conversation_to_staff.
ESCALATION_STAMP = 'car_import_escalated_at'


def _was_escalated(conversation):
    data = getattr(conversation, 'social_platform_data', None) or {}
    return bool(isinstance(data, dict) and data.get(ESCALATION_STAMP))


def _config_int(key, default):
    try:
        from modules.base.models import ConfigParameter
        row = ConfigParameter.objects.filter(key=key).values('value').first()
        return max(1, int(str((row or {}).get('value')).strip()))
    except Exception:
        return default


@shared_task
def chase_abandoned_escalations():
    """Find customers the assistant handed over and nobody answered.

    Escalation is one-way by design: once the assistant hands a conversation to
    a human it switches itself off and stays off. That is correct — and it means
    a conversation can sit there forever if the human never arrives. It happened
    in testing: a customer asked four more questions into silence.

    So every run looks for conversations where the AI is off, the newest message
    is the CUSTOMER's, and it has been waiting longer than the SLA — then tells
    the deal's agent, or the whole sales team when there is no deal yet.
    """
    from datetime import timedelta

    from django.utils import timezone

    from car_import.models import CarDeal

    try:
        from modules.chat.models import Conversation, Message
    except Exception:
        logger.warning('car_import: chat is not installed; escalation chase skipped')
        return {'checked': 0}

    minutes = _sla_minutes()
    max_age_hours = _config_int(MAX_AGE_KEY, DEFAULT_MAX_AGE_HOURS)
    now = timezone.now()
    cutoff = now - timedelta(minutes=minutes)
    # An UPPER bound as well as a lower one. Without it the first run matched
    # 279 of the client's imported historical conversations — every old thread
    # that happened to end with a customer message — and would have chased them
    # all. We are looking for a customer waiting NOW, not an archive.
    floor = now - timedelta(hours=max_age_hours)

    stale = []
    conversations = (Conversation.objects
                     .filter(handled_by_ai=False, type__in=('whatsapp', 'messenger',
                                                            'instagram', 'tiktok', 'webbot'))
                     .exclude(social_partner=None))
    for conversation in conversations:
        last = (Message.objects.filter(conversation=conversation)
                .order_by('-created_at').first())
        # Nobody has replied when the newest message is still the customer's.
        if last is None or last.direction != 'inbound':
            continue
        if not (floor <= last.created_at <= cutoff):
            continue
        # And it must be a conversation the assistant actually handed over.
        # `handled_by_ai=False` is also the default for every thread that never
        # had AI at all, which is most of an imported history.
        if not _was_escalated(conversation):
            continue
        waited = int((now - last.created_at).total_seconds() // 60)
        stale.append((conversation, waited))

    warned = sum(1 for conversation, waited in stale if _warn_about(conversation, waited))

    if stale:
        logger.info('car_import: %d escalated conversation(s) waiting longer than %d minutes',
                    len(stale), minutes)
    return {'checked': conversations.count(), 'waiting': len(stale),
            'warned': warned, 'sla_minutes': minutes, 'max_age_hours': max_age_hours}


def _sla_minutes():
    return _config_int(ESCALATION_SLA_KEY, DEFAULT_SLA_MINUTES)


def _warn_about(conversation, waited_minutes):
    """Tell whoever owns this customer that they are still waiting."""
    from car_import.models import CarDeal

    partner = conversation.social_partner
    deal = (CarDeal.all_objects.filter(partner=partner)
            .exclude(state='cancelled').order_by('-id').first())

    recipients = []
    if deal is not None and deal.assigned_to_id:
        recipients = [deal.assigned_to.partner_id] if getattr(deal.assigned_to, 'partner_id', None) else []
    if not recipients:
        recipients = _sales_team_partner_ids()
    if not recipients:
        return

    name = getattr(partner, 'name', '') or 'a customer'
    try:
        from modules.notifications.services.post_notification import post_notification
        # subject/body, NOT title/body: the wrong keyword made this raise on
        # every call, the except swallowed it, and the task reported success
        # while delivering nothing at all.
        post_notification(
            partner_ids=recipients,
            subject='عميل محوّل ومستني',
            body=f'{name} محوّل للفريق ومستني من {waited_minutes} دقيقة من غير رد.',
            url='/chat/?chat=%s' % conversation.pk,
            category='car_import',
        )
        return True
    except Exception:
        logger.exception('car_import: could not warn about conversation %s', conversation.pk)
        return False


def _sales_team_partner_ids():
    """Everyone in the sales groups, as partner ids."""
    try:
        from modules.base.models.user import User
        users = User.objects.filter(
            groups__technical_name__in=['car_import.sales_agent', 'car_import.sales_manager'],
            is_active=True).distinct()
        return [u.partner_id for u in users if getattr(u, 'partner_id', None)]
    except Exception:
        logger.exception('car_import: could not resolve the sales team')
        return []


@shared_task
def refresh_listing_availability():
    """Nightly: flip supplier listings that are no longer advertised.

    Quoting a car that has already sold is the client's own most common
    complaint about their current process. This is the job that catches it
    before the customer does.
    """
    from car_import.services import mobile_de

    result = mobile_de.refresh_availability()
    logger.info('car_import: listing refresh %s', result)
    return result
