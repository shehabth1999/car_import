# -*- coding: utf-8 -*-
"""Hand the leads nobody owns to the sales team, in turn.

The client's Odoo ran this every ten minutes; this is the same job, reading
`LeadAssignmentGroup` (models/lead_assignment.py). The rule, in the order it is
applied to one lead:

1. **Which group.** The first active group — lowest id first — that shares a
   tag with the lead. A group with no tags is a catch-all and is only tried
   after every group that has tags. The lead belongs to that one group: when
   nobody in it is free the lead WAITS, it does not fall through to the next.
2. **Whose turn.** The group's salespeople in id order, starting right after
   whoever received the last lead (`last_assigned_index`).
3. **Who is skipped.** A switched-off account, somebody who already received
   the group's daily limit from this job today, and somebody on approved time
   off today. If that leaves nobody, the lead stays unassigned for the next run.

What it never does is take a lead away from anybody. Only leads with NO
salesperson are touched, and the write itself is conditional on that still
being true — so the platform's own assignment (the agent who is alone on the
customer's chat, `crm.services.ad_lead.sole_agent_for`; a claimed conversation;
a salesperson picked by hand) always stands.
"""
import logging
from collections import defaultdict
from datetime import timedelta

from django.apps import apps
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

logger = logging.getLogger(__name__)

#: The hr.Leave states that mean the time off is granted. `validate1` is still
#: waiting for its second approval, so it is not one of them.
APPROVED_LEAVE_STATES = ('validate',)

#: `_hand_over` answers with a user id, with None (somebody else took the lead
#: first), or with this.
NOBODY_FREE = object()


# ── the rule, as plain functions ─────────────────────────────────────────────
def match_group(groups, lead_tag_ids):
    """The group a lead belongs to, or None.

    `groups` is `[(group_id, tag_ids)]` in the order they are tried. Every
    tagged group is asked before any catch-all, wherever the catch-all sits.
    """
    lead_tag_ids = set(lead_tag_ids or ())
    for group_id, tag_ids in groups:
        if tag_ids and lead_tag_ids.intersection(tag_ids):
            return group_id
    for group_id, tag_ids in groups:
        if not tag_ids:
            return group_id
    return None


def next_in_turn(member_ids, last_index, unavailable):
    """The place of the next free member after `last_index`, or None.

    The modulo also covers a pointer left beyond the end of a list that has
    since lost people.
    """
    count = len(member_ids)
    start = 0 if last_index is None else last_index + 1
    for step in range(count):
        index = (start + step) % count
        if member_ids[index] not in unavailable:
            return index
    return None


def local_day(now=None):
    """Today in the project's time zone, as `(start, end)` — end excluded."""
    local = (now or timezone.now()).astimezone(timezone.get_default_timezone())
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


# ── who is away ──────────────────────────────────────────────────────────────
def users_on_leave(user_ids, now=None):
    """Of these users, the ones on approved time off today.

    HR is a soft dependency: it is not in the manifest, and where it is not
    installed nobody is on leave. Whole days, the way HR itself counts a leave
    (local calendar days, both ends included): somebody whose time off ends
    "the 12th, 00:00" is off on the 12th, and comparing instants would hand
    them leads from one second past midnight.
    """
    user_ids = list(user_ids or ())
    if not user_ids:
        return set()
    try:
        Leave = apps.get_model('hr', 'Leave')
    except LookupError:
        return set()
    start, end = local_day(now)
    try:
        # In its own savepoint: on Postgres a failed query poisons the
        # transaction around it, and a broken leave lookup must not stop leads
        # from being handed out.
        with transaction.atomic():
            return set(Leave._base_manager
                       .filter(state__in=APPROVED_LEAVE_STATES, active=True,
                               date_from__lt=end, date_to__gte=start,
                               employee__user_id__in=user_ids)
                       .values_list('employee__user_id', flat=True))
    except Exception:
        logger.exception('car_import: time off could not be read; nobody is treated as on leave')
        return set()


# ── one run ──────────────────────────────────────────────────────────────────
def assign_new_leads(now=None):
    """One run of the job. Safe to repeat and safe to overlap; returns counts."""
    from modules.base.models.user import User
    from modules.crm.models import Lead

    now = now or timezone.now()
    result = {'assigned': 0, 'waiting': 0, 'no_group': 0}

    groups, members = _active_groups()
    if not groups:
        return result

    # Open and unowned, oldest first. `all_objects`: the default manager
    # filters by the branches of a request, and a worker has none.
    open_leads = (Lead.all_objects.filter(assigned_to__isnull=True, active=True)
                  .exclude(stage__is_closed=True))
    lead_ids = list(open_leads.order_by('created_at', 'id').values_list('id', flat=True))
    if not lead_ids:
        return result

    tags_of = defaultdict(set)
    for lead_id, tag_id in (Lead.tags.through.objects.filter(lead__in=open_leads)
                            .values_list('lead_id', 'tag_id')):
        tags_of[lead_id].add(tag_id)

    # Away for the whole run: no working account (`User.objects` leaves the
    # assistant's own accounts out), or on leave.
    everyone = {user_id for ids in members.values() for user_id in ids}
    working = set(User.objects.filter(pk__in=everyone, is_active=True).values_list('pk', flat=True))
    away = (everyone - working) | users_on_leave(working, now)

    day_start, _day_end = local_day(now)
    teams, skip = {}, set()
    for lead_id in lead_ids:
        group_id = match_group(groups, tags_of.get(lead_id))
        if group_id is None:
            result['no_group'] += 1
            continue
        if group_id in skip:
            result['waiting'] += 1
            continue
        try:
            outcome = _hand_over(lead_id, group_id, members[group_id], away, now, day_start, teams)
        except Exception:
            # One log line per group, not one per lead still waiting in it.
            logger.exception('car_import: lead %s could not be assigned; group %s is left for the next run',
                             lead_id, group_id)
            outcome = NOBODY_FREE
        if outcome is NOBODY_FREE:
            skip.add(group_id)
            result['waiting'] += 1
        elif outcome is not None:
            result['assigned'] += 1

    if result['assigned']:
        logger.info('car_import: lead assignment %s', result)
    return result


def _active_groups():
    """`([(group_id, tag_ids)], {group_id: [user ids]})`, groups in the order they are tried.

    Read through the two link tables rather than `group.tags.all()`: crm.Tag's
    own manager filters by the companies of a request, and a worker has none.
    """
    from car_import.models import LeadAssignmentGroup

    group_ids = list(LeadAssignmentGroup.objects.filter(active=True).order_by('id')
                     .values_list('id', flat=True))
    tags, members = defaultdict(set), defaultdict(list)
    if group_ids:
        for group_id, tag_id in (LeadAssignmentGroup.tags.through.objects
                                 .filter(leadassignmentgroup_id__in=group_ids)
                                 .values_list('leadassignmentgroup_id', 'tag_id')):
            tags[group_id].add(tag_id)
        # By user id: a turn order that does not move when somebody is renamed.
        for group_id, user_id in (LeadAssignmentGroup.salespeople.through.objects
                                  .filter(leadassignmentgroup_id__in=group_ids)
                                  .order_by('user_id')
                                  .values_list('leadassignmentgroup_id', 'user_id')):
            members[group_id].append(user_id)
    return ([(group_id, frozenset(tags[group_id])) for group_id in group_ids],
            {group_id: members[group_id] for group_id in group_ids})


def _hand_over(lead_id, group_id, member_ids, away, now, day_start, teams):
    """Give one lead to the group's next free salesperson — all of it or none."""
    from car_import.models import LeadAssignmentGroup, LeadAssignmentLog
    from modules.crm.models import Lead

    with transaction.atomic():
        # The row lock is what makes two overlapping runs take turns: the
        # second waits here, then reads the pointer and the day's counts the
        # first one committed.
        group = (LeadAssignmentGroup.objects.select_for_update()
                 .filter(pk=group_id, active=True).first())
        if group is None:
            return NOBODY_FREE                      # switched off or deleted since the run began

        unavailable = set(away)
        if group.daily_limit:
            counts = (LeadAssignmentLog.objects.filter(group_id=group.pk, created_at__gte=day_start)
                      .order_by().values('user_id').annotate(given=Count('id')))
            unavailable.update(row['user_id'] for row in counts if row['given'] >= group.daily_limit)

        index = next_in_turn(member_ids, group.last_assigned_index, unavailable)
        if index is None:
            return NOBODY_FREE
        user_id = member_ids[index]

        # Only while the lead STILL has nobody: a person, a claimed chat or an
        # overlapping run may have got there first, and none of them is to be
        # overruled. `.update()`, like crm's own lead_assignment — an ownership
        # change must not re-run the lead's partner sync and stage broadcast.
        values = {'assigned_to_id': user_id, 'updated_at': now}
        team_id = _team_id(user_id, teams)
        if team_id:
            values['team_id'] = team_id
        if not Lead.all_objects.filter(pk=lead_id, assigned_to__isnull=True).update(**values):
            return None

        LeadAssignmentLog.objects.create(group=group, lead_id=lead_id, user_id=user_id, created_at=now)
        LeadAssignmentGroup.objects.filter(pk=group.pk).update(last_assigned_index=index)
    return user_id


def _team_id(user_id, cache):
    """The sales team a lead carries for this salesperson.

    What `Lead.pre_save` would have set, and an `.update()` skips. A nicety:
    failing to find it must not cost the salesperson the lead.
    """
    if user_id not in cache:
        cache[user_id] = None
        try:
            from modules.base.models.user import User
            from modules.crm.models.lead import resolve_team_for_user
            with transaction.atomic():
                team = resolve_team_for_user(User.objects.filter(pk=user_id).first())
            cache[user_id] = getattr(team, 'pk', None)
        except Exception:
            logger.exception('car_import: could not resolve the sales team of user %s', user_id)
    return cache[user_id]
