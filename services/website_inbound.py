# -*- coding: utf-8 -*-
"""Website → Genie: the lead webhook and the tracking answer.

Both are called by the website's BACKEND (server to server), never by a
visitor's browser, and both carry the one key on the Website connection
screen, in `X-Api-Key` or `Authorization: Bearer`. Replies follow the website
API's own conventions so the developer meets nothing new: `{"data": …}` on
success, `{"message", "errors"}` on a 422.

The tracking answer never contains the customer's name, phone, prices or
payment state: a chassis number is printed on the car, so anyone holding one
can ask.
"""
import hmac
import logging
import re
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

MEDIUM = {
    'vehicle_request': 'Website — Vehicle Request',
    'car_inquiry': 'Website — Car Inquiry',
    'contact': 'Website — Contact Form',
    'other': 'Website — Other',
}
FORM_LABEL_AR = {
    'vehicle_request': 'طلب عربية من الموقع',
    'car_inquiry': 'سؤال عن عربية من الموقع',
    'contact': 'تواصل من الموقع',
    'other': 'طلب من الموقع',
}
DUPLICATE_WINDOW = timedelta(minutes=10)
STATUS_LABEL = {
    'open': {'ar': 'جارية', 'en': 'In progress'},
    'on_hold': {'ar': 'متوقفة مؤقتاً', 'en': 'On hold'},
    'done': {'ar': 'تم التسليم', 'en': 'Delivered'},
}


# ── auth and plumbing ────────────────────────────────────────────────────────
def presented_key(request):
    key = request.headers.get('X-Api-Key') or ''
    if not key:
        auth = request.headers.get('Authorization') or ''
        if auth.lower().startswith('bearer '):
            key = auth[7:]
    return key.strip()


def key_ok(request, connection):
    expected = connection.inbound_api_key or ''
    given = presented_key(request)
    return bool(expected and given) and hmac.compare_digest(given.encode(), expected.encode())


def client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return (forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR', ''))[:64]


def rate_ok(request, bucket, limit=120, window=60):
    from django.core.cache import cache
    key = f'car_import:website_in:{bucket}:{client_ip(request)}:{int(timezone.now().timestamp() // window)}'
    try:
        if cache.add(key, 1, window + 5):
            return True
        return cache.incr(key) <= limit
    except Exception:
        return True


def log_in(request, path, status, request_body, response_body, started, ref=''):
    try:
        from car_import.models import WebsiteApiLog
        from car_import.services.website_api import _short
        WebsiteApiLog.objects.create(
            direction='in', method=request.method, path=path[:255], status_code=status,
            ok=200 <= status < 300, duration_ms=int((timezone.now() - started).total_seconds() * 1000),
            request_body=_short(request_body), response_body=_short(response_body), object_ref=ref[:64])
    except Exception:
        logger.exception('car_import: could not log the inbound website call')


def invalid(errors):
    first = next(iter(errors.values()))[0]
    return 422, {'message': first if len(errors) == 1 else 'The given data was invalid.', 'errors': errors}


# ── the lead webhook ─────────────────────────────────────────────────────────
def _text(data, key, limit=None):
    value = data.get(key)
    if value is None:
        return ''
    value = str(value).strip()
    return value[:limit] if limit else value


def _int(data, key):
    value = data.get(key)
    if value in (None, ''):
        return None
    try:
        return int(str(value).strip())
    except ValueError:
        return 'invalid'


def compose_phone(phone, country_code=''):
    """'+20' + '01025294594' → '201025294594' (canonical, no plus), or '' when unusable."""
    raw = re.sub(r'[^\d+]', '', str(phone or ''))
    code = re.sub(r'\D', '', str(country_code or ''))
    if not raw:
        return ''
    if raw.startswith('+'):
        candidate = raw[1:]
    elif raw.startswith('00'):
        candidate = raw[2:]
    elif code:
        local = raw.lstrip('0')
        candidate = raw if raw.startswith(code) and len(raw) > len(code) + 6 else code + local
    else:
        candidate = raw
    try:
        from modules.whatsapp.utils.phone import normalize_phone
        canonical = normalize_phone(candidate) or normalize_phone(raw, default_region='EG')
    except Exception:
        canonical = None
    return canonical or re.sub(r'\D', '', candidate)


def validate_lead(data):
    errors = {}
    form = _text(data, 'form') or 'vehicle_request'
    if form not in MEDIUM:
        errors['form'] = ['The form must be one of: ' + ', '.join(MEDIUM) + '.']
    name = _text(data, 'name', 190)
    if not name:
        errors['name'] = ['The name field is required.']
    phone = compose_phone(data.get('phone'), data.get('country_code'))
    if not phone:
        errors['phone'] = ['The phone field is required.']
    elif len(phone) < 8 or len(phone) > 15:
        errors['phone'] = ['The phone must be a valid phone number.']
    email = _text(data, 'email', 190)
    if email and not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        errors['email'] = ['The email must be a valid email address.']
    for key in ('brand_id', 'model_id', 'vehicle_id', 'service_id'):
        if _int(data, key) == 'invalid':
            errors[key] = [f'The {key} must be an integer.']
    year = _int(data, 'year')
    if year == 'invalid' or (isinstance(year, int) and not 1900 <= year <= 2100):
        errors['year'] = ['The year must be a year between 1900 and 2100.']
    submission_id = _text(data, 'submission_id')
    if len(submission_id) > 100:
        errors['submission_id'] = ['The submission_id may not be greater than 100 characters.']
    return errors, {'form': form, 'name': name, 'phone': phone, 'email': email,
                    'year': year if isinstance(year, int) else None, 'submission_id': submission_id or None}


def find_or_create_partner(name, phone, email):
    from django.db.models import Q
    from modules.base.models import Partner
    variants = {phone, '+' + phone, '00' + phone}
    tail = phone[-10:]
    partner = (Partner.all_objects.filter(Q(phone__in=variants) | Q(mobile__in=variants)).order_by('id').first()
               or Partner.all_objects.filter(Q(phone__endswith=tail) | Q(mobile__endswith=tail))
               .order_by('id').first())
    if partner is not None:
        changed = []
        if email and not partner.email:
            partner.email = email
            changed.append('email')
        if changed:
            partner.save(update_fields=changed)
        return partner, False
    partner = Partner(name=name[:255], phone=('+' + phone)[:20], email=email or None, customer=True)
    partner.save()
    return partner, True


def _lookup_name(kind, website_id):
    from car_import.models import WebsiteLookup
    if not website_id:
        return ''
    row = WebsiteLookup.objects.filter(kind=kind, website_id=website_id).first()
    return (row.name_en or row.name_ar) if row else f'#{website_id}'


def _car_wanted(data, website_car):
    if website_car is not None:
        return str(website_car)[:255]
    brand = _text(data, 'brand_name') or _lookup_name('brand', _int(data, 'brand_id'))
    model = _text(data, 'model_name') or _lookup_name('model', _int(data, 'model_id'))
    year = _int(data, 'year')
    return ' '.join(str(x) for x in [brand, model, year if isinstance(year, int) else ''] if x)[:255]


def receive_lead(data, ip=''):
    """Validate, deduplicate, create the customer and the lead. Returns (status, body)."""
    from car_import.models import WebsiteCar, WebsiteSubmission

    errors, clean = validate_lead(data)
    if errors:
        return invalid(errors)

    if clean['submission_id']:
        earlier = WebsiteSubmission.objects.filter(submission_id=clean['submission_id']).first()
        if earlier is not None:
            return 200, {'data': _lead_reply(earlier, duplicate=True)}

    vehicle_id = _int(data, 'vehicle_id')
    website_car = WebsiteCar.objects.filter(website_id=vehicle_id).first() if isinstance(vehicle_id, int) else None
    form = clean['form']
    if website_car is not None and form == 'vehicle_request':
        form = 'car_inquiry'
    car_wanted = _car_wanted(data, website_car)
    message = _text(data, 'message') or _text(data, 'details')

    recent = (WebsiteSubmission.objects
              .filter(phone=clean['phone'], form=form, car_wanted=car_wanted,
                      created_at__gte=timezone.now() - DUPLICATE_WINDOW, is_duplicate=False)
              .order_by('-id').first())

    submission = WebsiteSubmission(
        form=form, submission_id=clean['submission_id'], name=clean['name'], phone=clean['phone'],
        email=clean['email'], car_wanted=car_wanted, message=message, website_car=website_car,
        payload={k: v for k, v in data.items() if k not in ('api_key', 'password')}, remote_ip=ip)

    if recent is not None:
        submission.is_duplicate = True
        submission.partner_id, submission.lead_id = recent.partner_id, recent.lead_id
        submission.save()
        return 200, {'data': _lead_reply(submission, duplicate=True)}

    partner, _created = find_or_create_partner(clean['name'], clean['phone'], clean['email'])
    lead = _create_lead(submission, partner, data, clean, website_car)
    submission.partner, submission.lead = partner, lead
    submission.save()
    _tell_sales(submission, lead, partner)
    return 201, {'data': _lead_reply(submission, duplicate=False)}


def _lead_reply(submission, duplicate):
    return {'id': submission.pk, 'lead_id': submission.lead_id, 'duplicate': duplicate,
            'received_at': (submission.created_at or timezone.now()).isoformat()}


def _create_lead(submission, partner, data, clean, website_car):
    from car_import.services import sales_flow
    from car_import.tasks import _owner_users_for_partner
    from modules.crm.services.ad_lead import create_lead_from_external

    owners = _owner_users_for_partner(partner) or []
    lines = [f'{FORM_LABEL_AR[submission.form]} — {timezone.localtime():%Y-%m-%d %H:%M}',
             f'الاسم: {clean["name"]}', f'التليفون: +{clean["phone"]}']
    phone2 = compose_phone(data.get('phone2'), data.get('country_code2'))
    if phone2:
        lines.append(f'تليفون تاني: +{phone2}')
    if clean['email']:
        lines.append(f'الإيميل: {clean["email"]}')
    if submission.car_wanted:
        lines.append(f'العربية: {submission.car_wanted}')
    if website_car is not None:
        lines.append(f'إعلان الموقع رقم {website_car.website_id} — {website_car.price or ""} '
                     f'{getattr(website_car.currency, "code", "")}')
    if submission.message:
        lines += ['', 'الرسالة:', submission.message]
    page = _text(data, 'page_url', 500)
    if page:
        lines.append(f'الصفحة: {page}')

    name = f'{FORM_LABEL_AR[submission.form]} — {submission.car_wanted or clean["name"]}'[:255]
    lead = create_lead_from_external(
        channel='website', partner=partner, branch=sales_flow.default_branch(), name=name,
        email=clean['email'], phone=('+' + clean['phone'])[:20],
        utm_source_name=_text(data, 'utm_source', 100) or 'Website',
        utm_medium_name=_text(data, 'utm_medium', 100) or MEDIUM[submission.form],
        utm_campaign_name=_text(data, 'utm_campaign', 200),
        description='\n'.join(lines), assigned_to=owners[0] if owners else None, is_opportunity=True)
    if lead is None:
        return None
    extra = {}
    wanted = submission.car_wanted
    if clean['year'] and wanted.endswith(str(clean['year'])):
        wanted = wanted[:-len(str(clean['year']))].strip()    # the year has its own field
    if wanted:
        extra['ka_model_wanted'] = wanted[:128]
    if clean['year']:
        extra['ka_model_year_wanted'] = clean['year']
    if extra:
        try:
            type(lead)._base_manager.filter(pk=lead.pk).update(**extra)
        except Exception:
            logger.exception('car_import: could not store the wanted car on lead %s', lead.pk)
    return lead


def _tell_sales(submission, lead, partner):
    try:
        from car_import.tasks import _owner_users_for_partner
        from modules.notifications.services.post_notification import post_notification
        users = _owner_users_for_partner(partner) or []
        partner_ids = [u.partner_id for u in users if getattr(u, 'partner_id', None)]
        if not partner_ids:
            return
        post_notification(
            partner_ids=partner_ids, category='car_import',
            subject=f'{FORM_LABEL_AR[submission.form]}: {submission.name}',
            body=(f'{submission.car_wanted or ""}\n+{submission.phone}\n{submission.message or ""}').strip(),
            url=_lead_url(lead))
    except Exception:
        logger.exception('car_import: could not notify sales about website request %s', submission.pk)


def _lead_url(lead):
    if lead is None:
        return ''
    try:
        from modules.base.models.menu_item import MenuItem
        menu = (MenuItem.objects.filter(key='crm_main_menu_leads').values_list('id', flat=True).first())
    except Exception:
        menu = None
    return f'/genie/{menu}/?model=crm.lead&module=crm&view_type=form&id={lead.pk}' if menu else ''


# ── the tracking answer ──────────────────────────────────────────────────────
def normalise_chassis(value):
    return re.sub(r'[^A-Za-z0-9]', '', str(value or '')).upper()


def _absolute(url):
    from car_import.services.sales_flow import absolute_url
    return absolute_url(url) if url else None


def _stage_dict(stage, state=None, reached_at=None):
    from car_import.models.import_stage import DEFAULT_ICONS
    icon_url = None
    if stage.icon_id:
        try:
            icon_url = _absolute(stage.icon.file.url)
        except Exception:
            icon_url = None
    out = {
        'code': stage.code,
        'sequence': stage.sequence,
        'name': {'ar': stage.name or stage.name_en or '', 'en': stage.name_en or stage.name or ''},
        'icon': stage.icon_class or DEFAULT_ICONS.get(stage.code, 'fa-solid fa-circle'),
        'icon_url': icon_url,
        'color': stage.color or None,
    }
    if state is not None:
        out['state'] = state
        out['reached_at'] = reached_at.isoformat() if reached_at else None
    return out


def tracking(chassis):
    """(status, body) for one chassis number."""
    from car_import.models import CarDeal, ImportStage, StageChangeLog, Vehicle

    vin = normalise_chassis(chassis)
    if not vin:
        return invalid({'chassis_number': ['The chassis number field is required.']})
    if len(vin) < 6:
        return invalid({'chassis_number': ['The chassis number must be at least 6 characters.']})

    vehicle_ids = list(Vehicle.objects.filter(vin__iexact=vin).values_list('id', flat=True))
    deal = (CarDeal.all_objects.filter(vehicle_id__in=vehicle_ids).exclude(state='cancelled')
            .select_related('import_stage', 'vehicle').order_by('-id').first()) if vehicle_ids else None
    if deal is None:
        return 404, {'message': 'No shipment was found for this chassis number.', 'data': None}

    stages = list(ImportStage.objects.filter(show_on_tracking=True).order_by('sequence', 'id'))
    reached = {}
    for log in StageChangeLog.objects.filter(deal=deal).order_by('changed_at', 'id'):
        if log.to_stage_id:
            reached[log.to_stage_id] = log.changed_at
    current = deal.import_stage
    if current is not None and not current.show_on_tracking:
        earlier = [s for s in stages if s.sequence <= current.sequence]
        current = earlier[-1] if earlier else None
    delivered = deal.state == 'done'

    steps, position = [], 0
    for index, stage in enumerate(stages, 1):
        if current is None:
            state = 'upcoming'
        elif stage.pk == current.pk:
            state = 'done' if delivered else 'current'
            position = index
        elif stage.sequence < current.sequence:
            state = 'done'
        else:
            state = 'upcoming'
        steps.append(_stage_dict(stage, state, reached.get(stage.pk)))

    total = len(stages)
    vehicle = deal.vehicle
    data = {
        'chassis_number': vin,
        'reference': deal.name or '',
        'car': {
            'make': getattr(vehicle, 'make', '') or '',
            'model': getattr(vehicle, 'model', '') or '',
            'trim': getattr(vehicle, 'trim', '') or '',
            'year': getattr(vehicle, 'model_year', None),
            'color': getattr(vehicle, 'colour_exterior', '') or '',
        },
        'status': {'code': deal.state, 'label': STATUS_LABEL.get(deal.state, STATUS_LABEL['open'])},
        'current_stage': (dict(_stage_dict(current),
                               since=deal.stage_entered_at.isoformat() if deal.stage_entered_at else None)
                          if current is not None else None),
        'progress': {'step': position, 'total': total,
                     'percent': round(100 * position / total) if total else 0},
        'stages': steps,
        'shipping': {'vessel': deal.vessel or None, 'arrival_port': deal.arrival_port or None,
                     'eta': deal.eta.isoformat() if deal.eta else None},
        'message': {'ar': deal.public_status or (current.name if current else ''),
                    'en': (current.name_en if current else '') or ''},
        'updated_at': (deal.updated_at or timezone.now()).isoformat(),
    }
    return 200, {'data': data}
