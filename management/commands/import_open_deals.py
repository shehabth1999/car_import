# -*- coding: utf-8 -*-
"""Bring the company's deals-in-flight into the system, without messaging anyone.

The single most dangerous hour in this project. The company has cars at sea
right now, and every one of them has to arrive in the system at the stage it is
actually at — which means writing a stage onto a deal, which means the save
hook fires, which means the customer is told about a stage they reached three
weeks ago.

So every deal is created with **`notifications_suppressed` on**, unconditionally
and regardless of the file. The switch comes off per deal, by a human, once the
customer has been told a system is now doing this. The first real stage move
after that is then their first automatic message.

    uv run python manage.py import_open_deals --file deals.csv --dry-run
    uv run python manage.py import_open_deals --file deals.csv

Columns (only the first three are required):
    customer_name, customer_phone, stage_code,
    make, model, model_year, vin, programme, payment_state,
    vessel, bl_number, eta, arrival_port, agent_email, note
"""
import csv
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


def _date(value):
    text = str(value or '').strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


class Command(BaseCommand):
    help = "Import the open deals from a CSV, with customer messages held"

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--release-messages', action='store_true',
                            help="DANGEROUS: create them with messaging already on")

    def handle(self, *args, **options):
        from car_import.models import CarDeal, ImportStage, Vehicle
        from car_import.services import naming
        from modules.base.models import Partner
        from modules.base.models.user import User

        if options['release_messages']:
            self.stdout.write(self.style.ERROR(
                'Refusing --release-messages on an import. Import quietly, then lift the hold '
                'per deal once each customer knows. This is not a flag worth having.'))
            return

        try:
            handle = open(options['file'], encoding='utf-8-sig', newline='')
        except OSError as exc:
            raise CommandError(f"Cannot read {options['file']}: {exc}")

        stages = {s.code: s for s in ImportStage.objects.all()}
        created, skipped, problems = 0, 0, []

        with handle, transaction.atomic():
            for line_no, row in enumerate(csv.DictReader(handle), start=2):
                name = (row.get('customer_name') or '').strip()
                phone = (row.get('customer_phone') or '').strip()
                stage_code = (row.get('stage_code') or '').strip()

                if not (name and phone and stage_code):
                    problems.append((line_no, name or phone or '?',
                                     'customer_name, customer_phone and stage_code are all required'))
                    continue
                stage = stages.get(stage_code)
                if stage is None:
                    problems.append((line_no, name,
                                     f'no stage with code {stage_code!r} — see Configuration → Stages'))
                    continue

                # Match an existing contact on the subscriber digits rather than
                # the written form, or the migration creates a second copy of a
                # customer the company already has.
                partner = None
                key = naming_subscriber(phone)
                for candidate in Partner.all_objects.exclude(phone=''):
                    if naming_subscriber(candidate.phone) == key:
                        partner = candidate
                        break
                if partner is None:
                    partner = Partner.objects.create(name=name, phone=phone)

                if CarDeal.all_objects.filter(partner=partner).exclude(state='cancelled').exists():
                    skipped += 1
                    continue

                vehicle = None
                if (row.get('make') or '').strip():
                    vehicle = Vehicle.create(
                        make=row['make'].strip(),
                        model=(row.get('model') or '').strip(),
                        model_year=int(row['model_year']) if (row.get('model_year') or '').strip().isdigit() else None,
                        vin=(row.get('vin') or '').strip(),
                    )

                agent = None
                if (row.get('agent_email') or '').strip():
                    agent = User.objects.filter(email__iexact=row['agent_email'].strip()).first()

                if not options['dry_run']:
                    CarDeal.create(
                        partner=partner,
                        vehicle=vehicle,
                        assigned_to=agent,
                        program=(row.get('programme') or 'initiative').strip() or 'initiative',
                        import_stage=stage,
                        payment_state=(row.get('payment_state') or 'not_paid').strip() or 'not_paid',
                        vessel=(row.get('vessel') or '').strip(),
                        bl_number=(row.get('bl_number') or '').strip(),
                        eta=_date(row.get('eta')),
                        arrival_port=(row.get('arrival_port') or '').strip(),
                        payment_note=(row.get('note') or '').strip(),
                        # The whole point of this command.
                        notifications_suppressed=True,
                    )
                created += 1

            if options['dry_run']:
                transaction.set_rollback(True)

        self.stdout.write(f'  deals to create : {created}')
        self.stdout.write(f'  already had one : {skipped}')
        if problems:
            self.stdout.write(self.style.ERROR(f'\n{len(problems)} row(s) NOT imported:'))
            for line_no, who, why in problems:
                self.stdout.write(self.style.ERROR(f'  line {line_no}: {who} — {why}'))

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('\nDry run — nothing written.'))
            return

        self.stdout.write(self.style.SUCCESS(
            f'\n{created} deal(s) imported with customer messages HELD.'))
        self.stdout.write(
            'Next, and not before the customers know a system is doing this:\n'
            '  1. check the stages are right — the kanban is the fastest way;\n'
            '  2. lift "Hold customer messages" per deal as each customer is confirmed;\n'
            '  3. the next real stage move is then their first automatic message.')


def naming_subscriber(value):
    from car_import.services.call_matching import subscriber
    return subscriber(value)
