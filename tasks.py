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
    # `services.reminders.remind`, which calls the API that exists. The old
    # `deal.schedule_activity(...)` did not, and the except below turned every
    # failed customer message into a log line nobody was reminded about.
    from car_import.services import reminders
    reminders.remind(
        deal,
        summary=str(log.to_stage) if log.to_stage else 'Stage message',
        note=f"العميل ما اتبلغش بالمرحلة دي: {log.error}",
        user=user,
    )


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
def export_tracking_feed():
    """Nightly: the website's tracking feed, one JSON entry per open deal."""
    from django.core.management import call_command
    call_command('export_tracking_feed')


@shared_task
def judge_recent_replies():
    """Daily: the judge model reads a sample of yesterday's replies."""
    from car_import.services import reply_judge
    return reply_judge.run(hours=24, limit=30)


@shared_task
def rebuild_ka_knowledge():
    """Re-index the approved answers — a fee, a plan or a switch just changed."""
    from django.core.management import call_command
    try:
        call_command('build_ka_knowledge')
    except Exception:
        logger.exception('car_import: the knowledge base could not be rebuilt')


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

    # Under the selling policy staff monitor; they are not on the queue. A
    # hand-over nobody answers goes back to the assistant, which then answers
    # what the customer already wrote (services/resume.py says what never does).
    resumed = 0
    try:
        from car_import.services import policy, resume
        if policy.ai_first():
            limit = resume.resume_after_minutes()
            still_waiting = []
            for conversation, waited in stale:
                # Minutes, not hours: someone who gave up this afternoon should
                # hear from a person, not from a bot that woke up at night.
                if limit <= waited <= resume.MAX_WAIT_MINUTES and resume.may_resume(conversation):
                    resume.give_back_to_ai(conversation, waited_minutes=waited)
                    resumed += 1
                else:
                    still_waiting.append((conversation, waited))
            stale = still_waiting
    except Exception:
        logger.exception('car_import: could not give abandoned conversations back to the assistant')

    warned = sum(1 for conversation, waited in stale if _warn_about(conversation, waited))

    if stale:
        logger.info('car_import: %d escalated conversation(s) waiting longer than %d minutes',
                    len(stale), minutes)
    return {'checked': conversations.count(), 'waiting': len(stale),
            'warned': warned, 'given_back_to_ai': resumed, 'sla_minutes': minutes, 'max_age_hours': max_age_hours}


def _sla_minutes():
    return _config_int(ESCALATION_SLA_KEY, DEFAULT_SLA_MINUTES)


def _warn_about(conversation, waited_minutes):
    """Tell whoever owns this customer that they are still waiting."""
    partner = conversation.social_partner
    owners = _owner_users_for_partner(partner)
    if not owners:
        return False

    name = getattr(partner, 'name', '') or 'أحد العملاء'
    body = (f'{name} محوّل للفريق ومستني من {waited_minutes} دقيقة من غير رد.\n'
            'محتاج حد يكمّل معاه من هنا.')
    try:
        # The warning goes IN the conversation as well as to the bell. The
        # client's point: a notification tells you somebody needs you and then
        # sends you off to find out why; a note says it where the reply will be
        # typed, and is still there for whoever opens the thread tomorrow.
        from car_import.services import internal_note
        return internal_note.post(conversation, body, recipients=owners,
                                  subject='عميل محوّل ومستني')
    except Exception:
        logger.exception('car_import: could not warn about conversation %s', conversation.pk)
        return False


def _owner_users_for_partner(partner):
    """The USERS who own this customer: their agent, else the sales team.

    Users, not partner ids, because an @mention addresses a user while a
    notification addresses a partner — and the two callers need both. Resolving
    once and deriving the ids keeps the escalation path and the chaser answering
    the same question the same way; a second copy of "who owns this customer?"
    is a second place for it to go stale.
    """
    from car_import.models import CarDeal

    if partner is None:
        return _sales_team_users()
    deal = (CarDeal.all_objects.filter(partner=partner)
            .exclude(state='cancelled').order_by('-id').first())
    if deal is not None and deal.assigned_to_id:
        return [deal.assigned_to]
    return _sales_team_users()


def _recipients_for_partner(partner):
    """The same answer as partner ids, for the notification path."""
    return [u.partner_id for u in _owner_users_for_partner(partner)
            if getattr(u, 'partner_id', None)]


#: Who to tell, best first. The last entry is the point: on a tenant where
#: nobody has been put into the car_import groups yet — which is exactly how
#: khaled_test was found — every earlier step resolves to nobody and the
#: warning evaporates. A warning that reaches nobody is not a warning.
ESCALATION_AUDIENCE = [
    ['car_import.sales_agent', 'car_import.sales_manager'],
    ['car_import.management', 'car_import.operations'],
    ['base.owner'],
]


def _users_in_groups(groups):
    """Active users in any of these groups. Empty is a real answer."""
    try:
        from modules.base.models.user import User
        return list(User.objects.filter(groups__technical_name__in=groups,
                                        is_active=True).distinct())
    except Exception:
        logger.exception('car_import: could not resolve %s', groups)
        return []


def _sales_team_users():
    """The first group in the chain that actually has somebody in it."""
    try:
        from modules.base.models.user import User
    except Exception:
        logger.exception('car_import: could not load the user model')
        return []

    for index, groups in enumerate(ESCALATION_AUDIENCE):
        try:
            users = list(User.objects.filter(groups__technical_name__in=groups,
                                             is_active=True).distinct())
        except Exception:
            logger.exception('car_import: could not resolve %s', groups)
            continue
        if users:
            if index:
                logger.warning(
                    'car_import: nobody is in %s, so an escalation warning fell back to %s. '
                    'Put the sales team into the car_import groups.',
                    ESCALATION_AUDIENCE[index - 1], groups)
            return users

    logger.error('car_import: an escalated customer is waiting and there is NOBODY to tell — '
                 'no user belongs to any car_import group or to base.owner.')
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


@shared_task
def sync_dropbox_calls():
    """Nightly: pull new call recordings and match them.

    A scheduled poll with the stored cursor covers whatever a missed webhook
    dropped — which is the failure mode webhooks actually have.
    """
    from car_import.services import dropbox_sync

    result = dropbox_sync.sync_calls()
    logger.info('car_import: dropbox sync %s', result)
    return result
