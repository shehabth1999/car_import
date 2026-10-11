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

**Three backends, one interface.** `LiveBackend` talks to mobile.de when
credentials exist. `ApifyBackend` reads the public site through an Apify Actor
(`services/apify.py`); it is used only when the switch
`car_import.mobile_de_backend` says `apify` — a token in the environment does
not turn it on by itself. `SimulatedBackend` answers from a fixture with the
same filtering, paging and response shape, for a developer's machine.

**The simulator never answers by default** (2026-10-11, the day the tenant went
to production use). It used to stand in whenever nothing real was configured,
which is how nine invented cars came to sit in a tenant about to go live. Now
it answers only where somebody asked for it by name
(`car_import.mobile_de_backend = simulator`); with no real source the search
says so and returns nothing.

Every simulated row is stamped `is_simulated`, and nothing anywhere strips that
flag: a fake car must never be quotable to a customer by accident.
"""
import base64
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

BASE_URL = 'https://services.mobile.de'
SEARCH_PATH = '/search-api/search'
AD_PATH = '/search-api/ad/'
JSON_MEDIA_TYPE = 'application/vnd.de.mobile.api+json'

MAX_PAGE_SIZE = 100          # documented hard cap
MAX_ADS_PER_RESULT_SET = 2000  # documented hard cap

USERNAME_KEY = 'car_import.mobile_de_username'
PASSWORD_KEY = 'car_import.mobile_de_password'
FORCE_SIMULATION_KEY = 'car_import.mobile_de_force_simulation'
#: `apify`, `simulator` (a developer's machine only), or `auto` — the official
#: API when it has credentials, else nothing. Anything else reads as `auto`.
BACKEND_KEY = 'car_import.mobile_de_backend'

# The Apify Actor that reads mobile.de, pay per result. Its input and output
# were read off its public schema and README on 2026-10-11; `_normalise_apify`
# is written for THIS Actor, which is why it is a constant and not a switch.
APIFY_ACTOR = '3x1t~mobile-de-scraper-ppr'
APIFY_MAX_ITEMS_PER_RUN = 50
DETAIL_URL = 'https://suchen.mobile.de/fahrzeuge/details.html?id=%s'


class MobileDeError(Exception):
    """Anything that stops a search returning results.

    `for_agent` marks a message written for the assistant — what to ask the
    customer next. Every other message is for whoever runs the system (a
    missing token, the day's limit, a switch to set) and must not reach a chat.
    """

    def __init__(self, message, for_agent=False):
        super().__init__(message)
        self.for_agent = for_agent


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

    name = 'official'
    simulated = False
    gone_is_certain = True       # a 404 on an advert means it was taken down

    def __init__(self, user, password, timeout=20):
        self.user = user
        self.password = password
        self.timeout = timeout

    def search(self, params, model_class=None, **_rules):
        return self._get(f'{BASE_URL}{SEARCH_PATH}?{urllib.parse.urlencode(params)}')

    def ad(self, ad_id):
        """One advert by its id — `GET /search-api/ad/{ad-key}` (documented;
        re-verified 2026-09-29). None when mobile.de has no such advert."""
        try:
            payload = self._get(f'{BASE_URL}{AD_PATH}{urllib.parse.quote(str(ad_id))}')
        except MobileDeError as exc:
            if 'HTTP 404' in str(exc):
                return None
            raise
        return (payload.get('ad') if isinstance(payload, dict) and 'ad' in payload else payload) or None

    def _get(self, url):
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

    name = 'simulator'
    simulated = True
    gone_is_certain = False

    def __init__(self, ads=None):
        self.ads = ads if ads is not None else load_fixture()

    def search(self, params, model_class=None, **_rules):
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

    def ad(self, ad_id):
        return next((dict(a) for a in self.ads
                     if str(a.get('ad_id') or a.get('id') or '') == str(ad_id)), None)


class ApifyBackend:
    """mobile.de's public pages, read by an Apify Actor (`services/apify.py`).

    The same two questions as the other backends — a search, and one advert —
    asked in the Actor's vocabulary. What the Actor cannot do is said here once:

    * it has NO price filter and NO VAT filter, so a budget and `vatable` are
      applied to what comes back — it asks for twice as many adverts when
      either is set, so that the filter still leaves enough;
    * it takes a model only from its own list (`Mercedes-Benz|C 200`), so a
      search needs a model or a class — a make alone is not something it can
      be asked for;
    * it returns one page, the first.
    """

    name = 'apify'
    simulated = False
    gone_is_certain = False      # an empty run may be a blocked run, not a sold car

    _SORT = {
        ('price', False): 'Price (lowest first)',
        ('price', True): 'Price (highest first)',
        ('mileage', False): 'Mileage (lowest first)',
        ('mileage', True): 'Mileage (highest first)',
        ('firstRegistrationDate', False): 'Initial registration date (oldest first)',
        ('firstRegistrationDate', True): 'Initial registration date (newest first)',
    }
    # The Actor's codes are the marketplace's own, the same as the official API's.
    _FUELS = {'PETROL', 'DIESEL', 'ELECTRICITY', 'HYBRID', 'HYBRID_DIESEL', 'LPG', 'CNG',
              'HYDROGENIUM', 'ETHANOL', 'OTHER'}
    _GEARBOXES = {'MANUAL_GEAR', 'AUTOMATIC_GEAR', 'SEMIAUTOMATIC_GEAR'}

    def search(self, params, model_class=None, saloon_only=False, accident_free=False):
        make, model = _classified(params)
        models = self._models(make, model, model_class)
        if not models:
            asked = model_class or model
            raise MobileDeError(
                f"No model '{asked}' is known for make '{make}'. Check the model's name with the "
                f"customer." if asked else
                f"Cars to import are searched by model: the make alone ('{make}') is not enough. Ask the "
                f"customer which model they want.", for_agent=True)

        size = max(1, min(int(params.get('page.size', 20)), APIFY_MAX_ITEMS_PER_RUN))
        # Every filter applied here, after the run, costs adverts — so the run
        # is asked for a multiple, and enough are left.
        late_filters = int(bool(params.get('vatable')) or any(
            params.get(key) is not None for key in ('price.min', 'price.max'))) + int(bool(accident_free))
        fetch = min(size * (1 + late_filters), APIFY_MAX_ITEMS_PER_RUN)
        descending = str(params.get('sort.order', '')).upper().startswith('DESC')
        run_input = {
            'searchCategory': 'Car', 'models': models, 'maxItems': fetch,
            'searchPageURLs': [], 'searchTerms': [],
            # Dealer reviews are not ours to collect, and each one slows the run.
            'automaticPaging': True, 'reviewLimit': 0, 'showDamagedVehicles': 'false',
            'sort': self._SORT.get((params.get('sort.field'), descending), 'Standard'),
        }
        for ours, theirs in (('mileage.min', 'mileageKmMin'), ('mileage.max', 'mileageKmMax'),
                             ('power.min', 'powerKwMin'), ('power.max', 'powerKwMax')):
            if params.get(ours) is not None:
                run_input[theirs] = int(params[ours])
        for ours, theirs in (('firstRegistrationDate.min', 'registrationDateYearMin'),
                             ('firstRegistrationDate.max', 'registrationDateYearMax')):
            year = _year_of(params.get(ours))
            if year:
                run_input[theirs] = year
        fuel = str(params.get('fuel') or '').upper()
        if fuel in self._FUELS:
            run_input['fuelType'] = [fuel]
        gearbox = str(params.get('gearbox') or '').upper()
        if gearbox in self._GEARBOXES:
            run_input['transmission'] = [gearbox]
        if params.get('country'):
            run_input['location'] = str(params['country']).upper()
        if saloon_only:
            run_input['vehicleType'] = ['Limousine']        # the marketplace's code for a saloon

        ads = self._run(run_input, fetch, timeout=120)
        ads = [ad for ad in ads if _price_within(ad, params.get('price.min'), params.get('price.max'))]
        if params.get('vatable'):
            ads = [ad for ad in ads if _apify_vat(ad)[0]]
        if accident_free:
            ads = [ad for ad in ads if _apify_accident_free(ad)]
        ads = ads[:size]
        return {'total': len(ads), 'page': {'number': 1, 'size': size}, 'ads': ads}

    def ad(self, ad_id):
        """One advert, by its page. None when the run returns nothing for it."""
        ads = self._run({
            'searchCategory': 'Car', 'searchPageURLs': [DETAIL_URL % urllib.parse.quote(str(ad_id))],
            'searchPageURLMaxItems': 1, 'maxItems': 1, 'automaticPaging': False, 'reviewLimit': 0,
        }, 1, timeout=60)
        # Only the advert that was asked for: a page that falls back to
        # "similar cars" is not an answer about this one.
        return next((ad for ad in ads if str(ad.get('id') or '') == str(ad_id)), None)

    def _run(self, run_input, max_items, timeout):
        from car_import.services import apify
        try:
            return apify.run_sync(APIFY_ACTOR, run_input, max_items=max_items, timeout=timeout)
        except apify.ApifyError as exc:
            raise MobileDeError(f'{exc} [{exc.kind}]') from exc

    def _models(self, make, model, model_class):
        """Our make and model in the Actor's words. Its list spells them the
        marketplace's way, so the match folds case and spacing ("C200" = "C 200")
        and reads the catalogue's own names first ("Mercedes" = "Mercedes-Benz")."""
        from car_import.services import apify, catalogue
        try:
            choices = apify.model_choices(APIFY_ACTOR)
        except apify.ApifyError as exc:
            raise MobileDeError(f'{exc} [{exc.kind}]') from exc

        brand = catalogue.find_brand(make)
        makes = {catalogue.norm(make), catalogue.norm(brand.name) if brand is not None else ''} - {''}
        of_make = [choice for choice in choices if catalogue.norm(choice.split('|')[0]) in makes]
        if model_class:
            in_class = re.compile(r'^%s[\s-]?\d' % re.escape(str(model_class).strip()), re.IGNORECASE)
            return [choice for choice in of_make if in_class.match(choice.split('|', 1)[-1])]
        car_model = catalogue.find_model(brand, model) if brand is not None else None
        names = {catalogue.norm(model), catalogue.norm(car_model.name) if car_model is not None else ''} - {''}
        return [choice for choice in of_make if catalogue.norm(choice.split('|', 1)[-1]) in names]


def _classified(params):
    """(make, model) back out of a query's `classification`."""
    text = str(params.get('classification') or '')
    make = text.split('/makes/')[1].split('/')[0] if '/makes/' in text else ''
    model = text.split('/models/')[1].split('/')[0] if '/models/' in text else ''
    return make, model


def _apify_vat(item):
    """(vatable, rate %) for an Apify item.

    Not in the Actor's README; read off real adverts on 2026-10-11. A car sold
    with VAT shown carries `price.withoutVAT` and `price.vat` (19); a car sold
    without — a private seller, or a dealer's margin-scheme stock — carries
    neither. That absence is the whole signal, so anything unclear is "no":
    the wrong "yes" understates a quote by the entire VAT.
    """
    price = item.get('price') if isinstance(item.get('price'), dict) else {}
    net = price.get('withoutVAT') if isinstance(price.get('withoutVAT'), dict) else {}
    rate = price.get('vat')
    vatable = bool(net.get('amount')) and isinstance(rate, (int, float)) and rate > 0
    return vatable, (rate if vatable else None)


def _apify_accident_free(item):
    """The seller declared the car accident-free — or it is new. The Actor has
    no filter for it; the advert says it in its condition line ("Used vehicle,
    Accident-free"), which is the same thing the marketplace's own checkbox
    reads. An advert that does not say so is left out: silence is not a claim."""
    attributes = item.get('attributes') if isinstance(item.get('attributes'), dict) else {}
    condition = str(attributes.get('Vehicle condition') or '').lower()
    return 'accident-free' in condition or condition.startswith('new')


def _price_within(ad, low, high):
    """The Actor has no price filter, so the budget is applied here."""
    if low is None and high is None:
        return True
    amount = (((ad.get('price') or {}).get('total') or {}).get('amount'))
    if amount is None:
        return False
    return (low is None or amount >= float(low)) and (high is None or amount <= float(high))


def _slug(value):
    return str(value or '').strip().lower().replace('-', '').replace(' ', '')


def _year_of(value):
    """2023 from '2023', '2023-05', the live API's '202305' (yyyyMM) or the
    Apify Actor's '05/2023'."""
    text = str(value or '').strip()
    if len(text) == 6 and text.isdigit():
        text = text[:4]
    month_first = re.fullmatch(r'\d{1,2}/((?:19|20)\d\d)', text)
    if month_first:
        return int(month_first.group(1))
    try:
        return int(text.split('-')[0])
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


def backend_choice():
    """What the switch says: `apify`, `simulator`, or `auto` for anything else."""
    value = str(_config(BACKEND_KEY)).strip().lower()
    return value if value in ('apify', 'simulator') else 'auto'


def _simulation_forced():
    return str(_config(FORCE_SIMULATION_KEY)).strip().lower() in ('1', 'true', 'yes', 'on')


def get_backend(force=None):
    """A real source, or an error that says what is missing — never fake cars
    unless they were asked for.

    `force` names a backend outright (`apify`, `official`, `simulator`) for a
    command that wants to try one without flipping the switch for everybody.
    Raises MobileDeError when the backend that was chosen cannot answer: a
    missing token must read as "no search today", not as a list of invented
    cars from another backend.
    """
    choice = str(force or backend_choice()).strip().lower()
    if choice == 'simulator' or (not force and _simulation_forced()):
        return SimulatedBackend()
    if choice == 'apify':
        from car_import.services import apify
        if apify.is_configured():
            return ApifyBackend()
        raise MobileDeError(f'{BACKEND_KEY} says apify but {apify.TOKEN_ENV} is not set in the environment')
    user, password = credentials()
    if user and password:
        return LiveBackend(user, password)
    if choice == 'official':
        raise MobileDeError('No mobile.de Search-API credentials are configured')
    raise MobileDeError(f'No mobile.de source is configured: set {BACKEND_KEY} to apify (with '
                        f'APIFY_TOKEN in the environment) or add the Search-API credentials')


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


def _first_number(text):
    """89106 from '89,106 km', 1984 from '1.984 ccm'. None when there is none."""
    match = re.search(r'\d[\d.,]*', str(text or ''))
    digits = re.sub(r'\D', '', match.group(0)) if match else ''
    return int(digits) if digits else None


def _normalise_apify(item):
    """The Apify Actor's item as the columns SupplierListing keeps.

    Written against the Actor's published sample and checked on real adverts
    (2026-10-11): the car's facts sit in `attributes` under the site's English
    labels, as display text with non-breaking spaces ("89,106 km",
    "169 kW (230 hp)", "08/2016"). `vatable` is `_apify_vat`.
    """
    attributes = item.get('attributes') if isinstance(item.get('attributes'), dict) else {}
    dealer = item.get('dealerDetails') if isinstance(item.get('dealerDetails'), dict) else {}
    total = ((item.get('price') or {}).get('total') or {})
    vatable, vat_rate = _apify_vat(item)

    title = str(item.get('title') or '').strip()
    for lead in (item.get('brand'), item.get('model')):
        lead = str(lead or '').strip()
        if lead and title.lower().startswith(lead.lower()):
            title = title[len(lead):].strip()

    condition = str(attributes.get('Vehicle condition') or '').lower()
    registered = str(attributes.get('First Registration') or '').strip()
    power = str(attributes.get('Power') or '')
    kilowatts = re.search(r'(\d+)\s*kW', power, re.IGNORECASE)
    horsepower = re.search(r'(\d+)\s*(?:hp|PS)\b', power, re.IGNORECASE)
    seller = str(dealer.get('sellerType') or '').lower()
    # "Mülhauser Straße 111, DE-47906 Kempen" → Kempen
    city = re.search(r'\b[A-Z]{1,3}-\d{4,5}\s+(.+)$', str(dealer.get('address') or '').strip())

    row = {
        'ad_id': str(item.get('id') or ''),
        'url': item.get('url') or '',
        'make': item.get('brand') or '',
        'model': item.get('model') or '',
        'version': title[:190],
        'model_year': _year_of(registered),
        'first_registration': registered[:16],
        'mileage_km': _first_number(attributes.get('Mileage')),
        'cc': _first_number(attributes.get('Cubic Capacity')),
        'power_kw': int(kilowatts.group(1)) if kilowatts else None,
        'power_hp': int(horsepower.group(1)) if horsepower else None,
        'fuel': str(attributes.get('Fuel') or '')[:32],
        'gearbox': str(attributes.get('Transmission') or '')[:32],
        'colour_exterior': str(attributes.get('Colour') or '')[:64],
        'condition_new': condition.startswith('new'),
        'accident_free': _apify_accident_free(item),      # said so in the advert, or a new car
        'price_gross_eur': total.get('amount') if (total.get('currency') or 'EUR') == 'EUR' else None,
        'vatable': vatable,
        'seller_name': str(dealer.get('name') or '')[:190],
        'seller_type': 'dealer' if 'dealer' in seller else ('private' if 'private' in seller else 'unknown'),
        'seller_city': (city.group(1).strip() if city else '')[:128],
        'country': str(dealer.get('country') or '')[:8],
        'images': [image for image in (item.get('images') or []) if image],
        'features': item.get('features') or [],
        'is_simulated': False,
        'raw': item,
    }
    if vatable:
        row['vat_rate_pct'] = vat_rate
    return row


def _normalised(backend, ad):
    if isinstance(backend, ApifyBackend):
        return _normalise_apify(ad)
    return _normalise(ad, backend.simulated)


def search(backend=None, model_class=None, saloon_only=False, accident_free=False, **kwargs):
    """Search, and return (listings, meta). Never raises for an empty result.

    `backend` forces one for a command (see `get_backend`). `model_class` is a
    class letter ("C" for C-Class) for the backend that cannot be asked for a
    make alone; the others ignore it and the caller narrows the result itself.
    `saloon_only` and `accident_free` are applied by the Apify backend, the one
    that reads the real marketplace.
    """
    backend = get_backend(backend)
    params = build_query(**kwargs)
    payload = backend.search(params, model_class=model_class, saloon_only=saloon_only,
                             accident_free=accident_free)
    ads = payload.get('ads') or payload.get('searchResult', {}).get('ads') or []
    listings = [_normalised(backend, ad) for ad in ads]
    meta = {
        'simulated': backend.simulated,
        'backend': backend.name,
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
    from car_import.services import catalogue

    now = timezone.now()
    created, updated = [], []
    for data in listings:
        ad_id = data.get('ad_id')
        if not ad_id:
            continue
        values = {k: v for k, v in data.items() if k not in ('ad_id', 'make', 'model')}
        # The advert's words become catalogue rows here, once; an unknown make
        # or model is added — a marketplace name is authoritative, not a typo.
        values['brand'], values['car_model'] = catalogue.resolve(data.get('make'), data.get('model'), create=True)
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
    try:
        backend = get_backend()
    except MobileDeError as exc:
        # Nothing to check against is not a reason to flag every car as sold.
        return {'seen': 0, 'gone': 0, 'failed': 0, 'simulated': False, 'skipped': str(exc)}
    if isinstance(backend, ApifyBackend):
        # What follows calls an advert gone when one search does not return it.
        # An Apify search returns a capped handful, so it would flag cars that
        # are still for sale — and bill for the privilege every night.
        return {'seen': 0, 'gone': 0, 'failed': 0, 'simulated': False, 'skipped': 'apify'}
    now = timezone.now()
    gone, seen, failed = 0, 0, 0

    # One search per make/model rather than per row: the API has no documented
    # "fetch one ad by id" endpoint on the search service, so presence in the
    # current result set is what tells us the advert is still up.
    by_group = {}
    for row in rows:
        raw = row.raw if isinstance(row.raw, dict) else {}
        make = raw.get('make') or (row.brand.name if row.brand_id else '')
        model = raw.get('model') or (row.car_model.name if row.car_model_id else '')
        by_group.setdefault((make, model), []).append(row)

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


# ───────────────────────────────────────────────────────────────────────────
# a link the customer pasted
# ───────────────────────────────────────────────────────────────────────────
_MOBILE_DE_LINK = re.compile(r'https?://[^\s]*mobile\.de[^\s]*', re.IGNORECASE)


def ad_id_from_link(text):
    """The advert id inside any mobile.de link — the app's share link
    (m.mobile.de/…/details.html?id=…), the site's (suchen.mobile.de/…?id=…) or
    an /auto-inserat/…/<id>.html page. None when there is no such link."""
    match = _MOBILE_DE_LINK.search(str(text or ''))
    if not match:
        return None
    parts = urllib.parse.urlparse(match.group(0))
    query = urllib.parse.parse_qs(parts.query)
    for key in ('id', 'adId'):
        value = (query.get(key) or [''])[0]
        if value.isdigit():
            return value
    # Up to 16 digits: adverts posted since 2026 carry 14-digit ids.
    tail = re.search(r'/(\d{6,16})(?:\.html)?/?$', parts.path)
    return tail.group(1) if tail else None


def read_advert(link):
    """(listing, how) for a mobile.de link the customer sent.

    `how` is `stored` or `fetched` with a listing, or — with None — why not:
    `not_a_mobile_de_link`, `no_api_access` (the simulator: nothing can open
    the link), `not_found` (the advert is gone) or `mobile_de_error`. Through
    Apify an empty answer is `mobile_de_error`, never `not_found`: a blocked
    run looks the same as a removed advert, and telling a customer their car
    was sold when it was not is the worse mistake.
    """
    from car_import.models import SupplierListing

    ad_id = ad_id_from_link(link)
    if not ad_id:
        return None, 'not_a_mobile_de_link'
    row = (SupplierListing.objects.filter(source='mobile.de', ad_id=ad_id)
           .order_by('-id').first())
    if row is not None and row.still_available and row.price_gross_eur:
        return row, 'stored'
    try:
        backend = get_backend()
    except MobileDeError:
        logger.warning('car_import: no mobile.de source to read advert %s with', ad_id, exc_info=True)
        return None, 'no_api_access'
    try:
        ad = backend.ad(ad_id)
    except MobileDeError:
        logger.warning('car_import: could not read mobile.de advert %s', ad_id, exc_info=True)
        return None, 'mobile_de_error'
    if not ad:
        if backend.simulated:
            return None, 'no_api_access'
        return None, ('not_found' if backend.gone_is_certain else 'mobile_de_error')
    created, updated = import_listings([_normalised(backend, ad)])
    rows = created or updated
    return (rows[0], 'fetched') if rows else (None, 'not_found')
