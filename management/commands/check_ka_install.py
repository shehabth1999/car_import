# -*- coding: utf-8 -*-
"""
Deployment guard.

This project keeps accounting out on purpose. `sales` depends on `account`,
`payment` and `products`, and installing it auto-installs `sales_account`,
`crm_sales` and `whatsapp_sales`, which put invoice, payment and quotation
buttons back on the screens (doc 16 §2).

`appointment` is on the list because it depends on `sales` — installing it
quietly brings the whole chain back.

Run it as step 7 of every release. A non-zero exit fails the deploy.
"""
from django.core.management.base import BaseCommand

FORBIDDEN = [
    'sales', 'account', 'payment', 'products',
    'sales_account', 'crm_sales', 'whatsapp_sales',
    'appointment', 'stock', 'purchase', 'pos',
]

#: The four that must never be installed — the rest are warnings.
HARD_BLOCK = {'sales', 'account', 'payment', 'products'}


class Command(BaseCommand):
    help = "Fail if a module this project deliberately excludes is installed"

    def add_arguments(self, parser):
        parser.add_argument('--strict', action='store_true',
                            help="Treat every module on the list as a failure, not only the four hard blocks")

    def handle(self, *args, **options):
        from modules.base.models import Module

        installed = set(
            Module.objects
            .filter(technical_name__in=FORBIDDEN, state='installed')
            .values_list('technical_name', flat=True)
        )

        if not installed:
            self.stdout.write(self.style.SUCCESS(
                "car_import: clean — none of the excluded modules is installed."
            ))
            return

        blocking = installed & HARD_BLOCK if not options['strict'] else installed
        warning = installed - blocking

        for name in sorted(warning):
            self.stdout.write(self.style.WARNING(
                f"car_import: '{name}' is installed. It is not in this project's scope "
                f"and may put buttons back on the CRM and deal screens."
            ))

        if blocking:
            names = ', '.join(sorted(blocking))
            self.stdout.write(self.style.ERROR(
                f"car_import: {names} installed — accounting is out of scope for this project.\n"
                f"The deal is its own model (car_import.CarDeal) and needs none of them. "
                f"Uninstall them, or ask the project owner before deploying."
            ))
            raise SystemExit(1)
