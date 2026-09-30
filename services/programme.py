# -*- coding: utf-8 -*-
"""Which programme a car goes by — decided by its model year and whether it is new.

The owner's rule of 2026-09-30, and it replaces «المبادرة بتسمح بزيرو موديل السنة»:

    current model year, NEW (zero km)  → personal import only → Port Said (105,000 EGP)
                                          → customs duties, stated on the offer
    current model year, USED            → the initiative → Alexandria (55,000 EGP)
    the three model years before it     → the initiative — the company provides one,
      (in 2026: 2023, 2024, 2025)          or the customer brings their own → Alexandria
    older                               → not importable

So the programme is not a question for the customer and not a choice for the
model: it is read off the car. The port follows it, and so does the block the
offer must carry — the customs figure for a personal import, the initiative's
USD deposit for an initiative car. On 2026-09-30 a quote priced from a
screenshot carried neither, and the owner called the quote wrong.

The contract runs three months from the second payment on both programmes; the
initiative also needs its prior import approval (الموافقة الاستيرادية المسبقة).
That is the only difference between the two, in the owner's words.
"""
from decimal import Decimal

PERSONAL = 'personal'
INITIATIVE = 'initiative'

#: The port each programme lands at, and so the port fee on the offer.
PORTS = {PERSONAL: 'port_said', INITIATIVE: 'alexandria'}

PROGRAMME_AR = {PERSONAL: 'استيراد شخصي', INITIATIVE: 'مبادرة'}
PORT_AR = {'port_said': 'ميناء بورسعيد', 'alexandria': 'ميناء الإسكندرية'}

#: An advert under this is a new car when it does not say so itself.
NEW_CAR_MAX_KM = 100

INITIATIVE_YEARS_BACK = 3


def contract_term_ar(programme):
    """The contract's duration, as the owner states it (2026-09-30)."""
    text = 'مدة التعاقد 3 شهور من الدفعة التانية'
    if programme == INITIATIVE:
        text += '، وبشرط وجود موافقة المبادرة (الموافقة الاستيرادية المسبقة)'
    return text + '.'


def current_year(on=None):
    from django.utils import timezone
    return (on or timezone.localdate()).year


def is_new_listing(listing):
    """True / False from the advert itself; None when it does not say."""
    if listing is None:
        return None
    if getattr(listing, 'condition_new', None):
        return True
    mileage = getattr(listing, 'mileage_km', None)
    if mileage is None:
        return None
    return mileage < NEW_CAR_MAX_KM


def normalise_condition(value):
    text = str(value or '').strip().lower()
    if text in ('new', 'zero', 'زيرو', 'جديدة', 'جديد'):
        return True
    if text in ('used', 'مستعملة', 'مستعمل'):
        return False
    return None


def decide(model_year, is_new=None, on=None):
    """{'programme', 'port', 'problem', 'why'} for a car.

    `problem` is None when a programme was decided, else one of `year_needed`,
    `condition_needed` (a current-model-year car: new or used decides it) and
    `too_old`.
    """
    now = current_year(on)
    try:
        year = int(model_year) if model_year else None
    except (TypeError, ValueError):
        year = None
    if not year:
        return {'programme': None, 'port': None, 'problem': 'year_needed',
                'why': 'The model year decides the programme and it is not known.'}
    if year >= now:
        if is_new is None:
            return {'programme': None, 'port': None, 'problem': 'condition_needed',
                    'why': (f'A {year} car goes by personal import when it is new (zero km) and by the '
                            f'initiative when it is used — which one is it?')}
        programme = PERSONAL if is_new else INITIATIVE
    elif year >= now - INITIATIVE_YEARS_BACK:
        programme = INITIATIVE
    else:
        return {'programme': None, 'port': None, 'problem': 'too_old',
                'why': (f'Model {year} is older than the initiative allows: model '
                        f'{now - INITIATIVE_YEARS_BACK} or newer.'),
                'oldest_year': now - INITIATIVE_YEARS_BACK}
    return {'programme': programme, 'port': PORTS[programme], 'problem': None, 'why': ''}


def car_model_of(listing=None, vehicle=None, text=''):
    """The catalogue model behind an advert, a car, or the words describing it."""
    if listing is not None and getattr(listing, 'car_model_id', None):
        return listing.car_model
    if vehicle is not None and getattr(vehicle, 'car_model_id', None):
        return vehicle.car_model
    from car_import.services import initiative_values
    return initiative_values.find_model(text) if text else None


def customs_eur(car_model, model_year):
    """The customs figure for a personal import — the amount payable (client,
    2026-09-16) — or None when the table has no row for this car."""
    if car_model is None or not model_year:
        return None
    from car_import.models import CustomsValuation
    row = CustomsValuation.in_force(car_model=car_model, model_year=int(model_year)).first()
    return Decimal(row.value_eur) if row is not None and row.value_eur is not None else None


def initiative_deposits(car_model, model_year, tier=None, region=None):
    """[{'year', 'tier', 'region', 'usd'}] from the owner's deposit sheet.

    Tier and region narrow it only when known; otherwise every variant goes on
    the offer (the owner: never interrogate — say the full and medium figures,
    inside and outside Europe)."""
    if car_model is None or not model_year:
        return []
    from car_import.services import initiative_values
    rows = initiative_values.rows(car_model, int(model_year),
                                  initiative_values.normalise_tier(tier),
                                  initiative_values.normalise_region(region))
    return [{'year': r.model_year, 'tier': r.tier, 'region': r.region, 'usd': str(r.deposit_usd)}
            for r in rows]


def filter_of(deposits):
    """(tier, region) the stored rows were narrowed to — (None, None) when they
    carry every variant. Lets a recalculation keep what the customer said."""
    tiers = {row.get('tier') for row in deposits or []}
    regions = {row.get('region') for row in deposits or []}
    return (next(iter(tiers)) if len(tiers) == 1 else None,
            next(iter(regions)) if len(regions) == 1 else None)


def deposit_label(row):
    from car_import.services.initiative_values import REGION_AR, TIER_AR
    return f"{TIER_AR.get(row.get('tier'), row.get('tier'))} — {REGION_AR.get(row.get('region'), row.get('region'))}"


def usd(value):
    return f'{Decimal(str(value)):,.0f} $'


def eur(value):
    text = f'{Decimal(str(value)):,.2f}'
    return f'{text[:-3] if text.endswith(".00") else text} €'


def for_agent(programme, port, customs=None, deposits=None, car_model=None, model_year=None):
    """What the assistant is told to say about the programme, in one block."""
    data = {
        'programme': PROGRAMME_AR.get(programme, programme),
        'port': PORT_AR.get(port, port),
        'contract_term': contract_term_ar(programme),
    }
    car = f'{car_model or "the car"} {model_year or ""}'.strip()
    if programme == PERSONAL:
        if customs is not None:
            data['customs'] = eur(customs)
            data['customs_note'] = ('Personal import: this customs figure is on the offer and is NOT part of '
                                    'the EUR total. State it exactly.')
        else:
            data['customs'] = None
            data['customs_note'] = (f'Personal import pays customs, but the customs table has no figure for '
                                    f'{car}. Say the car carries customs duties and a colleague confirms the '
                                    f'amount before contracting — never guess a number.')
    elif programme == INITIATIVE:
        if deposits:
            data['initiative_value'] = [{'variant': deposit_label(r), 'year': r['year'],
                                         'deposit_usd': usd(r['usd'])} for r in deposits]
            data['initiative_note'] = ('«قيمة المبادرة» = the USD deposit, paid in dollars and returned after 5 '
                                       'years, NOT part of the EUR total. It is on the offer; state the figures '
                                       'exactly. Several variants = the tier or residence is not known yet: say '
                                       'them all in one line, do not interrogate.')
        else:
            data['initiative_value'] = None
            data['initiative_note'] = (f'The initiative deposit sheet has no value for {car}. Say the initiative '
                                       f'value for this car is confirmed by a colleague — never guess a number.')
    return data
