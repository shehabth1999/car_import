# -*- coding: utf-8 -*-
"""Which programme a car goes by — decided by its model year and whether it is new.

The owner's rules of 2026-09-30 (two messages the same day):

    current model year, NEW (zero km)  → the customer's OWN initiative if they hold one
                                          (→ Alexandria), else personal import (the better
                                          route without one) → Port Said (105,000 EGP),
                                          its customs stated on the offer
    current model year, USED            → the initiative → Alexandria (55,000 EGP)
    the three model years before it     → the initiative — the company provides one,
      (in 2026: 2023, 2024, 2025)          or the customer brings their own → Alexandria
    older                               → not importable

For a new current-year car whether the customer holds an initiative is the one
question worth asking («بنسأل العميل لو عنده مبادرة»); everything else is read
off the car. The port follows, and so does the block the offer must carry — the
customs figure for a personal import; for an initiative car the USD deposit,
plus the powers-of-attorney fee when the company provides the initiative («سعر
العربية + المبادرة + ثمن التوكيلات + مصاريف الميناء»). On 2026-09-30 a quote
priced from a screenshot carried none of it, and the owner called it wrong.

Every initiative car lands at Alexandria, a new one included («المبادرات بتتبعت
كلها على اسكندرية»); only a personal import goes to Port Said.

The contract runs three months from the second payment on both programmes; the
initiative also needs its prior import approval (الموافقة الاستيرادية المسبقة).
That is the only difference between the two, in the owner's words.
"""
from decimal import Decimal

PERSONAL = 'personal'
INITIATIVE = 'initiative'

#: The port each programme lands at, and so the port fee on the offer.
PORTS = {PERSONAL: 'port_said', INITIATIVE: 'alexandria'}
#: FeeSchedule code of the powers of attorney, charged in USD when the company
#: provides the initiative.
POA_FEE = 'powers_of_attorney'

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
    """The year of `on` (a date), else this year. A form's onchange hands dates
    over as text, which counts as not given."""
    from django.utils import timezone
    year = getattr(on, 'year', None)
    return year if isinstance(year, int) else timezone.localdate().year


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


def port_for(programme, model_year=None, is_new=None, on=None):
    """Port Said for a personal import; Alexandria for EVERY initiative car,
    a new one on the customer's own initiative included (owner, 2026-09-30:
    «المبادرات بتتبعت كلها على اسكندرية»). The other arguments are kept for
    the callers; the programme alone decides."""
    return PORTS.get(programme)


def decide(model_year, is_new=None, has_own_initiative=None, on=None):
    """{'programme', 'port', 'problem', 'why'} for a car.

    `problem` is None when a programme was decided, else one of `year_needed`,
    `condition_needed` (a current-model-year car: new or used decides it),
    `initiative_holder_needed` (a new current-year car: the customer's own
    initiative decides it) and `too_old`.
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
                    'why': (f'A {year} car goes by the initiative when it is used; a new one (zero km) by the '
                            f'customer\'s own initiative or by personal import — which one is it?')}
        if not is_new:
            programme = INITIATIVE
        elif has_own_initiative is None:
            return {'programme': None, 'port': None, 'problem': 'initiative_holder_needed',
                    'why': (f'A new {year} car can come on the customer\'s OWN initiative; without one it is a '
                            f'personal import. Whether they hold an initiative is not known.')}
        else:
            programme = INITIATIVE if has_own_initiative else PERSONAL
    elif year >= now - INITIATIVE_YEARS_BACK:
        programme = INITIATIVE
    else:
        return {'programme': None, 'port': None, 'problem': 'too_old',
                'why': (f'Model {year} is older than the initiative allows: model '
                        f'{now - INITIATIVE_YEARS_BACK} or newer.'),
                'oldest_year': now - INITIATIVE_YEARS_BACK}
    return {'programme': programme, 'port': port_for(programme, year, is_new, on), 'problem': None, 'why': ''}


def poa_usd(programme, own_initiative):
    """The powers-of-attorney fee (USD) when the COMPANY provides the
    initiative — i.e. an initiative car whose customer did not say they bring
    their own. None otherwise, or when the fee table has no row."""
    if programme != INITIATIVE or own_initiative:
        return None
    from car_import.services.pricing import _fee
    return _fee(POA_FEE, None)


def car_model_of(listing=None, vehicle=None, text=''):
    """The catalogue model behind an advert, a car, or the words describing it."""
    if listing is not None and getattr(listing, 'car_model_id', None):
        return listing.car_model
    if vehicle is not None and getattr(vehicle, 'car_model_id', None):
        return vehicle.car_model
    from car_import.services import initiative_values
    return initiative_values.find_model(text) if text else None


def customs_row(car_model, model_year):
    """The customs table's row for a car: its own model year, else the year
    before it — a new car is sold as next year's model from the autumn, and
    the 2027 car IS the 2026 one («موديل 2026 هي هي موديل 2027», the client's
    GM, 2026-10-01, after the assistant refused him a figure three times).
    None when neither year is in the table."""
    if car_model is None or not model_year:
        return None
    from car_import.models import CustomsValuation
    year = int(model_year)
    return (CustomsValuation.in_force(car_model=car_model, model_year__in=[year, year - 1])
            .exclude(value_eur__isnull=True).order_by('-model_year').first())


def customs_eur(car_model, model_year):
    """The customs figure for a personal import — the amount payable (client,
    2026-09-16) — or None when the table has no row for this car."""
    row = customs_row(car_model, model_year)
    return Decimal(row.value_eur) if row is not None else None


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


#: Who gets the initiative's deposit back (owner, 2026-10-07): «قيمة الوديعة
#: مش بتستردها الا لو كنت انت صاحب المبادرة». When the company provides the
#: initiative the customer is not its holder, and nothing comes back to them.
#: Until then the assistant told such a customer the deposit «بترجعلك بعد 5
#: سنين», twice in one chat.
COMPANY_INITIATIVE_SAVING_AR = ('حضرتك بتجيب عربية بسعر أقل من مصر، وبكماليات أعلى، وبحالة الزيرو، '
                                'وعداد قليل.')


def deposit_refund_rule(company_provides):
    """What the assistant may say about getting the deposit back."""
    if company_provides:
        return ('The COMPANY provides this initiative, so the deposit is NOT returned to this customer — only '
                'the initiative\'s holder gets it back. Never say it is returned to them. If they ask who gets '
                'it back or whether they get it back, say exactly: «قيمة الوديعة مش بتستردها حضرتك — بيستردها '
                'صاحب المبادرة بس». Only if they then ask what they save, say exactly: «'
                + COMPANY_INITIATIVE_SAVING_AR + '» — those four points and nothing added.')
    return ('The deposit is returned after 5 years to the initiative\'s HOLDER — to the customer only when the '
            'initiative is their own. Never promise it back to a customer the company provides an initiative to.')


def full_cost_ar(total_eur, egp_due=None, programme='', customs=None, deposits=None, poa=None):
    """Everything the customer pays for the car, each sum in its own currency —
    the text the assistant says when asked for "the price with the initiative".

    The owner, 2026-10-07: after the offer the customer asks to confirm the
    price and the assistant «بيتلخبط وبيقول سعر العربية بس». In the client's
    test chat it said the euro total already held the initiative, then took it
    back, then summed dollars into a figure of its own. The pieces are in three
    currencies and stay three lines; nothing here adds them up."""
    lines = [f'• إجمالي سعر البيع لحد باب البيت (العربية والشحن والمصاريف): {eur(total_eur)}']
    if programme == PERSONAL:
        lines.append(f'• الجمارك والضرايب: {eur(customs)}' if customs is not None else
                     '• الجمارك والضرايب: قيمتها بتتأكد من الشركة قبل التعاقد')
    elif programme == INITIATIVE:
        if deposits:
            lines.append('• قيمة المبادرة (وديعة بالدولار):')
            lines.extend(f'   - {line}' for line in _deposit_lines(deposits))
        else:
            lines.append('• قيمة المبادرة (وديعة بالدولار): بتتأكد من الشركة قبل التعاقد')
        if poa is not None:
            lines.append(f'• ثمن التوكيلات: {usd(poa)}')
    if egp_due:
        lines.append(f'• مصاريف الميناء عند الوصول: {Decimal(str(egp_due)):,.0f} جنيه')
    return '\n'.join(lines)


def _deposit_lines(deposits):
    """One line per tier; the residence is named only where it changes the figure."""
    from car_import.services.initiative_values import REGION_AR, TIER_AR
    lines = []
    for tier in [t for t in TIER_AR if any(r.get('tier') == t for r in deposits)]:
        rows = [r for r in deposits if r.get('tier') == tier]
        if len({str(r['usd']) for r in rows}) == 1:
            lines.append(f'{TIER_AR[tier]}: {usd(rows[0]["usd"])}')
        else:
            lines.append(f'{TIER_AR[tier]}: ' + ' / '.join(
                f'{REGION_AR.get(r.get("region"), r.get("region"))} {usd(r["usd"])}' for r in rows))
    return lines


def full_cost_of_quote(quote):
    """`full_cost_ar` for a stored quotation."""
    return full_cost_ar(quote.total_eur, quote.egp_due_on_arrival, quote.programme,
                        customs=quote.customs_eur, deposits=quote.initiative_deposits,
                        poa=quote.poa_usd)


FULL_COST_RULE = ('When the customer asks for the whole price, the price with the initiative or the customs, '
                  'what they pay in total, or to confirm the price after the offer, say `full_cost_ar` exactly as '
                  'written, as one message. The EUR total does NOT include the initiative value, the customs, the '
                  'powers of attorney or the port fees — never say it does. Never add the currencies together and '
                  'never convert anything to EGP or state an exchange rate yourself.')


def for_agent(programme, port, customs=None, deposits=None, car_model=None, model_year=None, poa=None):
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
                                    'the EUR total. State it exactly. The price is the car + this customs '
                                    'figure + the port fees — say all three.')
        else:
            data['customs'] = None
            data['customs_note'] = (f'Personal import pays customs, but the customs table has no figure for '
                                    f'{car}. A colleague was tagged in the chat to supply it. Say the car '
                                    f'carries customs duties and a colleague is confirming the amount now — '
                                    f'never guess a number, an engine size or a country of origin.')
    elif programme == INITIATIVE:
        if deposits:
            data['initiative_value'] = [{'variant': deposit_label(r), 'year': r['year'],
                                         'deposit_usd': usd(r['usd'])} for r in deposits]
            data['initiative_note'] = ('«قيمة المبادرة» = the USD deposit, paid in dollars, NOT part of the EUR '
                                       'total. It is on the offer; state the figures exactly. Several variants = '
                                       'the tier or residence is not known yet: say them all in one line, do '
                                       'not interrogate. ' + deposit_refund_rule(poa is not None))
        else:
            data['initiative_value'] = None
            data['initiative_note'] = (f'The initiative deposit sheet has no value for {car}. A colleague was '
                                       f'tagged in the chat to supply it. Say a colleague is confirming the '
                                       f'initiative value for this car now — never guess a number.')
        if poa is not None:
            data['powers_of_attorney'] = usd(poa)
            data['price_is'] = ('The company provides the initiative, so the price is: the car (EUR total) + the '
                                'initiative value + the powers of attorney + the port fees. Say all four. If the '
                                'customer brings their OWN initiative, call again with has_own_initiative=true.')
    return data
