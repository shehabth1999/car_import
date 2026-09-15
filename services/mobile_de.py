# -*- coding: utf-8 -*-
"""mobile.de Search API — with a simulator so the build never waits on a key.

The endpoint and every parameter name below were taken from the official
documentation at https://services.mobile.de/docs/search-api.html (re-verified
2026-09-16), not from memory:

    GET https://services.mobile.de/search-api/search?<params>
    HTTP Basic auth (mandatory)
    Accept: application/vnd.de.mobile.api+json
    classification · price.min/max · firstRegistrationDate.min/max ·
    mileage.min/max · fuel · gearbox · power.min/max · vatable=1 ·
    country · customerNumber · sort.field/sort.order · page.number/page.size
    page.size caps at 100, and at most 2,000 ads can be paged through.

**Two backends, one interface.** `LiveBackend` talks to mobile.de when
credentials exist. `SimulatedBackend` answers from a fixture with the same
filtering, the same paging and the same response shape when they do not — so
everything downstream (import, screens, tools, pricing) is written once and
does not change when the real key arrives.

Every simulated row is stamped `is_simulated`, and nothing anywhere strips that
flag: a fake car must never be quotable to a customer by accident.
"""
import base64
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

BASE_URL = 'https://services.mobile.de'
SEARCH_PATH = '/search-api/search'
JSON_MEDIA_TYPE = 'application/vnd.de.mobile.api+json'

MAX_PAGE_SIZE = 100          # documented hard cap
MAX_ADS_PER_RESULT_SET = 2000  # documented hard cap

USERNAME_KEY = 'car_import.mobile_de_username'
PASSWORD_KEY = 'car_import.mobile_de_password'
FORCE_SIMULATION_KEY = 'car_import.mobile_de_force_simulation'


class MobileDeError(Exception):
    """Anything that stops a search returning results."""


# ───────────────────────────────────────────────────────────────────────────
# credentials
# ───────────────────────────────────────────────────────────────────────────
def _config(key):
    try:
        from modules.base.models import ConfigParameter
        row = ConfigParameter.objects.filter(key=key).values('value').first()
    except Exception:
        return ''
    return (row or {}).get('value') or ''


def credentials():
    """(username, password) from config, else from settings, else ('', '')."""
    user, password = _config(USERNAME_KEY), _config(PASSWORD_KEY)
    if not (user and password):
        from django.conf import settings
        user = user or getattr(settings, 'MOBILE_DE_USERNAME', '') or ''
        password = password or getattr(settings, 'MOBILE_DE_PASSWORD', '') or ''
    return user, password


def is_live():
    """True when a real search would be attempted."""
    if str(_config(FORCE_SIMULATION_KEY)).strip().lower() in ('1', 'true', 'yes', 'on'):
        return False
    user, password = credentials()
    return bool(user and password)


# ───────────────────────────────────────────────────────────────────────────
# the query — built once, used by both backends
# ───────────────────────────────────────────────────────────────────────────
def build_query(make=None, model=None, price_max=None, price_min=None,
                year_min=None, year_max=None, mileage_max=None, mileage_min=None,
                fuel=None, gearbox=None, power_min=None, power_max=None,
                vatable=True, country=None, sort_field='price',
                sort_order='ASCENDING', page_number=1, page_size=20):
    """The documented parameter names, and only those."""
    params = {}
    if make and model:
        params['classification'] = f'refdata/classes/Car/makes/{make}/models/{model}'
    elif make:
        params['classification'] = f'refdata/classes/Car/makes/{make}'
    if price_min is not None:
        params['price.min'] = int(price_min)
    if price_max is not None:
        params['price.max'] = int(price_max)
    if year_min is not None:
        params['firstRegistrationDate.min'] = f'{int(year_min)}-01'
    if year_max is not None:
        params['firstRegistrationDate.max'] = f'{int(year_max)}-12'
    if mileage_min is not None:
        params['mileage.min'] = int(mileage_min)
    if mileage_max is not None:
        params['mileage.max'] = int(mileage_max)
    if fuel:
        params['fuel'] = fuel
    if gearbox:
        params['gearbox'] = gearbox
    if power_min is not None:
        params['power.min'] = int(power_min)
    if power_max is not None:
        params['power.max'] = int(power_max)
    if vatable:
        params['vatable'] = 1          # documented as vatable=1, not true
    if country:
        params['country'] = country
    if sort_field:
        params['sort.field'] = sort_field
        params['sort.order'] = sort_order
    params['page.number'] = max(1, int(page_number))
    params['page.size'] = min(int(page_size), MAX_PAGE_SIZE)
    return params


# ───────────────────────────────────────────────────────────────────────────
# backends
# ───────────────────────────────────────────────────────────────────────────
class LiveBackend:
    """The real thing. Only used when credentials exist."""

    simulated = False

    def __init__(self, user, password, timeout=20):
        self.user = user
        self.password = password
        self.timeout = timeout

    def search(self, params):
        url = f'{BASE_URL}{SEARCH_PATH}?{urllib.parse.urlencode(params)}'
        token = base64.b64encode(f'{self.user}:{self.password}'.encode()).decode()
        request = urllib.request.Request(url, headers={
            'Accept': JSON_MEDIA_TYPE,
            'Authorization': f'Basic {token}',
        })
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            # 401 is the one everybody hits first: the account exists but the
            # Search API was never activated on it.
            body = ''
            try:
                body = exc.read().decode('utf-8', 'replace')[:400]
            except Exception:
                pass
            raise MobileDeError(f'mobile.de returned HTTP {exc.code}: {body}') from exc
        except urllib.error.URLError as exc:
            raise MobileDeError(f'mobile.de unreachable: {exc.reason}') from exc


class SimulatedBackend:
    """Same shape, same filters, same paging — from a fixture.

    It exists so that the importer, the screens, the AI tool and the pricing
    work that follows can all be written and tested now. It filters for real
    rather than returning the whole fixture, because code that is only ever fed
    matching data is code whose filters were never tested.
    """

    simulated = True

    def __init__(self, ads=None):
        self.ads = ads if ads is not None else load_fixture()

    def search(self, params):
        rows = [dict(ad) for ad in self.ads]

        classification = params.get('classification') or ''
        if '/makes/' in classification:
            wanted_make = classification.split('/makes/')[1].split('/')[0]
            rows = [a for a in rows if _slug(a.get('make')) == _slug(wanted_make)]
        if '/models/' in classification:
            wanted_model = classification.split('/models/')[1].split('/')[0]
            rows = [a for a in rows if _slug(wanted_model) in _slug(a.get('model'))]

        rows = _between(rows, 'price', params.get('price.min'), params.get('price.max'))
        rows = _between(rows, 'mileage', params.get('mileage.min'), params.get('mileage.max'))
        rows = _between(rows, 'power_kw', params.get('power.min'), params.get('power.max'))

        year_min = _year_of(params.get('firstRegistrationDate.min'))
        year_max = _year_of(params.get('firstRegistrationDate.max'))
        rows = _between(rows, 'model_year', year_min, year_max)

        if params.get('fuel'):
            rows = [a for a in rows if _slug(a.get('fuel')) == _slug(params['fuel'])]
        if params.get('gearbox'):
            rows = [a for a in rows if _slug(a.get('gearbox')) == _slug(params['gearbox'])]
        if params.get('vatable'):
            rows = [a for a in rows if a.get('vatable')]
        if params.get('country'):
            rows = [a for a in rows if _slug(a.get('country')) == _slug(params['country'])]

        reverse = str(params.get('sort.order', '')).upper().startswith('DESC')
        field = {'price': 'price', 'mileage': 'mileage',
                 'firstRegistrationDate': 'model_year'}.get(params.get('sort.field'), 'price')
        rows.sort(key=lambda a: (a.get(field) is None, a.get(field)), reverse=reverse)

        total = len(rows)
        size = min(int(params.get('page.size', 20)), MAX_PAGE_SIZE)
        number = max(1, int(params.get('page.number', 1)))
        start = (number - 1) * size
        page = rows[start:start + size]

        return {
            'total': min(total, MAX_ADS_PER_RESULT_SET),
            'page': {'number': number, 'size': size},
            'ads': page,
            'simulated': True,
        }


def _slug(value):
    return str(value or '').strip().lower().replace('-', '').replace(' ', '')


def _year_of(value):
    try:
        return int(str(value).split('-')[0])
    except (TypeError, ValueError):
        return None


def _between(rows, key, low, high):
    if low is not None:
        rows = [a for a in rows if a.get(key) is not None and a[key] >= float(low)]
    if high is not None:
        rows = [a for a in rows if a.get(key) is not None and a[key] <= float(high)]
    return rows


def load_fixture():
    """The simulated marketplace, from `fixtures/mobile_de_sample_ads.json`."""
    import os
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'fixtures', 'mobile_de_sample_ads.json')
    try:
        with open(path, encoding='utf-8') as handle:
            return json.load(handle)
    except Exception:
        logger.exception('car_import: could not read the mobile.de fixture')
        return []


def get_backend():
    """Live when we can, simulated when we cannot — and it says which."""
    if is_live():
        user, password = credentials()
        return LiveBackend(user, password)
    return SimulatedBackend()


# ───────────────────────────────────────────────────────────────────────────
# one normalised shape, whichever backend answered
# ───────────────────────────────────────────────────────────────────────────
def _normalise(ad, simulated):
    """Flatten either backend's ad into the columns SupplierListing keeps."""
    if simulated:
        # Mapped field by field, NOT copied wholesale: the fixture speaks the
        # marketplace's language (`price`, `mileage`) and the model speaks ours.
        # Copying the dict shipped both, and the model rejected the extras.
        return {
            'ad_id': str(ad.get('ad_id') or ad.get('id') or ''),
            'url': ad.get('url') or '',
            'make': ad.get('make') or '',
            'model': ad.get('model') or '',
            'version': ad.get('version') or '',
            'model_year': ad.get('model_year'),
            'first_registration': ad.get('first_registration') or '',
            'mileage_km': ad.get('mileage'),
            'cc': ad.get('cc'),
            'power_kw': ad.get('power_kw'),
            'power_hp': ad.get('power_hp'),
            'fuel': ad.get('fuel') or '',
            'gearbox': ad.get('gearbox') or '',
            'colour_exterior': ad.get('colour_exterior') or '',
            'condition_new': bool(ad.get('condition_new')),
            'accident_free': bool(ad.get('accident_free')),
            'price_gross_eur': ad.get('price'),
            'vatable': bool(ad.get('vatable')),
            'seller_name': ad.get('seller_name') or '',
            'seller_type': ad.get('seller_type') or 'unknown',
            'seller_city': ad.get('seller_city') or '',
            'country': ad.get('country') or '',
            'images': ad.get('images') or [],
            'features': ad.get('features') or [],
            'is_simulated': True,
            'raw': ad,
        }

    # The live shape nests price and seller; keep the raw payload either way so
    # a mapping mistake can be corrected later without re-querying.
    price = (ad.get('price') or {}).get('consumerPriceGross') or {}
    seller = ad.get('seller') or {}
    return {
        'ad_id': str(ad.get('mobileAdId') or ad.get('id') or ''),
        'url': ad.get('detailPageUrl') or '',
        'make': ad.get('make') or '',
        'model': ad.get('model') or '',
        'version': ad.get('modelDescription') or '',
        'model_year': _year_of(ad.get('firstRegistration')),
        'first_registration': ad.get('firstRegistration') or '',
        'mileage_km': ad.get('mileage'),
        'cc': ad.get('cubicCapacity'),
        'power_kw': ad.get('power'),
        'fuel': ad.get('fuel') or '',
        'gearbox': ad.get('gearbox') or '',
        'colour_exterior': ad.get('exteriorColor') or '',
        'condition_new': bool(ad.get('condition') == 'NEW'),
        'accident_free': bool(ad.get('accidentDamaged') is False),
        'price_gross_eur': price.get('amount'),
        'vatable': bool(ad.get('vatable')),
        'seller_name': seller.get('name') or '',
        'seller_type': 'dealer' if seller.get('type') == 'DEALER' else 'private',
        'seller_city': (seller.get('address') or {}).get('city') or '',
        'country': (seller.get('address') or {}).get('country') or '',
        'images': [i.get('xxl') or i.get('l') or '' for i in (ad.get('images') or [])],
        'features': ad.get('features') or [],
        'is_simulated': False,
        'raw': ad,
    }


def search(**kwargs):
    """Search, and return (listings, meta). Never raises for an empty result."""
    backend = get_backend()
    params = build_query(**kwargs)
    payload = backend.search(params)
    ads = payload.get('ads') or payload.get('searchResult', {}).get('ads') or []
    listings = [_normalise(ad, backend.simulated) for ad in ads]
    meta = {
        'simulated': backend.simulated,
        'total': payload.get('total') or payload.get('searchResult', {}).get('total') or len(ads),
        'page': params['page.number'],
        'page_size': params['page.size'],
        'params': params,
    }
    if backend.simulated:
        logger.info('car_import: mobile.de search served by the SIMULATOR (no credentials)')
    return listings, meta


def import_listings(listings, deal=None):
    """Write what a search returned into SupplierListing rows."""
    from car_import.models import SupplierListing

    now = timezone.now()
    created, updated = [], []
    for data in listings:
        ad_id = data.get('ad_id')
        if not ad_id:
            continue
        values = {k: v for k, v in data.items() if k != 'ad_id'}
        values.update({'last_seen_at': now, 'still_available': True, 'gone_at': None})
        if deal is not None:
            values['deal'] = deal
        row = SupplierListing.objects.filter(source='mobile.de', ad_id=ad_id).first()
        if row is None:
            values['first_seen_at'] = now
            row = SupplierListing.create(source='mobile.de', ad_id=ad_id, **values)
            created.append(row)
        else:
            for field, value in values.items():
                setattr(row, field, value)
            row.save()
            updated.append(row)
    return created, updated


def refresh_availability(queryset=None):
    """Re-check stored listings and flag the ones that are gone.

    Quoting a sold car is the client's most common complaint about their own
    process; this is the job that stops it.
    """
    from car_import.models import SupplierListing

    rows = queryset if queryset is not None else SupplierListing.objects.filter(
        still_available=True, source='mobile.de')
    backend = get_backend()
    now = timezone.now()
    gone, seen, failed = 0, 0, 0

    # One search per make/model rather than per row: the API has no documented
    # "fetch one ad by id" endpoint on the search service, so presence in the
    # current result set is what tells us the advert is still up.
    by_group = {}
    for row in rows:
        by_group.setdefault((row.make, row.model), []).append(row)

    for (make, model), group in by_group.items():
        try:
            payload = backend.search(build_query(
                make=make or None, model=model or None,
                vatable=False, page_size=MAX_PAGE_SIZE))
        except MobileDeError:
            failed += len(group)
            logger.warning('car_import: could not refresh %s %s', make, model)
            continue
        ads = payload.get('ads') or payload.get('searchResult', {}).get('ads') or []
        live_ids = {str(ad.get('ad_id') or ad.get('mobileAdId') or '') for ad in ads}
        for row in group:
            if row.ad_id in live_ids:
                row.last_seen_at = now
                seen += 1
            else:
                row.still_available = False
                row.gone_at = now
                gone += 1
            row.save()

    return {'seen': seen, 'gone': gone, 'failed': failed, 'simulated': backend.simulated}
