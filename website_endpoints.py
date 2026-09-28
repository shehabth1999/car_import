# -*- coding: utf-8 -*-
"""The three URLs the company website's backend calls on Genie.

    POST     /api/website/leads      a visitor submitted a form   → CRM lead
    GET|POST /api/website/tracking   "track your car"              → stages JSON
    GET      /api/website/ping       the developer checks the key  → {"ok": true}

Plain Django views, CSRF-exempt: the caller is a server holding the key on the
Website connection screen, not a browser with a session. Every call is logged
in `WebsiteApiLog` (direction "in").
"""
import json

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt


def _body(request):
    """JSON body, or form fields, or query string — whichever the caller used."""
    if request.body and 'json' in (request.content_type or ''):
        try:
            data = json.loads(request.body.decode('utf-8') or '{}')
        except (ValueError, UnicodeDecodeError):
            return None
        return data if isinstance(data, dict) else None
    if request.method == 'POST' and request.POST:
        return {k: v for k, v in request.POST.items()}
    if request.body:
        try:
            data = json.loads(request.body.decode('utf-8') or '{}')
            return data if isinstance(data, dict) else None
        except (ValueError, UnicodeDecodeError):
            pass
    return {k: v for k, v in request.GET.items()}


def _reply(request, path, status, body, data, started, ref=''):
    from car_import.services import website_inbound
    website_inbound.log_in(request, path, status, data, body, started, ref)
    return JsonResponse(body, status=status, json_dumps_params={'ensure_ascii': False})


def _guard(request, path, started, switch):
    """None when the call may proceed, else the error response."""
    from car_import.models import WebsiteConnection
    from car_import.services import website_inbound
    # The rate limit comes FIRST: a caller hammering with wrong keys is limited
    # too, and pays no database query or log row per attempt past the limit.
    if not website_inbound.rate_ok(request, path):
        response = JsonResponse({'message': 'Too Many Attempts.'}, status=429)
        response['Retry-After'] = '60'
        return response
    connection = WebsiteConnection.get()
    if not website_inbound.key_ok(request, connection):
        return _reply(request, path, 401, {'message': 'Unauthenticated.'}, None, started)
    if switch and not getattr(connection, switch):
        return _reply(request, path, 503, {'message': 'This service is switched off in Genie.'}, None, started)
    return None


@csrf_exempt
def leads(request):
    started = timezone.now()
    path = 'api/website/leads'
    if request.method != 'POST':
        return _reply(request, path, 405, {'message': 'The GET method is not supported for this route. '
                                                      'Supported methods: POST.'}, None, started)
    blocked = _guard(request, path, started, 'leads_enabled')
    if blocked is not None:
        return blocked
    data = _body(request)
    if data is None:
        return _reply(request, path, 422, {'message': 'The request body must be a JSON object.',
                                           'errors': {'body': ['The request body must be a JSON object.']}},
                      None, started)
    from car_import.services import website_inbound
    try:
        status, body = website_inbound.receive_lead(data, website_inbound.client_ip(request))
    except Exception:  # noqa: BLE001 — the website must get JSON, never an HTML 500
        import logging
        logging.getLogger(__name__).exception('car_import: website lead intake failed')
        status, body = 500, {'message': 'Server Error.'}
    ref = f"lead:{(body.get('data') or {}).get('lead_id') or ''}" if isinstance(body, dict) else ''
    return _reply(request, path, status, body, data, started, ref)


@csrf_exempt
def tracking(request):
    started = timezone.now()
    path = 'api/website/tracking'
    if request.method not in ('GET', 'POST'):
        return _reply(request, path, 405, {'message': 'Supported methods: GET, POST.'}, None, started)
    blocked = _guard(request, path, started, 'tracking_enabled')
    if blocked is not None:
        return blocked
    data = _body(request) or {}
    from car_import.services import website_inbound
    try:
        status, body = website_inbound.tracking(data.get('chassis_number') or data.get('chassis') or '')
    except Exception:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).exception('car_import: website tracking failed')
        status, body = 500, {'message': 'Server Error.'}
    ref = f"deal:{(body.get('data') or {}).get('reference', '')}" if isinstance(body, dict) and body.get('data') else ''
    return _reply(request, path, status, body, {'chassis_number': data.get('chassis_number')}, started, ref)


@csrf_exempt
def ping(request):
    started = timezone.now()
    path = 'api/website/ping'
    blocked = _guard(request, path, started, None)
    if blocked is not None:
        return blocked
    return _reply(request, path, 200, {'ok': True, 'service': 'Genie ERP',
                                       'time': timezone.now().isoformat()}, None, started)
