# -*- coding: utf-8 -*-
"""Import call recordings from Dropbox (or the simulator).

    uv run python manage.py sync_dropbox_calls
    uv run python manage.py sync_dropbox_calls --status
    uv run python manage.py sync_dropbox_calls --reset-cursor

Prints which backend answered, every time. A simulated call that reads like a
real one is how a fake summary ends up on a customer's deal.
"""
from django.core.management.base import BaseCommand

from car_import.services import dropbox_sync


class Command(BaseCommand):
    help = "Pull new call recordings from Dropbox and match them to customers"

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=None)
        parser.add_argument('--reset-cursor', action='store_true',
                            help="Read the whole folder again (imports are deduplicated anyway)")
        parser.add_argument('--status', action='store_true')

    def handle(self, *args, **options):
        live = dropbox_sync.is_live()
        self.stdout.write(self.style.NOTICE(
            f"Backend: {'Dropbox (LIVE)' if live else 'the SIMULATOR (no credentials)'}"))

        if options['status']:
            for label, key in (('app key', dropbox_sync.APP_KEY),
                               ('app secret', dropbox_sync.APP_SECRET),
                               ('refresh token', dropbox_sync.REFRESH_TOKEN),
                               ('folder', dropbox_sync.FOLDER_KEY),
                               ('cursor', dropbox_sync.CURSOR_KEY)):
                value = dropbox_sync._config(key)
                shown = 'set' if value and 'token' in label or 'secret' in label else (value or '—')
                self.stdout.write(f'  {label:<15} {shown if value else "not set"}   ({key})')
            if not live:
                self.stdout.write(self.style.WARNING(
                    '  Running simulated. Set the three credentials to go live — no code change.'))
            return

        result = dropbox_sync.sync_calls(limit=options['limit'],
                                         reset_cursor=options['reset_cursor'])
        self.stdout.write(
            f"  seen {result['seen']} · imported {result['imported']} · "
            f"already had {result['already_had']} · needs review {result['needs_review']}")
        if result['needs_review']:
            self.stdout.write(self.style.WARNING(
                f"  {result['needs_review']} recording(s) could not be matched to one customer — "
                f"they are on the review list, not guessed."))
        if result['simulated'] and result['imported']:
            self.stdout.write(self.style.WARNING(
                '  These rows are marked is_simulated. Never send one to a customer.'))
