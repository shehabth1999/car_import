# -*- coding: utf-8 -*-
"""Search mobile.de (or the simulator) and optionally store what came back.

    uv run python manage.py search_mobile_de --make Mercedes-Benz --model C200
    uv run python manage.py search_mobile_de --make Mercedes-Benz --max-price 50000 --import
    uv run python manage.py search_mobile_de --status

Through Apify, without flipping the switch for everybody else:

    uv run python manage.py search_mobile_de --backend apify --make BMW --model X1 --size 10 --raw /tmp/x1.json
    uv run python manage.py search_mobile_de --backend apify --url "https://suchen.mobile.de/fahrzeuge/details.html?id=…"

It prints which backend answered, every time. A simulated result that reads
like a real one is how a fake car ends up in a customer's quote.
"""
import json

from django.core.management.base import BaseCommand

from car_import.services import apify, mobile_de

BACKEND_LABEL = {
    'official': 'mobile.de (LIVE — the official Search API)',
    'apify': f'mobile.de through Apify ({mobile_de.APIFY_ACTOR})',
    'simulator': 'the SIMULATOR (fake cars)',
}


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
        parser.add_argument('--backend', choices=['auto', 'apify', 'official', 'simulator'], default='auto',
                            help="Use this backend for this run only (default: what the switch says)")
        parser.add_argument('--url', default=None,
                            help="Read ONE advert from its mobile.de link instead of searching")
        parser.add_argument('--raw', default=None,
                            help="Also write the backend's untouched answer to this file, as JSON")

    def handle(self, *args, **options):
        force = None if options['backend'] == 'auto' else options['backend']

        if options['status']:
            return self._status()

        try:
            backend = mobile_de.get_backend(force)
        except mobile_de.MobileDeError as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            return
        self.stdout.write(self.style.NOTICE(f'Backend: {BACKEND_LABEL[backend.name]}'))

        try:
            if options['url']:
                listings = self._one_advert(backend, options['url'])
                total = len(listings)
            else:
                listings, meta = mobile_de.search(
                    backend=force,
                    make=options['make'], model=options['model'],
                    price_min=options['min_price'], price_max=options['max_price'],
                    year_min=options['min_year'], year_max=options['max_year'],
                    mileage_max=options['max_mileage'],
                    fuel=options['fuel'], gearbox=options['gearbox'],
                    country=options['country'],
                    vatable=not options['any_vat'],
                    page_number=options['page'], page_size=options['size'],
                )
                total = meta['total']
        except mobile_de.MobileDeError as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            return

        self.stdout.write(f"{len(listings)} of {total} result(s), page {options['page']}\n")
        for row in listings:
            self.stdout.write(self._line(row, backend))

        if options['raw']:
            with open(options['raw'], 'w', encoding='utf-8') as handle:
                json.dump([row.get('raw') for row in listings], handle, ensure_ascii=False, indent=1)
            self.stdout.write(f"\nRaw answer written to {options['raw']}")

        if backend.name == 'apify':
            self.stdout.write(f"Apify results used today: {apify.used_today()} of {apify.daily_cap()}")

        if options['do_import']:
            deal = None
            if options['deal']:
                from car_import.models import CarDeal
                deal = CarDeal.all_objects.filter(pk=options['deal']).first()
            created, updated = mobile_de.import_listings(listings, deal=deal)
            self.stdout.write(self.style.SUCCESS(
                f"\nImported: {len(created)} new, {len(updated)} updated."))
            if backend.simulated:
                self.stdout.write(self.style.WARNING(
                    "These rows are marked is_simulated. Never quote them to a customer."))

    def _one_advert(self, backend, link):
        ad_id = mobile_de.ad_id_from_link(link)
        if not ad_id:
            raise mobile_de.MobileDeError('That is not a mobile.de advert link')
        ad = backend.ad(ad_id)
        if not ad:
            self.stdout.write(self.style.WARNING(f'Nothing came back for advert {ad_id}.'))
            return []
        return [mobile_de._normalised(backend, ad)]

    def _line(self, row, backend):
        price = row.get('price_gross_eur')
        if row.get('vatable'):
            vat = '  VAT-deductible'
            if price:
                vat += f"  (net ≈ {round(float(price) / 1.19):,} €)"
        else:
            vat = '  no VAT reclaim'
        return (f"  {row['ad_id']}  {row.get('make','')} {row.get('model','')} "
                f"{row.get('version','')} {row.get('model_year','')}  "
                f"{row.get('mileage_km','?')} km  {price} €{vat}")

    def _status(self):
        try:
            backend = mobile_de.get_backend()
            self.stdout.write(self.style.NOTICE(f'Backend: {BACKEND_LABEL[backend.name]}'))
        except mobile_de.MobileDeError as exc:
            self.stdout.write(self.style.ERROR(str(exc)))
        user, _password = mobile_de.credentials()
        self.stdout.write(f"  switch {mobile_de.BACKEND_KEY}: {mobile_de.backend_choice()}")
        self.stdout.write("  official Search API:")
        self.stdout.write(f"    username configured: {'yes' if user else 'no'}")
        self.stdout.write(f"    config keys: {mobile_de.USERNAME_KEY} / {mobile_de.PASSWORD_KEY}")
        self.stdout.write(f"    force simulation: {mobile_de.FORCE_SIMULATION_KEY}")
        self.stdout.write("  Apify:")
        # Whether it is there, never what it is.
        self.stdout.write(f"    {apify.TOKEN_ENV} in the environment: {'yes' if apify.is_configured() else 'no'}")
        self.stdout.write(f"    actor: {mobile_de.APIFY_ACTOR}")
        self.stdout.write(f"    results used today: {apify.used_today()} of {apify.daily_cap()} "
                          f"({apify.DAILY_CAP_KEY})")
        if not mobile_de.is_live() and mobile_de.backend_choice() != 'apify':
            self.stdout.write(self.style.WARNING(
                "  Running simulated. To read real adverts: put the token in the environment and set "
                f"{mobile_de.BACKEND_KEY} to apify — or set the two official config parameters."))
