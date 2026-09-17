# -*- coding: utf-8 -*-
"""Pages the extension serves itself — mounted at runtime by `patches.apply_url_patches`.

The calculator: the client's spreadsheet as a screen, for the moment a
salesman has a customer on the phone and no quotation yet. It runs the SAME
engine the quotation form runs (`Quote._live_values`, the onchange behind the
form) — nothing here computes a price; it asks the model to.
"""
import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

SALES_GROUPS = ['car_import.sales_agent', 'car_import.sales_manager', 'car_import.management']

INPUT_FIELDS = ('gross_price_eur', 'vat_rate_pct', 'with_eur1', 'shipping_type', 'port',
                'collect_from_showroom', 'admin_fee_discount_eur', 'fx_rate_egp', 'paid_eur')


def _may_use(user):
    if getattr(user, 'is_superuser', False):
        return True
    has_groups = getattr(user, 'has_groups', None)
    return bool(has_groups and has_groups(SALES_GROUPS))


def _decimal(value, default=None):
    if value in (None, '', False):
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return default


def _quote_from(payload):
    """An unsaved Quote carrying the page's inputs — the engine's argument."""
    from car_import.models import Quote
    return Quote(
        gross_price_eur=_decimal(payload.get('gross_price_eur')),
        vat_rate_pct=_decimal(payload.get('vat_rate_pct'), Decimal('19')),
        with_eur1=bool(payload.get('with_eur1')),
        shipping_type=(payload.get('shipping_type') or '')
        if payload.get('shipping_type') in ('', 'vip_roro', 'container') else '',
        port=payload.get('port') if payload.get('port') in ('alexandria', 'port_said') else 'alexandria',
        collect_from_showroom=bool(payload.get('collect_from_showroom')),
        admin_fee_discount_eur=_decimal(payload.get('admin_fee_discount_eur'), Decimal(0)),
        fx_rate_egp=_decimal(payload.get('fx_rate_egp')),
        paid_eur=_decimal(payload.get('paid_eur'), Decimal(0)),
    )


@login_required
def calculator_page(request):
    if not _may_use(request.user):
        return render(request, 'car_import/calculator.html', {'forbidden': True}, status=403)
    from car_import.models import FxReference, Quote
    latest_fx = FxReference.objects.order_by('-effective_from', '-id').first()
    return render(request, 'car_import/calculator.html', {
        'forbidden': False,
        'shipping_types': [(k or 'standard', str(v)) for k, v in Quote.SHIPPING_TYPE],
        'ports': [(k, str(v)) for k, v in Quote.PORT],
        'fx_rate': float(latest_fx.rate) if latest_fx else '',
        'fx_note': (f'سعر الإدارة يوم {latest_fx.effective_from:%Y-%m-%d}' if latest_fx and latest_fx.effective_from
                    else 'مفيش سعر صرف منشور — اكتب سعر اليوم لو عايز رقم بالجنيه'),
        'user_name': getattr(request.user, 'name', '') or getattr(request.user, 'email', ''),
    })


@login_required
@require_POST
def calculator_compute(request):
    """The engine, as JSON. Same call as the quotation form's onchange."""
    if not _may_use(request.user):
        return JsonResponse({'error': 'forbidden'}, status=403)
    try:
        payload = json.loads(request.body or b'{}')
    except ValueError:
        return JsonResponse({'error': 'bad json'}, status=400)
    quote = _quote_from(payload)
    result = quote._live_values()
    values = result['value']
    values['pricing_error'] = quote.pricing_error or ''
    return JsonResponse({'value': values})


@login_required
@require_POST
def calculator_save(request):
    """Freeze what is on screen as a quotation, and open it."""
    if not _may_use(request.user):
        return JsonResponse({'error': 'forbidden'}, status=403)
    try:
        payload = json.loads(request.body or b'{}')
    except ValueError:
        return JsonResponse({'error': 'bad json'}, status=400)
    quote = _quote_from(payload)
    if not quote.gross_price_eur:
        return JsonResponse({'error': 'اكتب السعر الأول'}, status=400)
    quote.assigned_to = request.user
    from car_import.services import currencies
    quote.currency = currencies.eur()
    try:
        quote.save()
    except Exception as exc:  # a ValidationError from pre_save is the useful case
        messages = getattr(exc, 'messages', None) or [str(exc)]
        return JsonResponse({'error': ' '.join(str(m) for m in messages)}, status=400)
    from modules.base.models.menu_item import MenuItem
    menu = MenuItem.objects.filter(key='car_import_menu_quotes').values_list('id', flat=True).first()
    url = (f'/genie/{menu}/?model=car_import.quote&module=car_import&view_type=form&id={quote.pk}'
           if menu else '/genie/apps/')
    return JsonResponse({'url': url, 'name': quote.name})
