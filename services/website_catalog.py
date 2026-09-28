# -*- coding: utf-8 -*-
"""The cars the company has NOW, as the assistant may offer them.

The source is the company website's catalogue (`WebsiteCar`), which Genie
keeps in step with the website. The assistant reaches it only through its car
search tool — never through its prompt: a list pasted into a prompt is stale
the moment a car is sold, and the prompt is cached for everyone.

Offered: shown on the website, not sold or booked, not archived (test entries
are archived, not deleted, so the nightly import does not bring them back).

A search is always NARROW. The customer names a brand, a budget or a year
first, and the answer is a handful of cars plus a link to see the rest on the
website — never the whole stock read out in a chat. A customer who does not
know what they want gets the website to browse and comes back with a car.
"""
import re

from django.db.models import Q

EGYPT, GERMANY = 1, 2
DEFAULT_LIMIT, MAX_LIMIT = 3, 5


def _fmt(value, symbol):
    if value is None:
        return None
    text = f'{value:,.2f}'
    return f'{text[:-3] if text.endswith(".00") else text} {symbol}'


# ── the website's public pages ───────────────────────────────────────────────
def site_url():
    """https://khaledautomobilegmbh.de — the API address without its /api."""
    from car_import.models import WebsiteConnection
    base = (WebsiteConnection.get().base_url or '').rstrip('/')
    return re.sub(r'/api$', '', base) or 'https://khaledautomobilegmbh.de'


def cars_link(brand=None, car_model=None, price_min=None, price_max=None):
    """The website's car list, already filtered the way the customer asked."""
    params = []
    if brand is not None and brand.website_id:
        params.append(f'brand_id={brand.website_id}')
    if car_model is not None and car_model.website_id:
        params.append(f'model_id={car_model.website_id}')
    if price_min:
        params.append(f'price_from={int(price_min)}')
    if price_max:
        params.append(f'price_to={int(price_max)}')
    return f'{site_url()}/cars' + ('?' + '&'.join(params) if params else '')


def car_link(car):
    """One car's page. The website reads the number; the words are for people."""
    if not car.website_id:
        return None
    slug = re.sub(r'[^a-z0-9]+', '-', (car.title_en or '').lower()).strip('-') or 'car'
    return f'{site_url()}/cars-details/{car.website_id}/{slug}'


# ── the stock ────────────────────────────────────────────────────────────────
def offerable():
    from car_import.models import WebsiteCar
    return (WebsiteCar.objects.filter(active=True, visible=True)
            .exclude(website_status__in=['sold', 'booked'])
            .select_related('location', 'brand', 'car_model', 'currency'))


def totals(rows=None):
    rows = offerable() if rows is None else rows
    return {'in_egypt_showroom': rows.filter(location__website_id=EGYPT).count(),
            'in_germany': rows.filter(location__website_id=GERMANY).count()}


def budget_currency(price_min=None, price_max=None, currency=None, location=None):
    """'EGP' or 'EUR' — which cars a price range can apply to. Said by the
    customer when possible; else the place; else the size of the number (a
    six-figure-plus budget is pounds, a car in euros rarely is)."""
    code = str(currency or '').strip().upper()
    if code in ('EGP', 'LE', 'جنيه', 'ج.م'):
        return 'EGP'
    if code in ('EUR', '€', 'يورو'):
        return 'EUR'
    if location == 'egypt':
        return 'EGP'
    if location == 'germany':
        return 'EUR'
    biggest = max(float(price_min or 0), float(price_max or 0))
    return 'EGP' if biggest >= 300000 else 'EUR'


def our_cars(brand=None, model=None, price_min=None, price_max=None, year_min=None, year_max=None,
             location=None, limit=DEFAULT_LIMIT, currency=None):
    """A narrow look at the stock. Returns a dict: `cars` (at most `limit`),
    `matching` (how many match in all), `see_all_on_website`, `understood`
    (the brand/model the words were read as) and `totals` per place.

    Prices are compared in each car's own currency: pounds for the Egypt
    showroom, euros for cars in Germany — the currency the customer's budget
    is in decides which cars a price range can apply to."""
    from car_import.services import catalogue

    rows = offerable()
    if location == 'egypt':
        rows = rows.filter(location__website_id=EGYPT)
    elif location == 'germany':
        rows = rows.filter(location__website_id=GERMANY)

    brand_row, model_row = catalogue.resolve(brand, model) if brand else (None, None)
    if brand_row is None and (brand or model):
        brand_row, model_row = catalogue.parse(' '.join(x for x in [brand, model] if x))
    if brand_row is not None:
        rows = rows.filter(brand=brand_row)
        if model_row is not None:
            rows = rows.filter(car_model=model_row)
        elif model:
            for word in str(model).split():
                rows = rows.filter(Q(title_en__icontains=word) | Q(title_ar__icontains=word)
                                   | Q(car_model__name__icontains=word))
    else:
        for word in ' '.join(x for x in [brand, model] if x).split():
            rows = rows.filter(Q(title_en__icontains=word) | Q(title_ar__icontains=word)
                               | Q(brand__name__icontains=word) | Q(brand__name_ar__icontains=word)
                               | Q(car_model__name__icontains=word) | Q(serial__iexact=word))
    money = None
    if price_min or price_max:
        money = budget_currency(price_min, price_max, currency, location)
        rows = rows.filter(currency__code=money)
    if price_min:
        rows = rows.filter(price__gte=price_min)
    if price_max:
        rows = rows.filter(price__lte=price_max)
    if year_min:
        rows = rows.filter(year__gte=year_min)
    if year_max:
        rows = rows.filter(year__lte=year_max)

    cap = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
    ordered = rows.order_by('price', '-website_id') if (price_min or price_max) else rows.order_by('-website_id')
    cars = []
    for car in ordered[:cap]:
        in_egypt = car.location_id and car.location.website_id == EGYPT
        cars.append({
            'reference': f'WC-{car.pk}',
            'title': car.title_ar or car.title_en,
            'year': car.year,
            'mileage_km': car.distance,
            'price': _fmt(car.price, 'ج.م' if in_egypt else '€'),
            'where': ('في معرضنا في مصر — استلام فوري' if in_egypt
                      else 'في ألمانيا عندنا — محتاجة شحن لمصر'),
            'link': car_link(car),
            'photos_available': int(bool(car.site_image_url)) + len(car.site_gallery_urls or []),
        })
    return {
        'cars': cars,
        'matching': rows.count(),
        'see_all_on_website': cars_link(brand_row, model_row, price_min, price_max),
        'understood': {'brand': brand_row.name if brand_row else None,
                       'model': model_row.name if model_row else None,
                       'budget_currency': money},
        'totals': totals(),
    }
