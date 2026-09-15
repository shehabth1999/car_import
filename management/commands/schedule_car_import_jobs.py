# -*- coding: utf-8 -*-
"""Register this module's recurring jobs with Celery beat.

    uv run python manage.py schedule_car_import_jobs
    uv run python manage.py schedule_car_import_jobs --off

Two jobs:

* **chase_abandoned_escalations**, every 15 minutes — a customer the assistant
  handed to a human and nobody answered. Escalation is one-way by design, so
  without this a conversation can wait forever; it did in testing.
* **refresh_listing_availability**, nightly — flips a supplier listing to "gone"
  when the advert disappears, so an agent finds out before the customer does.

Beat reads its schedule from the database, but the running process only notices
a new row when `PeriodicTasks` is bumped — historical models in a migration do
not fire that signal, which is why this is a command and not a data migration.
"""
from django.core.management.base import BaseCommand

SCHEDULES = [
    {
        'name': 'car_import: chase abandoned escalations',
        'task': 'car_import.tasks.chase_abandoned_escalations',
        'every': 15, 'period': 'minutes',
    },
    {
        'name': 'car_import: refresh supplier listing availability',
        'task': 'car_import.tasks.refresh_listing_availability',
        'every': 1, 'period': 'days',
    },
]


class Command(BaseCommand):
    help = "Create or remove car_import's periodic tasks"

    def add_arguments(self, parser):
        parser.add_argument('--off', action='store_true', help="Disable them instead")

    def handle(self, *args, **options):
        from django_celery_beat.models import IntervalSchedule, PeriodicTask, PeriodicTasks

        for spec in SCHEDULES:
            interval, _ = IntervalSchedule.objects.get_or_create(
                every=spec['every'],
                period=getattr(IntervalSchedule, spec['period'].upper()))
            task, created = PeriodicTask.objects.update_or_create(
                name=spec['name'],
                defaults={'task': spec['task'], 'interval': interval,
                          'enabled': not options['off']})
            state = 'disabled' if options['off'] else ('created' if created else 'updated')
            self.stdout.write(f"  {spec['name']}: {state} "
                              f"(every {spec['every']} {spec['period']})")

        # Without this the running beat process keeps its old schedule until it
        # restarts, and the job looks registered while never firing.
        PeriodicTasks.update_changed()
        self.stdout.write(self.style.SUCCESS('\nBeat notified; the new schedule is live.'))
