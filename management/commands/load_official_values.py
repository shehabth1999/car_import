# -*- coding: utf-8 -*-
"""Load the owner's values workbook into the deposit, customs and price tables.

    uv run python manage.py load_official_values --file /path/to/official_values.csv
    uv run python manage.py load_official_values --file … --dry-run

The file is NOT shipped with the module. It is the client's commercial data and
it stays out of the repository; put it on the server when you load it and
remove it afterwards.

**Rows that fail a sanity check are rejected and reported, never guessed.** The
workbook has been wrong before — an earlier extraction had a full tier priced
below its medium tier, and a 34,076 that had become 24,076. A loader that
silently accepts those turns a typo into a quote.
"""
import csv
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

CONFIRMED = date(2026, 9, 15)
SOURCE = "official values workbook 2026-09"


def _decimal(value):
    """'12,345' / '12٬345' / '' → a number or None."""
    text = str(value or '').strip().replace(',', '').replace('،', '').replace('٬', '')
    text = text.replace('٫', '.').replace(' ', '')
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _int(value):
    number = _decimal(value)
    return int(number) if number is not None else None


class Command(BaseCommand):
    help = "Load the official values workbook (CSV) into DepositTier, CustomsValuation and ModelPriceRange"

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help="Path to the CSV export of the workbook")
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        from car_import.models import CustomsValuation, DepositTier, ModelPriceRange

        path = options['file']
        dry = options['dry_run']
        try:
            # utf-8-sig: the export carries a BOM, and without this the first
            # column arrives as '﻿make' and every row silently misses.
            handle = open(path, encoding='utf-8-sig', newline='')
        except OSError as exc:
            raise CommandError(f'Cannot read {path}: {exc}')

        deposits = customs = ranges = 0
        rejected = []

        with handle, transaction.atomic():
            for line_no, row in enumerate(csv.DictReader(handle), start=2):
                make = (row.get('make') or '').strip()
                model = (row.get('model') or '').strip()
                year = _int(row.get('model_year'))
                if not (make and model and year):
                    rejected.append((line_no, f'{make} {model}', 'missing make, model or year'))
                    continue

                full_eu = _decimal(row.get('deposit_full_europe_usd'))
                full_out = _decimal(row.get('deposit_full_outside_usd'))
                med_eu = _decimal(row.get('deposit_medium_europe_usd'))
                med_out = _decimal(row.get('deposit_medium_outside_usd'))

                # Sanity: the full tier is never cheaper than the medium one.
                # This is exactly the error that got through last time.
                for tier_full, tier_med, region in ((full_eu, med_eu, 'europe'),
                                                    (full_out, med_out, 'outside')):
                    if tier_full is not None and tier_med is not None and tier_full < tier_med:
                        rejected.append((line_no, f'{make} {model} {year}',
                                         f'full tier ({tier_full}) below medium ({tier_med}) '
                                         f'for {region} — columns look swapped'))

                bad_line = any(r[0] == line_no for r in rejected)
                if bad_line:
                    continue

                for value, tier, region in ((full_eu, 'full', 'europe'),
                                            (full_out, 'full', 'outside'),
                                            (med_eu, 'medium', 'europe'),
                                            (med_out, 'medium', 'outside')):
                    if value is None:
                        continue
                    if not dry:
                        DepositTier.objects.update_or_create(
                            make=make, model=model, model_year=year, tier=tier, region=region,
                            defaults={'deposit_usd': value, 'effective_from': CONFIRMED,
                                      'source_note': SOURCE})
                    deposits += 1

                customs_value = _decimal(row.get('customs_2026_eur'))
                if customs_value is not None:
                    if not dry:
                        CustomsValuation.objects.update_or_create(
                            make=make, model=model, model_year=year,
                            defaults={'value_eur': customs_value, 'basis': 'unknown',
                                      'effective_from': CONFIRMED, 'source_note': SOURCE})
                    customs += 1

                price_from = _decimal(row.get('avg_price_from_eur'))
                price_to = _decimal(row.get('avg_price_to_eur'))
                if price_from is not None or price_to is not None:
                    if price_from is not None and price_to is not None and price_from > price_to:
                        rejected.append((line_no, f'{make} {model} {year}',
                                         f'price range reversed ({price_from} → {price_to})'))
                        continue
                    if not dry:
                        ModelPriceRange.objects.update_or_create(
                            make=make, model=model, model_year=year,
                            defaults={'price_from_eur': price_from, 'price_to_eur': price_to,
                                      'egypt_price_egp': _decimal(row.get('egypt_price_egp')),
                                      'hp': _int(row.get('hp')),
                                      'cc_rounded': _int(row.get('cc_rounded')),
                                      'fuel': (row.get('fuel') or '').strip(),
                                      'effective_from': CONFIRMED, 'source_note': SOURCE})
                    ranges += 1

            if dry:
                transaction.set_rollback(True)

        self.stdout.write(f'  deposit values : {deposits}')
        self.stdout.write(f'  customs values : {customs}')
        self.stdout.write(f'  price ranges   : {ranges}')

        if rejected:
            self.stdout.write(self.style.ERROR(f'\n{len(rejected)} row(s) REJECTED, not loaded:'))
            for line_no, what, why in rejected:
                self.stdout.write(self.style.ERROR(f'  line {line_no}: {what} — {why}'))
            self.stdout.write('Fix them in the workbook and re-run; nothing was guessed.')
        else:
            self.stdout.write(self.style.SUCCESS('\nNo rows failed the sanity checks.'))

        if dry:
            self.stdout.write(self.style.WARNING('Dry run — nothing written.'))
