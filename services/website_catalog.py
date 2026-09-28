# -*- coding: utf-8 -*-
"""The cars the company has NOW, as the assistant may offer them.

The source is the company website's catalogue (`WebsiteCar`), which Genie
keeps in step with the website. The assistant reaches it only through its car
search tool — never through its prompt: a list pasted into a prompt is stale
the moment a car is sold, and the prompt is cached for everyone.

Offered: shown on the website, not sold or booked, not archived (test entries
are archived, not deleted, so the nightly import does not bring them back).
"""
from django.db.models import Q

EGYPT, GERMANY = 1, 2


def _fmt(value, symbol):
    if value is None:
        return None
    text = f'{value:,.2f}'
    return f'{text[:-3] if text.endswith(".00") else text} {symbol}'


def offerable():
    from car_import.models import WebsiteCar
    return (WebsiteCar.objects.filter(active=True, visible=True)
            .exclude(website_status__in=['sold', 'booked'])
            .select_related('location', 'brand', 'model', 'fuel', 'gearbox', 'engine', 'bodytype', 'currency'))


def our_cars(query='', location=None, limit=8):
    """(cars, totals) — cars matching the words, newest first; totals per location."""
    rows = offerable()
    totals = {'egypt': rows.filter(location__website_id=EGYPT).count(),
              'germany': rows.filter(location__website_id=GERMANY).count()}
    if location == 'egypt':
        rows = rows.filter(location__website_id=EGYPT)
    elif location == 'germany':
        rows = rows.filter(location__website_id=GERMANY)
    for word in str(query or '').split():
        rows = rows.filter(Q(title_en__icontains=word) | Q(title_ar__icontains=word)
                           | Q(brand__name_en__icontains=word) | Q(brand__name_ar__icontains=word)
                           | Q(model__name_en__icontains=word) | Q(serial__iexact=word))
    cars = []
    for car in rows.order_by('-website_id')[:max(1, min(int(limit or 8), 20))]:
        in_egypt = car.location_id and car.location.website_id == EGYPT
        cars.append({
            'reference': f'WC-{car.pk}',
            'title': car.title_ar or car.title_en,
            'title_en': car.title_en,
            'brand': car.brand.name_en if car.brand_id else None,
            'model': car.model.name_en if car.model_id else None,
            'year': car.year,
            'mileage_km': car.distance,
            'fuel': car.fuel.name_ar or car.fuel.name_en if car.fuel_id else None,
            'gearbox': car.gearbox.name_ar or car.gearbox.name_en if car.gearbox_id else None,
            'engine': car.engine.name_en if car.engine_id else None,
            'price': _fmt(car.price, 'ج.م' if in_egypt else '€'),
            'where': ('في معرضنا في مصر — استلام فوري' if in_egypt
                      else 'في ألمانيا عندنا — محتاجة شحن لمصر'),
            'price_note': ('Final price in EGP as listed on our website.' if in_egypt
                           else 'Price in EUR as listed on our website for the car in Germany. It is not the '
                                'delivered-to-Egypt cost; do not add figures to it yourself.'),
            'extras': car.extra_options.count(),
            'photos_available': int(bool(car.site_image_url)) + len(car.site_gallery_urls or []),
            'about': (car.description_ar or car.description_en or '')[:220],
        })
    return cars, totals
