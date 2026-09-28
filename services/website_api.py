# -*- coding: utf-8 -*-
"""Genie → website: the client for the website's own API.

Written against the developer's documentation ("Khaled Automobile GmbH API",
Laravel + Sanctum) and checked against the live site on 2026-09-28:

* `POST /login` {email, password, device_name} → {token_type, token, user}.
  Every login mints a NEW token and the site allows 5 logins a minute, so the
  token is kept on the connection row and a login happens only when there is
  none or the site answers 401.
* 60 calls a minute per account. Calls are spaced ~1 s apart and a 429 waits
  for Retry-After once.
* Errors come back as {message, errors}.
* Every id the site accepts is one of ITS ids — hence `WebsiteLookup`.
* A soft-deleted vehicle's serial can never be used again, so Genie never
  deletes: it hides (`status` 0).
* Only `sold` can be set through the status endpoint; a booked car answers 409.
* The gallery endpoint only appends; nothing can be removed through the API.

Every call is written to `WebsiteApiLog`, with the password redacted.
"""
import io
import logging
import re
import time
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

TIMEOUT = 40
MIN_INTERVAL = 1.05           # seconds between calls: stays under 60/min
MAX_IMAGE_BYTES = 3_900_000   # the site allows 4096 KB
GALLERY_BATCH = 10
VIN = re.compile(r'^[A-HJ-NPR-Z0-9]{17}$')
_last_call = [0.0]


class WebsiteApiError(Exception):
    def __init__(self, message, status=None, errors=None):
        super().__init__(message)
        self.status = status
        self.errors = errors or {}

    def __str__(self):
        text = self.args[0] if self.args else 'error'
        if self.errors:
            details = '; '.join(f'{k}: {" ".join(v) if isinstance(v, list) else v}'
                                for k, v in self.errors.items())
            text = f'{text} ({details})'
        return f'{text} [HTTP {self.status}]' if self.status else text


def _conn():
    from car_import.models import WebsiteConnection
    return WebsiteConnection.get()


def _short(body, limit=20000):
    """What is kept in the log: the body, or a summary when it is large."""
    if body is None:
        return None
    try:
        import json
        text = json.dumps(body, ensure_ascii=False, default=str)
    except Exception:
        return {'unserialisable': True}
    if len(text) <= limit:
        return body
    if isinstance(body, dict):
        return {'truncated': True, 'keys': sorted(body.keys())[:40],
                'total': body.get('total'), 'items': len(body.get('data') or []) if isinstance(body.get('data'), list) else None}
    return {'truncated': True, 'size': len(text)}


def _log(method, path, status, ok, started, request_body=None, response_body=None, error='', ref=''):
    try:
        from car_import.models import WebsiteApiLog
        if isinstance(request_body, dict) and 'password' in request_body:
            request_body = dict(request_body, password='***')
        WebsiteApiLog.objects.create(
            direction='out', method=method, path=path[:255], status_code=status, ok=ok,
            duration_ms=int((time.time() - started) * 1000), request_body=_short(request_body),
            response_body=_short(response_body), error=(error or '')[:4000], object_ref=ref[:64])
    except Exception:
        logger.exception('car_import: could not write the website API log')


class WebsiteClient:
    """One session against the website. Reuses the stored token."""

    def __init__(self, connection=None):
        import requests
        self.conn = connection or _conn()
        self.session = requests.Session()
        self.session.headers.update({'Accept': 'application/json', 'User-Agent': 'Genie-ERP/1.0'})

    # ── plumbing ────────────────────────────────────────────────────────────
    def _url(self, path):
        return f'{self.conn.base_url.rstrip("/")}/{path.lstrip("/")}'

    def _space(self):
        wait = MIN_INTERVAL - (time.time() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.time()

    def _save_conn(self, **fields):
        type(self.conn)._base_manager.filter(pk=self.conn.pk).update(**fields)
        for key, value in fields.items():
            setattr(self.conn, key, value)

    def login(self):
        import requests
        if not (self.conn.api_email and self.conn.api_password):
            raise WebsiteApiError('The website login is not set on the Website connection screen.')
        body = {'email': self.conn.api_email, 'password': self.conn.api_password, 'device_name': 'Genie ERP'}
        started = time.time()
        self._space()
        try:
            resp = self.session.post(self._url('login'), json=body, timeout=TIMEOUT)
        except requests.RequestException as exc:
            _log('POST', 'login', None, False, started, body, error=str(exc))
            self._save_conn(last_error=f'login: {exc}'[:2000])
            raise WebsiteApiError(f'The website could not be reached: {exc}') from exc
        payload = self._json(resp)
        ok = resp.status_code == 200 and isinstance(payload, dict) and payload.get('token')
        _log('POST', 'login', resp.status_code, bool(ok), started, body,
             {k: v for k, v in (payload or {}).items() if k != 'token'} if isinstance(payload, dict) else payload)
        if not ok:
            message = (payload or {}).get('message') if isinstance(payload, dict) else None
            self._save_conn(last_error=f'login {resp.status_code}: {message or ""}'[:2000], token='')
            raise WebsiteApiError(message or 'The website refused the login.', resp.status_code,
                                  (payload or {}).get('errors') if isinstance(payload, dict) else None)
        self._save_conn(token=payload['token'], token_obtained_at=timezone.now(),
                        last_ok_at=timezone.now(), last_error='')
        return payload

    @staticmethod
    def _json(resp):
        try:
            return resp.json()
        except ValueError:
            return {'message': (resp.text or '')[:300]} if resp.text else None

    def request(self, method, path, json=None, params=None, files=None, ref='', _retry=True):
        import requests
        if not self.conn.token:
            self.login()
        headers = {'Authorization': f'Bearer {self.conn.token}'}
        started = time.time()
        self._space()
        try:
            resp = self.session.request(method, self._url(path), json=json, params=params, files=files,
                                        headers=headers, timeout=TIMEOUT)
        except requests.RequestException as exc:
            _log(method, path, None, False, started, json, error=str(exc), ref=ref)
            self._save_conn(last_error=f'{method} {path}: {exc}'[:2000])
            raise WebsiteApiError(f'The website could not be reached: {exc}') from exc

        if resp.status_code == 401 and _retry:
            _log(method, path, 401, False, started, json, error='token rejected — logging in again', ref=ref)
            self._save_conn(token='')
            self.login()
            return self.request(method, path, json=json, params=params, files=files, ref=ref, _retry=False)
        if resp.status_code == 429 and _retry:
            wait = min(int(resp.headers.get('Retry-After') or 60), 65)
            _log(method, path, 429, False, started, json, error=f'rate limited — waiting {wait}s', ref=ref)
            time.sleep(wait)
            return self.request(method, path, json=json, params=params, files=files, ref=ref, _retry=False)

        payload = self._json(resp)
        ok = 200 <= resp.status_code < 300
        _log(method, path, resp.status_code, ok, started,
             json if files is None else {'files': [f[1][0] for f in files] if isinstance(files, list) else 'upload'},
             payload, '' if ok else str((payload or {}).get('message') if isinstance(payload, dict) else payload),
             ref=ref)
        if not ok:
            message = (payload or {}).get('message') if isinstance(payload, dict) else None
            self._save_conn(last_error=f'{method} {path} {resp.status_code}: {message or ""}'[:2000])
            raise WebsiteApiError(message or f'The website answered {resp.status_code}.', resp.status_code,
                                  (payload or {}).get('errors') if isinstance(payload, dict) else None)
        self._save_conn(last_ok_at=timezone.now())
        return payload

    # ── reads ───────────────────────────────────────────────────────────────
    def current_user(self):
        return self.request('GET', 'user') or {}

    def input_list(self, endpoint, locale):
        body = self.request('GET', f'inputs/{endpoint}', params={'locale': locale}) or {}
        return body.get('data') or []

    def vehicles(self, per_page=100):
        page = 1
        while True:
            body = self.request('GET', 'vehiclelist', params={'page': page, 'per_page': per_page}) or {}
            rows = body.get('data') or []
            for row in rows:
                yield row
            if not rows or page >= int(body.get('last_page') or page):
                break
            page += 1


# ── lists ────────────────────────────────────────────────────────────────────
def sync_lookups(client=None):
    """Upsert every website list. Entries the site no longer returns are marked inactive."""
    from car_import.models import WebsiteLookup
    client = client or WebsiteClient()
    now = timezone.now()
    counts = {}
    for kind, endpoint in WebsiteLookup.ENDPOINTS.items():
        english = {row['id']: row for row in client.input_list(endpoint, 'en') if 'id' in row}
        arabic = {row['id']: row for row in client.input_list(endpoint, 'ar') if 'id' in row}
        for website_id, row in english.items():
            values = {'name_en': str(row.get('name') or '')[:190],
                      'name_ar': str((arabic.get(website_id) or {}).get('name') or '')[:190],
                      'is_active': True, 'synced_at': now}
            if kind == 'model':
                values['brand_website_id'] = row.get('brand_id')
                values['category_website_id'] = row.get('category_id')
            WebsiteLookup.objects.update_or_create(kind=kind, website_id=website_id, defaults=values)
        WebsiteLookup.objects.filter(kind=kind).exclude(website_id__in=list(english)).update(is_active=False)
        counts[kind] = len(english)
    conn = client.conn
    type(conn)._base_manager.filter(pk=conn.pk).update(lookups_synced_at=now)
    return counts


def _names(value):
    """(english, arabic) from a related object's name — a dict of translations or a plain string."""
    name = (value or {}).get('name') if isinstance(value, dict) else value
    if isinstance(name, dict):
        return str(name.get('en') or name.get('ar') or ''), str(name.get('ar') or '')
    return str(name or ''), ''


def lookup(kind, website_id, related=None):
    """The list entry for a website id; a stub when the site no longer lists it (a deleted brand)."""
    from car_import.models import WebsiteLookup
    if not website_id:
        return None
    try:
        website_id = int(website_id)
    except (TypeError, ValueError):
        return None
    row = WebsiteLookup.objects.filter(kind=kind, website_id=website_id).first()
    if row is not None:
        return row
    en, ar = _names(related)
    values = {'name_en': en[:190], 'name_ar': ar[:190], 'is_active': False}
    if kind == 'model' and isinstance(related, dict):
        values['brand_website_id'] = related.get('brand_id')
        values['category_website_id'] = related.get('category_id')
    return WebsiteLookup.objects.create(kind=kind, website_id=website_id, **values)


# ── website → Genie: the cars ───────────────────────────────────────────────
def _decimal(value):
    try:
        return Decimal(str(value)) if value not in (None, '') else None
    except (InvalidOperation, ValueError):
        return None


def _int(value):
    try:
        return int(float(value)) if value not in (None, '') else None
    except (TypeError, ValueError):
        return None


def review_reasons(car):
    reasons = []
    title = f'{car.title_en} {car.title_ar}'.lower()
    if 'test' in title or 'تجرب' in title:
        reasons.append('عنوان تجربة')
    if not VIN.match(car.serial or ''):
        reasons.append('رقم الشاسيه مش 17 حرف')
    if car.price is not None and car.price < 1000:
        reasons.append('السعر صغير جداً')
    if car.price is not None and not car.is_egypt and car.price > 1_000_000:
        reasons.append('سعر باليورو كبير جداً — غالباً اتكتب بالجنيه')
    return reasons


def _apply_site_row(car, row):
    title = row.get('title') if isinstance(row.get('title'), dict) else {}
    description = row.get('description') if isinstance(row.get('description'), dict) else {}
    car.title_en = str(title.get('en') or '')[:255]
    car.title_ar = str(title.get('ar') or '')[:255]
    car.description_en = str(description.get('en') or '')
    car.description_ar = str(description.get('ar') or '')
    car.serial = str(row.get('serial') or '')[:255]
    car.year = _int(row.get('year'))
    car.price = _decimal(row.get('price'))
    car.location = lookup('country', row.get('car_location'), row.get('carlocation'))
    car.category = lookup('category', row.get('category_id'), row.get('category'))
    car.brand = lookup('brand', row.get('brand_id'), row.get('brand'))
    car.model = lookup('model', row.get('model_id'), row.get('models'))
    car.origin = lookup('origin', row.get('origin_id'), row.get('origin'))
    car.gearbox = lookup('gearbox', row.get('gearbox_id'), row.get('gearbox'))
    car.bodytype = lookup('bodytype', row.get('bodytype_id'), row.get('bodytype'))
    car.engine = lookup('engine', row.get('engine_id'), row.get('engine'))
    car.fuel = lookup('fuel', row.get('fuel_id'), row.get('fules'))
    seat = row.get('seat') or ''
    car.seat = seat if seat in dict(car.SEAT) else ''
    car.distance = _int(row.get('distance'))
    link = str(row.get('video_link') or '')
    car.video_link = link[:255] if link.startswith(('http://', 'https://')) else ''
    car.visible = bool(_int(row.get('status')))
    status = row.get('vehicle_status') or 'avalible'
    car.website_status = status if status in dict(car.WEBSITE_STATUS) else 'avalible'
    car.odoo_id = _int(row.get('odoo_id'))
    car.site_image_url = str(row.get('image_for_web') or '')[:500]
    car.site_gallery_urls = [g.get('image_for_web') for g in (row.get('vehicle_gallery') or [])
                             if isinstance(g, dict) and g.get('image_for_web')]


def _extra_option_ids(row):
    ids = []
    for item in row.get('selected_extra_options') or []:
        if isinstance(item, dict):
            value = item.get('id') or (item.get('pivot') or {}).get('car_extra_option_id')
        else:
            value = item
        value = _int(value)
        if value:
            ids.append(value)
    return ids


def import_cars(mode='all', client=None):
    """Bring the website's cars into Genie.

    mode='all' overwrites Genie's copy with the website's (the first import,
    or a deliberate refresh from the button). mode='new' only adds cars that
    Genie does not have yet — the nightly job, so a car created in the
    website dashboard appears in Genie without undoing anything edited here.
    """
    from car_import.models import WebsiteCar, WebsiteLookup
    client = client or WebsiteClient()
    if not WebsiteLookup.objects.exists():
        sync_lookups(client)
    result = {'created': 0, 'updated': 0, 'review': 0, 'skipped': 0}
    now = timezone.now()
    for row in client.vehicles():
        website_id = _int(row.get('id'))
        if not website_id:
            continue
        car = WebsiteCar.objects.filter(website_id=website_id).first()
        if car is not None and mode == 'new':
            result['skipped'] += 1
            continue
        created = car is None
        car = car or WebsiteCar(website_id=website_id)
        car._from_site = True
        _apply_site_row(car, row)
        reasons = review_reasons(car)
        car.needs_review = bool(reasons)
        car.review_reason = '؛ '.join(reasons)[:255]
        car.sync_state = 'synced'
        car.last_error = ''
        car.last_synced_at = now
        car.save()
        extra = list(WebsiteLookup.objects.filter(kind='extra_option', website_id__in=_extra_option_ids(row)))
        car.extra_options.set(extra)
        result['created' if created else 'updated'] += 1
        result['review'] += int(car.needs_review)
    conn = client.conn
    type(conn)._base_manager.filter(pk=conn.pk).update(cars_imported_at=now)
    return result


# ── Genie → website: one car ─────────────────────────────────────────────────
REQUIRED = [('title', 'العنوان'), ('serial', 'رقم الشاسيه'), ('year', 'سنة الموديل'), ('price', 'السعر'),
            ('category', 'الفئة'), ('brand', 'الماركة'), ('model', 'الموديل'), ('gearbox', 'الفتيس'),
            ('bodytype', 'شكل العربية'), ('engine', 'الموتور'), ('fuel', 'الوقود'),
            ('location', 'مكان العربية')]


def build_payload(car):
    """(payload, missing) — the JSON the website's create/update expects."""
    title = {k: v for k, v in (('en', car.title_en), ('ar', car.title_ar)) if v}
    present = {
        'title': bool(title), 'serial': len(car.serial or '') >= 2, 'year': bool(car.year),
        'price': car.price is not None, 'category': bool(car.category_id), 'brand': bool(car.brand_id),
        'model': bool(car.model_id), 'gearbox': bool(car.gearbox_id), 'bodytype': bool(car.bodytype_id),
        'engine': bool(car.engine_id), 'fuel': bool(car.fuel_id), 'location': bool(car.location_id),
    }
    missing = [label for key, label in REQUIRED if not present[key]]
    if missing:
        return None, missing
    payload = {
        'title': title,
        'serial': car.serial,
        'year': car.year,
        'price': float(car.price),
        'category_id': car.category.website_id,
        'brand_id': car.brand.website_id,
        'model_id': car.model.website_id,
        'gearbox_id': car.gearbox.website_id,
        'bodytype_id': car.bodytype.website_id,
        'engine_id': car.engine.website_id,
        'fuel_id': car.fuel.website_id,
        'car_location': car.location.website_id,
        'status': 1 if car.visible else 0,
        'extra_options': sorted(car.extra_options.filter(kind='extra_option').values_list('website_id', flat=True)),
    }
    description = {k: v for k, v in (('en', car.description_en), ('ar', car.description_ar)) if v}
    if description:
        payload['description'] = description
    if car.origin_id:
        payload['origin_id'] = car.origin.website_id
    if car.distance is not None:
        payload['distance'] = car.distance
    if car.seat:
        payload['seat'] = car.seat
    payload['video_link'] = car.video_link or None
    return payload, []


def _set_state(car, **fields):
    type(car)._base_manager.filter(pk=car.pk).update(**fields)
    for key, value in fields.items():
        setattr(car, key, value)


def _disabled():
    return {'ok': False, 'error': 'الإرسال للموقع مقفول (شاشة ربط الموقع ← «إرسال التعديلات للموقع»).'}


def push_car(car, client=None):
    """Create or update the car on the website, then its photos. Never raises."""
    conn = _conn()
    if not conn.push_enabled:
        _set_state(car, last_error=_disabled()['error'])
        return _disabled()
    payload, missing = build_payload(car)
    if missing:
        error = 'ناقص قبل الإرسال: ' + '، '.join(missing)
        _set_state(car, sync_state='error', last_error=error)
        return {'ok': False, 'error': error}
    client = client or WebsiteClient(conn)
    ref = f'website_car:{car.pk}'
    try:
        if car.website_id:
            body = client.request('PATCH', f'vehicles/{car.website_id}', json=payload, ref=ref) or {}
        else:
            body = client.request('POST', 'vehicles', json=payload, ref=ref) or {}
        data = body.get('data') or {}
        updates = {'sync_state': 'synced', 'last_error': '', 'last_synced_at': timezone.now()}
        if data.get('id'):
            updates['website_id'] = int(data['id'])
        if data.get('vehicle_status') in dict(car.WEBSITE_STATUS):
            updates['website_status'] = data['vehicle_status']
        if data.get('image_for_web'):
            updates['site_image_url'] = str(data['image_for_web'])[:500]
        _set_state(car, **updates)
        _push_photos(car, client, ref)
        return {'ok': True, 'website_id': car.website_id}
    except WebsiteApiError as exc:
        _set_state(car, sync_state='error', last_error=str(exc)[:2000])
        return {'ok': False, 'error': str(exc)}
    except Exception as exc:  # noqa: BLE001 — a bug must not look like a network error
        logger.exception('car_import: pushing website car %s failed', car.pk)
        _set_state(car, sync_state='error', last_error=f'{type(exc).__name__}: {exc}'[:2000])
        return {'ok': False, 'error': str(exc)}


def _image_file(attachment):
    """(filename, bytes, mime) under the site's 4 MB limit, as JPEG/PNG/WEBP."""
    attachment.file.open('rb')
    try:
        raw = attachment.file.read()
    finally:
        attachment.file.close()
    mime = (attachment.mime_type or '').lower()
    name = attachment.name or 'photo.jpg'
    if len(raw) <= MAX_IMAGE_BYTES and mime in ('image/jpeg', 'image/jpg', 'image/png', 'image/webp'):
        return name, raw, mime
    from PIL import Image
    image = Image.open(io.BytesIO(raw))
    image = image.convert('RGB')
    image.thumbnail((2560, 2560))
    for quality in (86, 78, 70, 60, 50):
        out = io.BytesIO()
        image.save(out, format='JPEG', quality=quality, optimize=True)
        if out.tell() <= MAX_IMAGE_BYTES:
            break
    base = name.rsplit('.', 1)[0] or 'photo'
    return f'{base}.jpg', out.getvalue(), 'image/jpeg'


def _push_photos(car, client, ref):
    if not car.website_id:
        return
    if car.main_image_id and car.main_image_id != car.sent_main_image_id:
        name, data, mime = _image_file(car.main_image)
        body = client.request('POST', f'vehicles/{car.website_id}/image', files=[('img', (name, data, mime))],
                              ref=ref) or {}
        url = (body.get('data') or {}).get('image_for_web')
        _set_state(car, sent_main_image_id=car.main_image_id,
                   **({'site_image_url': str(url)[:500]} if url else {}))
    sent = set(car.sent_gallery_ids or [])
    fresh = [a for a in car.gallery.all().order_by('id') if a.pk not in sent]
    for start in range(0, len(fresh), GALLERY_BATCH):
        batch = fresh[start:start + GALLERY_BATCH]
        files = []
        for attachment in batch:
            name, data, mime = _image_file(attachment)
            files.append(('images[]', (name, data, mime)))
        body = client.request('POST', f'vehicles/{car.website_id}/gallery', files=files, ref=ref) or {}
        urls = [row.get('image_for_web') for row in (body.get('data') or []) if isinstance(row, dict)]
        sent |= {a.pk for a in batch}
        _set_state(car, sent_gallery_ids=sorted(sent),
                   site_gallery_urls=list(car.site_gallery_urls or []) + [u for u in urls if u])


def mark_sold(car, client=None):
    """Tell the website the car is sold. The website cannot reverse this."""
    if not _conn().push_enabled:
        return _disabled()
    if not car.website_id:
        return {'ok': False, 'error': 'العربية دي مش على الموقع.'}
    if car.website_status == 'sold':
        return {'ok': True}
    client = client or WebsiteClient()
    try:
        client.request('PATCH', f'vehicles/{car.website_id}/status', json={'vehicle_status': 'sold'},
                       ref=f'website_car:{car.pk}')
    except WebsiteApiError as exc:
        error = ('العربية محجوزة على الموقع — الموقع مش بيسمح تتعلّم «اتباعت».' if exc.status == 409 else str(exc))
        _set_state(car, last_error=error[:2000])
        return {'ok': False, 'error': error}
    _set_state(car, website_status='sold', last_error='', last_synced_at=timezone.now())
    return {'ok': True}


# ── glue ─────────────────────────────────────────────────────────────────────
def schedule_push(pk):
    """Send a changed car a few seconds after the save commits, once."""
    if not _conn().push_enabled:
        return
    from django.core.cache import cache
    if not cache.add(f'car_import:website_push:{pk}', 1, timeout=20):
        return
    from car_import.tasks import push_website_car
    transaction.on_commit(lambda: push_website_car.apply_async((pk,), countdown=8))


def on_deal_saved(deal):
    """A deal on a website car is paid (or delivered): the car is sold on the website."""
    if not deal.vehicle_id:
        return
    if deal.state != 'done' and deal.payment_state not in ('deposit_paid', 'fully_paid'):
        return
    from car_import.models import WebsiteCar
    ids = list(WebsiteCar.objects.filter(vehicle_id=deal.vehicle_id, website_id__isnull=False)
               .exclude(website_status='sold').values_list('id', flat=True))
    if not ids or not _conn().push_enabled:
        return
    from car_import.tasks import website_mark_sold
    for pk in ids:
        transaction.on_commit(lambda pk=pk: website_mark_sold.delay(pk))


def _norm(text):
    return re.sub(r'[^a-z0-9؀-ۿ]', '', str(text or '').lower())


def match_lookup(kind, *texts, brand=None):
    """The list entry whose name (or alias) matches one of these texts."""
    from car_import.models import WebsiteLookup
    wanted = {_norm(t) for t in texts if t}
    if not wanted:
        return None
    rows = WebsiteLookup.objects.filter(kind=kind, is_active=True)
    if brand is not None and kind == 'model':
        rows = rows.filter(brand_website_id=brand.website_id)
    for row in rows:
        if wanted & {_norm(n) for n in row.names()}:
            return row
    for row in rows:                       # "Mercedes" inside "Mercedes-Benz"
        names = {_norm(n) for n in row.names()}
        if any(w and n and (w.startswith(n) or n.startswith(w)) for w in wanted for n in names):
            return row
    return None


def nearest_engine(cc):
    from car_import.models import WebsiteLookup
    if not cc:
        return None
    best, gap = None, None
    for row in WebsiteLookup.objects.filter(kind='engine', is_active=True):
        digits = re.findall(r'\d{3,4}', row.name_en or '')
        if not digits:
            continue
        diff = abs(int(digits[0]) - int(cc))
        if gap is None or diff < gap or (diff == gap and 'turbo' in (row.name_en or '').lower()):
            best, gap = row, diff
    return best


def car_from_vehicle(vehicle):
    """A draft website car prefilled from a Genie car. Unmatched lists stay empty for a person."""
    from car_import.models import WebsiteCar, WebsiteLookup
    existing = WebsiteCar.objects.filter(vehicle=vehicle).order_by('-id').first()
    if existing is not None:
        return existing
    brand = match_lookup('brand', vehicle.make)
    body_names = {'sedan': 'sedan', 'hatchback': 'hatchback', 'suv': 'SUV', 'coupe': 'coupe',
                  'convertible': 'convertible', 'estate': 'station', 'van': 'van'}
    car = WebsiteCar(
        vehicle=vehicle,
        title_en=' '.join(str(x) for x in [vehicle.make, vehicle.model, vehicle.trim, vehicle.model_year] if x)[:255],
        serial=vehicle.vin or '',
        year=vehicle.model_year,
        price=vehicle.price_gross_eur,
        distance=vehicle.mileage_km,
        brand=brand,
        model=match_lookup('model', vehicle.model, f'{vehicle.model} {vehicle.trim or ""}', brand=brand) if brand else None,
        category=WebsiteLookup.objects.filter(kind='category', is_active=True).order_by('website_id').first(),
        fuel=match_lookup('fuel', vehicle.fuel, {'benzin': 'Petrol', 'petrol': 'Petrol', 'gasoline': 'Petrol',
                                                 'diesel': 'Diesel'}.get(str(vehicle.fuel or '').lower())),
        gearbox=match_lookup('gearbox', vehicle.gearbox, 'automatic' if 'auto' in str(vehicle.gearbox or '').lower() else None),
        bodytype=match_lookup('bodytype', body_names.get(str(getattr(vehicle, 'body', '') or '').lower(), getattr(vehicle, 'body', ''))),
        engine=nearest_engine(vehicle.cc),
        location=WebsiteLookup.objects.filter(kind='country', website_id=2).first(),   # Germany
        origin=match_lookup('origin', vehicle.country_built),
        visible=False,
    )
    car.save()
    return car


def ensure_vehicle(car):
    """The Genie car record behind a website car, created from the website data when missing."""
    from car_import.models import Vehicle
    if car.vehicle_id:
        return car.vehicle
    vin = car.serial if VIN.match(car.serial or '') else ''
    vehicle = Vehicle.objects.filter(vin=vin).first() if vin else None
    if vehicle is None:
        distance = car.distance or 0
        vehicle = Vehicle(
            make=(car.brand.name_en if car.brand_id else '') or '—',
            model=(car.model.name_en if car.model_id else '') or '—',
            model_year=car.year, vin=vin, mileage_km=car.distance,
            fuel=(car.fuel.name_en if car.fuel_id else '')[:32],
            gearbox=(car.gearbox.name_en if car.gearbox_id else '')[:32],
            condition='zero' if distance < 50 else 'used',
            price_gross_eur=None if car.is_egypt else car.price,
            notes=f'من الموقع — عربية رقم {car.website_id}.')
        vehicle.save()
    WebsiteCarModel = type(car)
    WebsiteCarModel._base_manager.filter(pk=car.pk).update(vehicle=vehicle)
    car.vehicle = vehicle
    return vehicle
