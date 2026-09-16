# -*- coding: utf-8 -*-
"""Remove the demo rows before the company's real data goes in.

Everything created to prove the system works — the `TEST` and `تجربة —`
customers, their deals, the simulated supplier listings and call recordings —
must go before a real agent opens the pipeline, or the first thing they see is
a customer who does not exist. This is the one command that removes data, so
it is dry-run by default and refuses to run on a database whose name does not
say `test` unless told, in so many words, that production is meant.

    uv run python manage.py purge_demo_data                       # report only
    uv run python manage.py purge_demo_data --confirm
    uv run python manage.py purge_demo_data --deal KA/2026/0002 --confirm
    uv run python manage.py purge_demo_data --prefix DEMO --confirm

What counts as demo: a partner whose name starts with one of the prefixes,
every deal of such a partner, every deal named with `--deal`, and every row
stamped `is_simulated`. Contracts, documents and the message log go with their
deal (the FK cascades); quotations, approval requests, mandates, initiatives
and call recordings are removed explicitly because their FKs only null out.
A partner still referenced by something outside this module is kept and
reported, never forced.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import ProtectedError, Q

DEFAULT_PREFIXES = ['TEST', 'تجربة']


def _mgr(model):
    return getattr(model, 'all_objects', model.objects)


class Command(BaseCommand):
    help = "Delete the demo partners, deals and simulated rows (dry run unless --confirm)"

    def add_arguments(self, parser):
        parser.add_argument('--confirm', action='store_true', help="Actually delete")
        parser.add_argument('--prefix', action='append', default=[], metavar='TEXT',
                            help="A partner-name prefix that marks demo rows (repeatable). "
                                 "Default: TEST, تجربة")
        parser.add_argument('--deal', action='append', default=[], metavar='REF',
                            help="A deal reference to remove as well, e.g. KA/2026/0002 (repeatable)")
        parser.add_argument('--i-mean-production', action='store_true',
                            help="Run although the database name does not contain 'test'")

    def handle(self, *args, **options):
        from django.conf import settings
        from modules.base.models import Partner
        from car_import.models import (ApprovalRequest, CallRecording, CarDeal, ConsignmentMandate,
                                       Contract, DealDocument, Initiative, Quote, StageChangeLog,
                                       SupplierListing, Vehicle)

        db = str(settings.DATABASES['default'].get('NAME') or '')
        if 'test' not in db.lower() and not options['i_mean_production']:
            raise CommandError(
                f"Database '{db}' does not look like a test tenant. If this really is the one to "
                f"purge, say so with --i-mean-production.")

        prefixes = options['prefix'] or DEFAULT_PREFIXES
        by_name = Q()
        for prefix in prefixes:
            by_name |= Q(name__istartswith=prefix)
        partners = Partner.all_objects.filter(by_name)
        partner_ids = list(partners.values_list('id', flat=True))

        for ref in options['deal']:
            if not _mgr(CarDeal).filter(name=ref).exists():
                self.stdout.write(self.style.WARNING(f'  --deal {ref}: no such deal'))
        deals = _mgr(CarDeal).filter(Q(partner_id__in=partner_ids) | Q(name__in=options['deal']))
        deal_ids = list(deals.values_list('id', flat=True))
        vehicle_ids = list(deals.exclude(vehicle__isnull=True).values_list('vehicle_id', flat=True))

        # Explicit deletes first (their FKs only null out), then the deals (which
        # cascade to contracts, documents and the log), then what is left over.
        explicit = [
            ('approval requests', _mgr(ApprovalRequest).filter(
                Q(deal_id__in=deal_ids) | Q(partner_id__in=partner_ids))),
            ('quotations', _mgr(Quote).filter(
                Q(deal_id__in=deal_ids) | Q(partner_id__in=partner_ids))),
            ('call recordings', _mgr(CallRecording).filter(
                Q(deal_id__in=deal_ids) | Q(partner_id__in=partner_ids) | Q(is_simulated=True))),
            ('consignment mandates', _mgr(ConsignmentMandate).filter(
                Q(owner_id__in=partner_ids) | Q(buyer_id__in=partner_ids))),
            ('initiatives', _mgr(Initiative).filter(
                Q(holder_id__in=partner_ids) | Q(buyer_id__in=partner_ids))),
            ('supplier listings', _mgr(SupplierListing).filter(
                Q(deal_id__in=deal_ids) | Q(is_simulated=True))),
        ]
        cascades = [
            ('contracts', _mgr(Contract).filter(deal_id__in=deal_ids)),
            ('deal documents', _mgr(DealDocument).filter(deal_id__in=deal_ids)),
            ('stage log rows', _mgr(StageChangeLog).filter(deal_id__in=deal_ids)),
        ]

        self.stdout.write(self.style.NOTICE(
            f'\nDemo data on {db} (prefixes: {", ".join(prefixes)})'))
        self.stdout.write(f'  partners: {len(partner_ids)}  '
                          + ', '.join(partners.values_list('name', flat=True)[:6]))
        self.stdout.write(f'  deals: {len(deal_ids)}  '
                          + ', '.join(deals.values_list('name', flat=True)))
        for label, qs in explicit + cascades:
            self.stdout.write(f'  {label}: {qs.count()}')
        self.stdout.write(f'  cars (only if nothing else holds them): {len(vehicle_ids)}')

        if not options['confirm']:
            self.stdout.write(self.style.WARNING('\nDry run. Add --confirm to delete.'))
            return

        with transaction.atomic():
            for label, qs in explicit:
                n, _ = qs.delete()
                self.stdout.write(f'  deleted {label}: {n}')
            n, detail = deals.delete()
            self.stdout.write(f'  deleted deals and what cascaded: {n}  {detail}')

            kept_cars = 0
            for vehicle in _mgr(Vehicle).filter(id__in=vehicle_ids):
                try:
                    with transaction.atomic():
                        vehicle.delete()
                except ProtectedError:
                    kept_cars += 1
            self.stdout.write(f'  deleted cars: {len(vehicle_ids) - kept_cars}, '
                              f'kept (still referenced): {kept_cars}')

            try:
                from modules.crm.models import Lead
            except ImportError:
                Lead = None
            if Lead is not None:
                n, _ = _mgr(Lead).filter(partner_id__in=partner_ids).delete()
                self.stdout.write(f'  deleted leads: {n}')

            kept = []
            for partner in Partner.all_objects.filter(id__in=partner_ids):
                try:
                    with transaction.atomic():
                        partner.delete()
                except ProtectedError as exc:
                    holder = next(iter(exc.protected_objects), None)
                    label = holder._meta.label if holder is not None else 'another record'
                    kept.append(f'{partner.name} (held by {label})')
            self.stdout.write(f'  deleted partners: {len(partner_ids) - len(kept)}')
            for line in kept:
                self.stdout.write(self.style.WARNING(f'  kept, still referenced: {line}'))

        self.stdout.write(self.style.SUCCESS(
            '\nDone. Re-run without --confirm to confirm nothing is left.'))
