# -*- coding: utf-8 -*-
"""Bring the company's contact list in without creating a single duplicate.

The pipeline already holds a partner for everyone who ever messaged a
connected WhatsApp number, keyed on the canonical phone (digits, country code,
no plus — what `modules/whatsapp` writes). A spreadsheet import that ignores
that creates a second partner per customer and splits every conversation from
its deal. So the phone is the identity here: each row is normalised the way
the inbound path normalises, matched against what exists, and only then
created — or, when it exists, completed. A filled field is never overwritten.

    uv run python manage.py import_contacts --file contacts.csv --dry-run
    uv run python manage.py import_contacts --file contacts.csv
    uv run python manage.py import_contacts --file contacts.csv --region DE

Columns (name and phone are required; the rest are optional):
    name, phone, email, note

Collisions — the same phone twice in the file, or a phone that matches two
partners already — are reported and skipped, never guessed.
"""
import csv

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q


class Command(BaseCommand):
    help = "Import contacts from a CSV, deduplicated on the canonical phone"

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--region', default='EG',
                            help="Country for numbers written without a code (default EG)")

    def handle(self, *args, **options):
        from modules.base.models import Partner
        from modules.whatsapp.utils.phone import normalize_phone

        try:
            handle = open(options['file'], encoding='utf-8-sig', newline='')
        except OSError as exc:
            raise CommandError(f"Cannot read {options['file']}: {exc}")
        region = options['region']

        created, completed, unchanged, collisions, problems = [], [], [], [], []
        seen = {}

        with handle, transaction.atomic():
            for line_no, row in enumerate(csv.DictReader(handle), start=2):
                name = (row.get('name') or '').strip()
                raw_phone = (row.get('phone') or '').strip()
                email = (row.get('email') or '').strip() or None
                note = (row.get('note') or '').strip() or None
                if not (name and raw_phone):
                    problems.append((line_no, name or raw_phone or '?', 'name and phone are required'))
                    continue
                canonical = normalize_phone(raw_phone, region)
                if not canonical:
                    problems.append((line_no, name, f'phone {raw_phone!r} cannot be read as a number'))
                    continue
                if canonical in seen:
                    collisions.append((line_no, name, f'same phone as line {seen[canonical]}'))
                    continue
                seen[canonical] = line_no

                # Candidates by the last nine digits, then the exact canonical
                # form — the same two-step the inbound path uses, so an import
                # finds exactly the partner a WhatsApp message would.
                tail = canonical[-9:]
                matches = [
                    p for p in Partner.all_objects.filter(
                        Q(phone__endswith=tail) | Q(mobile__endswith=tail))
                    if canonical in (normalize_phone(p.phone, region), normalize_phone(p.mobile, region))
                ]
                if len(matches) > 1:
                    collisions.append((line_no, name, 'matches partners '
                                       + ', '.join(f'#{p.id} {p.name}' for p in matches)))
                    continue

                if matches:
                    partner = matches[0]
                    filled = []
                    if not partner.phone:
                        partner.phone = canonical
                        filled.append('phone')
                    if email and not partner.email:
                        partner.email = email
                        filled.append('email')
                    if note and not partner.comment:
                        partner.comment = note
                        filled.append('note')
                    if filled:
                        partner.save(update_fields=filled_fields(filled))
                        completed.append((line_no, f'#{partner.id} {partner.name}', ', '.join(filled)))
                    else:
                        unchanged.append((line_no, f'#{partner.id} {partner.name}'))
                    continue

                values = {'name': name, 'phone': canonical, 'email': email, 'comment': note}
                partner = Partner.create(**{k: v for k, v in values.items() if v is not None}) \
                    if hasattr(Partner, 'create') else Partner.objects.create(
                        **{k: v for k, v in values.items() if v is not None})
                created.append((line_no, f'#{partner.id} {name}', canonical))

            if options['dry_run']:
                transaction.set_rollback(True)

        self._report('created', created, self.style.SUCCESS)
        self._report('completed (blank fields filled)', completed, self.style.SUCCESS)
        self._report('already there, unchanged', unchanged, str)
        self._report('collisions — skipped', collisions, self.style.WARNING)
        self._report('problems — skipped', problems, self.style.ERROR)
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('\nDry run — nothing was written.'))


    def _report(self, label, rows, style):
        self.stdout.write(style(f'\n{label}: {len(rows)}'))
        for row in rows[:40]:
            self.stdout.write('  line %s: %s' % (row[0], '  '.join(str(x) for x in row[1:])))
        if len(rows) > 40:
            self.stdout.write(f'  … and {len(rows) - 40} more')


def filled_fields(filled):
    """Map the report labels back onto the columns that were written."""
    return [{'note': 'comment'}.get(name, name) for name in filled]
