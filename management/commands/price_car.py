# -*- coding: utf-8 -*-
"""Price one car from the command line — and prove the engine against the sheet.

    uv run python manage.py price_car 48001
    uv run python manage.py price_car 48001 --eur1 --shipping container --port port_said
    uv run python manage.py price_car 48001 --paid 20000
    uv run python manage.py price_car --check

`--check` reproduces the two worked examples in the client's own workbook —
48,001 € in the English sheet and 30,000 € in the Arabic one — and fails loudly
if this engine disagrees with their calculator by a single cent.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Price a car with the company's calculator"

    def add_arguments(self, parser):
        parser.add_argument('gross', nargs='?', type=float, help="Price with VAT, in EUR")
        parser.add_argument('--eur1', action='store_true')
        parser.add_argument('--shipping', choices=['vip_roro', 'container'], default=None)
        parser.add_argument('--port', choices=['alexandria', 'port_said'], default='alexandria')
        parser.add_argument('--showroom', action='store_true', help="Collected from the showroom")
        parser.add_argument('--discount', type=float, default=0, help="Discount on the admin fee, EUR")
        parser.add_argument('--paid', type=float, default=None, help="What the customer actually paid")
        parser.add_argument('--fx', type=float, default=None, help="EGP per EUR, for an indicative total")
        parser.add_argument('--check', action='store_true', help="Verify against the workbook")

    def handle(self, *args, **options):
        from car_import.services import pricing

        if options['check']:
            return self._check(pricing)
        if not options['gross']:
            raise CommandError('Give a price, or use --check.')

        try:
            result = pricing.quote(
                options['gross'], eur1=options['eur1'], shipping_type=options['shipping'],
                port=options['port'], collect_from_showroom=options['showroom'],
                admin_fee_discount_eur=options['discount'], fx_rate_egp=options['fx'])
        except pricing.PricingError as exc:
            raise CommandError(str(exc))

        self.stdout.write(self.style.NOTICE(f"\nBand: {result['band']}"))
        for line in result['lines_eur']:
            self.stdout.write(f"  {line['label_ar']:<44} {line['amount']:>12,.2f} €")
        self.stdout.write(self.style.SUCCESS(
            f"  {'إجمالي سعر البيع':<44} {result['total_eur']:>12,.2f} €"))
        self.stdout.write(
            f"  {'مقدم جدية الحجز':<44} {result['deposit_eur']:>12,.2f} €"
            f"   ({result['deposit_pct']:g}%)")
        self.stdout.write(f"  {'الباقي':<44} {result['balance_eur']:>12,.2f} €")

        if result['lines_egp']:
            self.stdout.write(self.style.NOTICE('\nبالجنيه، بتتحصّل عند الوصول:'))
            for line in result['lines_egp']:
                self.stdout.write(f"  {line['label_ar']:<44} {line['amount']:>12,.2f} ج.م")

        if options['paid'] is not None:
            plan = pricing.payment_plan(result, options['paid'])
            self.stdout.write(self.style.NOTICE('\nالمدفوع:'))
            self.stdout.write(f"  paid {plan['paid_eur']:,.2f} € · deposit covered: "
                              f"{plan['deposit_covered']} · fully paid: {plan['fully_paid']}")
            self.stdout.write(f"  remaining {plan['remaining_eur']:,.2f} €"
                              + (f" · OVERPAID {plan['overpaid_eur']:,.2f} €"
                                 if plan['overpaid_eur'] else ''))

        for note in result['notes_ar']:
            self.stdout.write(f'  · {note}')

    # ------------------------------------------------------------------
    def _check(self, pricing):
        """The workbook's own two examples, to the cent."""
        # The numbers are the workbook's OWN cached results, read out of the
        # file, not re-derived by hand — sheet1!B13/B16/B19/B20 for 48,001 € and
        # sheet2!B19/B22/B25/B26 for 30,000 €, rounded to the cent.
        cases = [
            # gross, net, admin, total, deposit
            (48001, Decimal('40336.97'), Decimal('1210.11'), Decimal('46297.08'), Decimal('11574.27')),
            (30000, Decimal('25210.08'), Decimal('-750.00'), Decimal('29210.08'), Decimal('4381.51')),
        ]
        failures = 0
        for gross, net, admin, total, deposit in cases:
            got = pricing.quote(gross)
            checks = [
                ('net', got['net_eur'], net),
                ('admin', got['admin_fee_eur'], admin),
                ('total', got['total_eur'], total),
                ('deposit', got['deposit_eur'], deposit),
            ]
            bad = [(label, a, b) for label, a, b in checks if a != b]
            if bad:
                failures += 1
                self.stdout.write(self.style.ERROR(f'{gross} € — MISMATCH'))
                for label, ours, theirs in bad:
                    self.stdout.write(self.style.ERROR(
                        f'    {label}: engine {ours} vs workbook {theirs}'))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f'{gross:>7,} €  net {got["net_eur"]:>10,.2f}  admin {got["admin_fee_eur"]:>9,.2f}  '
                    f'total {got["total_eur"]:>10,.2f}  deposit {got["deposit_eur"]:>9,.2f} '
                    f'({got["deposit_pct"]:g}%)  ✓'))

        if failures:
            raise CommandError(f'{failures} case(s) disagree with the client\'s workbook.')
        self.stdout.write(self.style.SUCCESS(
            '\nThe engine matches the client\'s calculator exactly.'))
