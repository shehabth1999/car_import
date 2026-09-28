# Fills the car catalogue and points every row at it.
#
#   1. The website's brand and model lists become the catalogue (their website
#      ids kept, so cars can still be sent there).
#   2. Website cars follow their list entries into the catalogue.
#   3. Every free-text make/model — car records, supplier adverts, the workbook's
#      deposit / customs / price tables — is matched to the catalogue, folding
#      case, spaces and punctuation ("Mercedes" = "Mercedes-Benz", "C 200" =
#      "C200"). Text with no match is ADDED, never dropped: it is authoritative
#      data (the owner's workbook, an advert), not a customer's typo.
#
# Self-contained on purpose: a migration must not import the live services.

import re

from django.db import migrations

_KEEP = re.compile(r'[^a-z0-9؀-ۿ]')

#: Spellings the website lists do not carry but the company's data does.
BRAND_ALIASES = {
    'mercedes': 'Mercedes-Benz, Mercedes Benz, Benz, مرسيدس بنز',
    'volkswagen': 'VW, فولكس',
    'landrover': 'Range Rover, رينج روفر, رنج روفر',
}


def _norm(text):
    text = str(text or '').lower()
    text = text.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا').replace('ة', 'ه').replace('ى', 'ي')
    return _KEEP.sub('', text)


def _tidy(text):
    text = re.sub(r'\s+', ' ', str(text or '').strip())
    if text.isupper() and text.isalpha() and len(text) > 4:
        text = text.title()
    return text


def _names(row):
    return [n for n in [row.name, row.name_ar] + [a.strip() for a in (row.aliases or '').split(',')] if n]


def forwards(apps, schema_editor):
    Lookup = apps.get_model('car_import', 'WebsiteLookup')
    Brand = apps.get_model('car_import', 'CarBrand')
    CarModel = apps.get_model('car_import', 'CarModel')
    WebsiteCar = apps.get_model('car_import', 'WebsiteCar')
    Vehicle = apps.get_model('car_import', 'Vehicle')
    SupplierListing = apps.get_model('car_import', 'SupplierListing')
    tables = [apps.get_model('car_import', name) for name in ('DepositTier', 'CustomsValuation', 'ModelPriceRange')]

    # ── 1. the website's lists → the catalogue ──────────────────────────────
    brand_by_site, model_by_site = {}, {}
    for row in Lookup.objects.filter(kind='brand').order_by('website_id'):
        name = (row.name_en or row.name_ar or f'#{row.website_id}').strip()[:64]
        if Brand.objects.filter(name=name).exists():
            name = f'{name} #{row.website_id}'[:64]
        aliases = ', '.join(a for a in [row.aliases, BRAND_ALIASES.get(_norm(name), '')] if a)[:255]
        brand_by_site[row.website_id] = Brand.objects.create(
            name=name, name_ar=(row.name_ar or '')[:64], aliases=aliases, website_id=row.website_id)
    for row in Lookup.objects.filter(kind='model').order_by('website_id'):
        brand = brand_by_site.get(row.brand_website_id)
        if brand is None:
            continue
        name = (row.name_en or row.name_ar or f'#{row.website_id}').strip()[:128]
        if CarModel.objects.filter(brand=brand, name=name).exists():
            name = f'{name} #{row.website_id}'[:128]
        model_by_site[row.website_id] = CarModel.objects.create(
            brand=brand, name=name, name_ar=(row.name_ar or '')[:128], aliases=row.aliases or '',
            website_id=row.website_id, display_name=f'{brand.name} {name}')

    # ── 2. website cars ─────────────────────────────────────────────────────
    site_id = dict(Lookup.objects.filter(kind__in=['brand', 'model']).values_list('pk', 'website_id'))
    for car in WebsiteCar.objects.all():
        car_model = model_by_site.get(site_id.get(car.model_id)) if car.model_id else None
        brand = brand_by_site.get(site_id.get(car.brand_id)) if car.brand_id else None
        WebsiteCar.objects.filter(pk=car.pk).update(
            catalogue_brand=brand or (car_model.brand if car_model else None), car_model=car_model)

    # ── 3. free text → the catalogue ────────────────────────────────────────
    brands = list(Brand.objects.all())

    def ensure_brand(text):
        wanted = _norm(text)
        if not wanted or text.strip() in ('—', '-'):
            return None
        for brand in brands:
            if wanted in {_norm(n) for n in _names(brand)}:
                return brand
        hits = [b for b in brands if len(wanted) >= 3 and any(
            len(n) >= 3 and (n.startswith(wanted) or wanted.startswith(n)) for n in map(_norm, _names(b)))]
        if len(hits) == 1:
            return hits[0]
        brand = Brand.objects.create(name=_tidy(text)[:64])
        brands.append(brand)
        return brand

    def ensure_model(brand, text):
        wanted = _norm(text)
        if brand is None or not wanted or text.strip() in ('—', '-'):
            return None
        for car_model in CarModel.objects.filter(brand=brand):
            if wanted in {_norm(n) for n in _names(car_model)}:
                return car_model
        name = _tidy(text)[:128]
        return CarModel.objects.create(brand=brand, name=name, display_name=f'{brand.name} {name}')

    for vehicle in Vehicle.objects.all():
        brand = ensure_brand(vehicle.make)
        car_model = ensure_model(brand, vehicle.model)
        parts = [brand.name if brand else '', car_model.name if car_model else '', vehicle.trim,
                 str(vehicle.model_year or '')]
        name = ' '.join(p for p in parts if p).strip() or vehicle.vin or '—'
        Vehicle.objects.filter(pk=vehicle.pk).update(brand=brand, car_model=car_model, name=name[:255])

    for listing in SupplierListing.objects.all():
        brand = ensure_brand(listing.make)
        SupplierListing.objects.filter(pk=listing.pk).update(brand=brand, car_model=ensure_model(brand, listing.model))

    for Table in tables:
        for row in Table.objects.all():
            Table.objects.filter(pk=row.pk).update(car_model=ensure_model(ensure_brand(row.make), row.model))

    # ── 4. the brand and model lists now live in the catalogue ──────────────
    WebsiteCar.objects.update(brand=None, model=None)
    Lookup.objects.filter(kind__in=['brand', 'model']).delete()

    # Fire the deferred FK checks now, inside this migration, not at the next
    # ALTER TABLE ("pending trigger events").
    schema_editor.execute('SET CONSTRAINTS ALL IMMEDIATE')


class Migration(migrations.Migration):

    dependencies = [
        ('car_import', '0021_car_catalogue'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
