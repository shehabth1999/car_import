# -*- coding: utf-8 -*-
"""The tracking feed for the company's website — our half of the tracking page.

An extension cannot publish a public URL, and a customer's shipping status
must not sit behind the ERP's login. So the feed is a JSON file written to a
private path on the host, one entry per open deal keyed by the deal's secret
`public_token`; the website (Ahmed Saeed's side) pulls it over SSH/rsync and
serves `/track/<token>`. Nothing personal is in it — no name, no phone — only
what the customer already knows about their own car.

    uv run python manage.py export_tracking_feed
    uv run python manage.py export_tracking_feed --print
    uv run python manage.py export_tracking_feed --path /srv/genie/khaled_test/private/tracking.json

Runs nightly from beat; a stage move does not wait for it — the deal's
`public_status` is what the customer reads, and it changes on the stage move.
"""
import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

DEFAULT_RELATIVE = os.path.join('private', 'car_import', 'tracking.json')


def feed_path():
    from modules.base.models import ConfigParameter
    configured = (ConfigParameter.objects.filter(key='car_import.tracking_feed_path')
                  .values_list('value', flat=True).first() or '').strip()
    return configured or os.path.join(str(settings.BASE_DIR), DEFAULT_RELATIVE)


def build_feed():
    from car_import.models import CarDeal
    from car_import.services.tracking import ensure_token

    entries = {}
    for deal in (CarDeal.all_objects.filter(state__in=['open', 'on_hold'])
                 .select_related('import_stage', 'vehicle').order_by('id')):
        token = ensure_token(deal)
        stage = deal.import_stage
        entries[token] = {
            'reference': deal.name,
            'status': deal.public_status or (getattr(stage, 'name', '') or ''),
            'stage_code': getattr(stage, 'code', '') or '',
            'stage_sequence': getattr(stage, 'sequence', None),
            'car': str(deal.vehicle) if deal.vehicle_id else '',
            'eta': deal.eta.isoformat() if deal.eta else None,
            'port': deal.arrival_port or '',
            'vessel': deal.vessel or '',
            'on_hold': deal.state == 'on_hold',
            'updated_at': (deal.stage_entered_at or deal.updated_at or timezone.now()).isoformat(),
        }
    return {'generated_at': timezone.now().isoformat(), 'deals': entries}


class Command(BaseCommand):
    help = "Write the customer tracking feed (JSON keyed by public token) to the private path"

    def add_arguments(self, parser):
        parser.add_argument('--path', default=None)
        parser.add_argument('--print', action='store_true', dest='show')

    def handle(self, *args, **options):
        data = build_feed()
        if options['show']:
            self.stdout.write(json.dumps(data, ensure_ascii=False, indent=2))
            return
        path = options['path'] or feed_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as handle:
            json.dump(data, handle, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
        try:
            os.chmod(path, 0o640)
        except OSError:
            pass
        self.stdout.write(self.style.SUCCESS(f'{len(data["deals"])} deal(s) → {path}'))
