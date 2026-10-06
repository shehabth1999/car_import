# -*- coding: utf-8 -*-
"""Load the client's Odoo pick-lists — the "Link Tracker" menu — from an export folder.

    uv run python manage.py load_odoo_picklists /path/to/export --dry-run
    uv run python manage.py load_odoo_picklists /path/to/export

The folder holds one file per Odoo list, named after the Odoo model, plain or
gzipped (`inst.car.color.json`, `inst.car.color.json.gz`). A list whose file is
not there is reported and left alone.

Three things decide how this is written:

* **Only the twelve lists that are new here** (`LISTS` and `ON_HOLD` below). The
  same export carries Odoo's brands, models, sources and mediums, and this
  never opens them: the car catalogue is what the assistant matches a
  customer's words against, and folding Odoo's spellings into it is a decision
  of its own.
* **It can be run again.** Every row carries `key = odoo_<list>_<odoo id>`; a
  second run adds only what is missing and never rewrites a row somebody has
  corrected here since.
* **On hold needs a person.** Odoo names a salesperson by its own user id.
  `users.json` (the Odoo users: id, login, name), when it is in the folder,
  turns that into a login, and the login is the email of the account here. No
  file, or no such account: the row is skipped, counted and named — nobody is
  put on hold on the strength of a display name.

Rows go in with `bulk_create`: no save hook, no notification, nothing sent.
"""
import gzip
import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

#: Odoo model (= file name) -> (our model, the <list> of the key, the fields besides `name`)
LISTS = {
    'inst.car.model.year': ('CarModelYear', 'car_model_year', ()),
    'inst.car.color': ('CarColour', 'car_color', ()),
    'inst.car.trim.level': ('CarTrimLevel', 'car_trim_level', ('options_features',)),
    'inst.car.buyer': ('CarBuyer', 'car_buyer', ('company_name', 'address')),
    'inst.delivery.arrival.port': ('ArrivalPort', 'arrival_port', ()),
    'inst.delivery.shipping.destination': ('ShippingDestination', 'shipping_destination', ()),
    'inst.delivery.international.shipper': ('InternationalShipper', 'international_shipper', ()),
    'inst.delivery.international.shipping': ('LoadingPort', 'international_shipping', ()),
    'inst.delivery.custom.clearance.person.employee': ('CustomsClearancePerson', 'clearance_person', ()),
    'inst.opportunity.product.type': ('OpportunityProductType', 'product_type', ()),
    'inst.blacklist.res.partner': ('BlacklistedCustomer', 'blacklist', ('phone',)),
}
ON_HOLD = 'inst.onhold.res.users'


def text(value):
    """Odoo writes an empty field as `false`."""
    return '' if value in (None, False) else str(value)


def clean_label(value):
    """Odoo labels carry no-break spaces and stretched letters («مرحلــــة»)."""
    return re.sub(r'\s+', ' ', text(value).replace('\xa0', ' ').replace('ـ', '')).strip()


class Command(BaseCommand):
    help = "Load the Odoo pick-lists of the Link Tracker menu (the twelve new lists) — safe to re-run"

    def add_arguments(self, parser):
        parser.add_argument('folder', help="Folder holding the exported .json / .json.gz files")
        parser.add_argument('--dry-run', action='store_true', help="Do everything, then roll it all back")

    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        self.folder = Path(options['folder'])
        if not self.folder.is_dir():
            raise CommandError(f'{self.folder} is not a folder')
        self.lines, self.found = [], 0
        with transaction.atomic():
            self._run()
            if options['dry_run']:
                transaction.set_rollback(True)
        if not self.found:
            raise CommandError(f'None of the pick-list files is in {self.folder}')
        for line in self.lines:
            self.stdout.write('  ' + line)
        self.stdout.write(self.style.WARNING('dry run — nothing written') if options['dry_run']
                          else self.style.SUCCESS('done'))

    def _load(self, name):
        """The rows of one exported list, oldest first; None when the folder does not have it."""
        for candidate in (self.folder / f'{name}.json', self.folder / f'{name}.json.gz'):
            if candidate.exists():
                opener = gzip.open if candidate.suffix == '.gz' else open
                with opener(candidate, 'rt', encoding='utf-8') as handle:
                    return sorted(json.load(handle), key=lambda row: row['id'])
        return None

    def _say(self, name, rows, created, already, skipped=''):
        self.found += 1
        self.lines.append(f'{name}: {len(rows)} in the file, {created} created, {already} already loaded{skipped}')

    # ------------------------------------------------------------------
    def _run(self):
        from django.apps import apps

        for name, (model_name, prefix, extras) in LISTS.items():
            rows = self._load(name)
            if rows is None:
                self.lines.append(f'{name}: not in the folder')
                continue
            self._names(name, rows, apps.get_model('car_import', model_name), f'odoo_{prefix}_', extras)
        rows = self._load(ON_HOLD)
        if rows is None:
            self.lines.append(f'{ON_HOLD}: not in the folder')
        else:
            self._on_hold(rows, apps.get_model('car_import', 'OnHoldSalesperson'))

    def _names(self, name, rows, model, prefix, extras):
        """A list of names, with the few extra columns some of them carry."""
        have = set(model._base_manager.filter(key__startswith=prefix).values_list('key', flat=True))
        limit = {field: model._meta.get_field(field).max_length for field in ('name',) + tuple(extras)}
        new, nameless = [], 0
        for row in rows:
            key = f"{prefix}{row['id']}"
            if key in have:
                continue
            label = clean_label(row.get('name'))
            if not label:
                nameless += 1
                continue
            values = {field: text(row.get(field)).strip()[:limit[field]] for field in extras}
            new.append(model(key=key, name=label[:limit['name']], **values))
        model._base_manager.bulk_create(new)
        self._say(name, rows, len(new), len(rows) - len(new) - nameless,
                  f', {nameless} skipped (no name)' if nameless else '')

    def _on_hold(self, rows, model):
        """One row per salesperson, for the ones who have an account here."""
        from modules.base.models.user import User

        users = self._load('users')
        logins = {row['id']: text(row.get('login')).strip().lower() for row in users or ()}
        accounts = {(email or '').lower(): pk for email, pk in User.objects.values_list('email', 'pk')}
        have = set(model._base_manager.filter(key__startswith='odoo_onhold_').values_list('key', flat=True))
        held = set(model._base_manager.values_list('user_id', flat=True))
        new, already, unknown = [], 0, []
        for row in rows:
            key = f"odoo_onhold_{row['id']}"
            pair = row.get('user_id') or ()
            user_pk = accounts.get(logins.get(pair[0] if pair else None) or None)
            if key in have or user_pk in held:        # loaded before, or put on hold here by hand
                already += 1
            elif user_pk is None:
                unknown.append(text(pair[1] if len(pair) > 1 else '') or f"Odoo user {pair[0] if pair else '?'}")
            else:
                held.add(user_pk)
                new.append(model(key=key, user_id=user_pk, hidden=bool(row.get('hidden'))))
        model._base_manager.bulk_create(new)
        self._say(ON_HOLD, rows, len(new), already,
                  f', {len(unknown)} skipped (no account here)' if unknown else '')
        if unknown and users is None:
            self.lines.append('  users.json is not in the folder, so no on-hold row could be matched to an account')
        for label in unknown:
            self.lines.append(f'  skipped: {label}')
