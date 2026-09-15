# -*- coding: utf-8 -*-
"""Search mobile.de (or the simulator) and optionally store what came back.

    uv run python manage.py search_mobile_de --make Mercedes-Benz --model C200
    uv run python manage.py search_mobile_de --make Mercedes-Benz --max-price 50000 --import
    uv run python manage.py search_mobile_de --status

It prints which backend answered, every time. A simulated result that reads
like a real one is how a fake car ends up in a customer's quote.
"""
from django.core.management.base import BaseCommand

from car_import.services import mobile_de


class Command(BaseCommand):
    help = "Search mobile.de for cars (falls back to the built-in simulator)"

    def add_arguments(self, parser):
        parser.add_argument('--make', default=None)
        parser.add_argument('--model', default=None)
        parser.add_argument('--min-price', type=int, default=None)
        parser.add_argument('--max-price', type=int, default=None)
        parser.add_argument('--min-year', type=int, default=None)
        parser.add_argument('--max-year', type=int, default=None)
        parser.add_argument('--max-mileage', type=int, default=None)
        parser.add_argument('--fuel', default=None)
        parser.add_argument('--gearbox', default=None)
        parser.add_argument('--country', default=None)
        parser.add_argument('--any-vat', action='store_true',
                            help="Include cars whose VAT is NOT reclaimable (default: only vatable)")
        parser.add_argument('--page', type=int, default=1)
        parser.add_argument('--size', type=int, default=20)
        parser.add_argument('--import', dest='do_import', action='store_true',
                            help="Write the results into SupplierListing")
        parser.add_argument('--deal', type=int, default=None,
                            help="Attach the imported listings to this deal id")
        parser.add_argument('--status', action='store_true',
                            help="Only report which backend would answer")

    def handle(self, *args, **options):
        live = mobile_de.is_live()
        source = 'mobile.de (LIVE)' if live else 'the SIMULATOR (no credentials)'
        self.stdout.write(self.style.NOTICE(f'Backend: {source}'))

        if options['status']:
            user, _password = mobile_de.credentials()
            self.stdout.write(f"  username configured: {'yes' if user else 'no'}")
            self.stdout.write(f"  config keys: {mobile_de.USERNAME_KEY} / {mobile_de.PASSWORD_KEY}")
            self.stdout.write(f"  force simulation: {mobile_de.FORCE_SIMULATION_KEY}")
            if not live:
                self.stdout.write(self.style.WARNING(
                    "  Running simulated. Set the two config parameters to go live — "
                    "no code change is needed."))
            return

        listings, meta = mobile_de.search(
            make=options['make'], model=options['model'],
            price_min=options['min_price'], price_max=options['max_price'],
            year_min=options['min_year'], year_max=options['max_year'],
            mileage_max=options['max_mileage'],
            fuel=options['fuel'], gearbox=options['gearbox'],
            country=options['country'],
            vatable=not options['any_vat'],
            page_number=options['page'], page_size=options['size'],
        )

        self.stdout.write(f"{len(listings)} of {meta['total']} result(s), page {meta['page']}\n")
        for row in listings:
            net = ''
            price = row.get('price_gross_eur')
            if price and row.get('vatable'):
                net = f"  (net ≈ {round(float(price) / 1.19):,} €)"
            self.stdout.write(
                f"  {row['ad_id']}  {row.get('make','')} {row.get('model','')} "
                f"{row.get('version','')} {row.get('model_year','')}  "
                f"{row.get('mileage_km','?')} km  {price} €"
                f"{'  VAT-deductible' if row.get('vatable') else '  no VAT reclaim'}{net}"
            )

        if options['do_import']:
            deal = None
            if options['deal']:
                from car_import.models import CarDeal
                deal = CarDeal.all_objects.filter(pk=options['deal']).first()
            created, updated = mobile_de.import_listings(listings, deal=deal)
            self.stdout.write(self.style.SUCCESS(
                f"\nImported: {len(created)} new, {len(updated)} updated."))
            if meta['simulated']:
                self.stdout.write(self.style.WARNING(
                    "These rows are marked is_simulated. Never quote them to a customer."))
