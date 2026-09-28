# -*- coding: utf-8 -*-
"""Point leads at the car catalogue, and report anything still unlinked.

    uv run python manage.py link_car_catalogue            # link
    uv run python manage.py link_car_catalogue --dry-run  # only say what it would do

Run after `sync_schema` has added the lead's brand/model columns. Migration
0022 links everything car_import owns; a lead belongs to the CRM, so its
columns arrive through sync_schema and its link through here. Re-running is
safe: a lead that already points at a model is left alone.

A lead's words are read, never added to the catalogue: "عايز مرسيدس" finds
Mercedes; a spelling that matches nothing keeps its text and no relation.
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Link leads' wanted car to the car catalogue and report unlinked rows"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        from car_import.models import CarBrand, CarModel, CustomsValuation, DepositTier, ModelPriceRange, \
            SupplierListing, Vehicle, WebsiteCar
        from car_import.services import catalogue
        from modules.crm.models import Lead

        linked, unmatched = 0, []
        with transaction.atomic():
            leads = (Lead._base_manager.exclude(ka_model_wanted__isnull=True).exclude(ka_model_wanted='')
                     .filter(ka_car_model_wanted__isnull=True))
            for lead in leads:
                brand, car_model = catalogue.parse(lead.ka_model_wanted)
                if brand is None and lead.ka_brand_wanted_id is None:
                    unmatched.append(f'lead {lead.pk}: {lead.ka_model_wanted}')
                    continue
                values = {}
                if brand is not None and lead.ka_brand_wanted_id is None:
                    values['ka_brand_wanted'] = brand
                if car_model is not None:
                    values['ka_car_model_wanted'] = car_model
                if values:
                    Lead._base_manager.filter(pk=lead.pk).update(**values)
                    linked += 1
                    self.stdout.write(f'  lead {lead.pk}: "{lead.ka_model_wanted}" → '
                                      f'{car_model or brand}')
            if options['dry_run']:
                transaction.set_rollback(True)

        self.stdout.write(f'Leads linked: {linked}')
        for line in unmatched:
            self.stdout.write(self.style.WARNING(f'  no brand in the words — {line}'))

        gaps = {
            'cars without a brand': Vehicle._base_manager.filter(brand__isnull=True).count(),
            'adverts without a brand': SupplierListing._base_manager.filter(brand__isnull=True).count(),
            'website cars without a brand': WebsiteCar._base_manager.filter(brand__isnull=True).count(),
            'deposit rows without a model': DepositTier._base_manager.filter(car_model__isnull=True).count(),
            'customs rows without a model': CustomsValuation._base_manager.filter(car_model__isnull=True).count(),
            'price ranges without a model': ModelPriceRange._base_manager.filter(car_model__isnull=True).count(),
        }
        self.stdout.write(f'Catalogue: {CarBrand.objects.count()} brands, {CarModel.objects.count()} models '
                          f'({CarModel.objects.filter(website_id__isnull=True).count()} not on the website)')
        for label, count in gaps.items():
            style = self.style.WARNING if count else self.style.SUCCESS
            self.stdout.write(style(f'  {label}: {count}'))
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('Dry run — nothing written.'))
