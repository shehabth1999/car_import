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
