# -*- coding: utf-8 -*-
"""Put a reminder in front of a person — and actually create it this time.

Two places in this module have asked for a reminder since the first release:
the stage notifier when a customer message fails, and the assistant's
`ka_schedule_followup` tool. Both called `deal.schedule_activity(...)`. No
such method exists anywhere in the platform — `ActivityMixin` provides
`activity_schedule(activity_type_id, user_id=…, date_deadline=…)`, a different
name with a different signature — and both callers swallowed the
`AttributeError`. The notifier logged it; the tool fell through to a chatter
note and reported success. **No reminder was ever created.**

This is the one place that knows the real API, so a rename in the platform
breaks one function rather than every caller silently.
"""
import logging
from datetime import datetime, time

from django.utils import timezone

logger = logging.getLogger(__name__)

#: The activity type reminders are filed under. Looked up by name because the
#: platform seeds one called "Follow Up" already; created under an Arabic name
#: only on a tenant that somehow lacks it.
ACTIVITY_TYPE_NAMES = ('Follow Up', 'متابعة عميل')


def remind(record, summary, note='', due=None, user=None):
    """Schedule an activity on `record` for `user`, due on `due`.

    Returns the Activity, or None — never raises, because a reminder that
    fails must not take the message or the conversation down with it. The
    failure goes to the log where it can be seen, which is more than the old
    code managed.
    """
    if record is None or not hasattr(record, 'activity_schedule'):
        logger.warning('car_import: %r cannot carry activities', record)
        return None

    activity_type = _activity_type()
    if activity_type is None:
        return None

    user_id = getattr(user, 'pk', None) or getattr(record, 'assigned_to_id', None)
    if not user_id:
        logger.info('car_import: no owner to remind on %s', record)
        return None

    try:
        return record.activity_schedule(
            activity_type.pk,
            user_id=user_id,
            date_deadline=_deadline(due),
            summary=str(summary or '')[:255],
            note=str(note or ''),
        )
    except Exception:
        logger.exception('car_import: could not schedule a reminder on %s', record)
        return None


def _activity_type():
    try:
        from modules.notifications.models.activity import ActivityType
    except Exception:
        logger.warning('car_import: notifications module is not installed')
        return None
    for name in ACTIVITY_TYPE_NAMES:
        row = ActivityType.objects.filter(name=name).order_by('pk').first()
        if row is not None:
            return row
    try:
        return ActivityType.objects.create(name=ACTIVITY_TYPE_NAMES[-1], category='to_do',
                                           summary='متابعة مع العميل')
    except Exception:
        logger.exception('car_import: could not create the follow-up activity type')
        return None


def _deadline(due):
    """`date_deadline` is a DateTimeField. A bare date lands at 09:00 local —
    the start of the showroom's day, so the reminder is waiting when they are."""
    if due is None:
        return None
    if isinstance(due, datetime):
        return due if timezone.is_aware(due) else timezone.make_aware(due)
    return timezone.make_aware(datetime.combine(due, time(9, 0)))
