# -*- coding: utf-8 -*-
"""The initiative's USD deposit for a car — «قيمة المبادرة» = «قيمة الوديعة».

The figures are the owner's own workbook («مبادرة المصريين بالخارج - قيم الودائع
الدولارية»), loaded into `DepositTier` by `load_official_values`. The sheet has
one axis per thing that changes the number: the model, the model year, the
tier (full / medium) and the region (inside / outside Europe). Nothing else —
colour, options, mileage — moves it.

Until 2026-09-29 no tool read this table, so the assistant answered "what is
the initiative value?" by interviewing the customer about sunroofs and colours
and then saying it had no access to the sheet. The owner's instruction: look it
up and say one number («المطلوب الدخول على شيت وكتابه رقم محدد»).
"""
import re

TIER_AR = {'full': 'فئة كاملة', 'medium': 'فئة متوسطة'}
REGION_AR = {'europe': 'داخل أوروبا', 'outside': 'خارج أوروبا'}

_ARABIC_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')
_TIER_WORDS = {'full': ('full', 'كامل', 'كاملة', 'فل'), 'medium': ('medium', 'mid', 'متوسط', 'متوسطة')}
# Outside first: «خارج أوروبا» also contains «أوروبا».
_REGION_WORDS = {'outside': ('outside', 'خارج', 'gulf', 'خليج'),
                 'europe': ('europe', 'eu', 'اوروبا', 'أوروبا', 'داخل')}


def _pick(value, words):
    text = str(value or '').strip().lower()
    for key, spellings in words.items():
        if text and any(s in text for s in spellings):
            return key
    return None


def year_in(text):
    match = re.search(r'\b(19|20)\d\d\b', str(text or '').translate(_ARABIC_DIGITS))
    return int(match.group(0)) if match else None


#: Customers spell Mercedes classes out in Arabic letters («سي 180», «جي ال سي
#: 200»). Longest first, so «جي ال سي» is not read as «سي».
_ARABIC_CLASS_NAMES = [
    ('جي ال اي', 'GLE'), ('جي ال إي', 'GLE'), ('جي ال سي', 'GLC'), ('جي ال ايه', 'GLA'),
    ('جي ال اية', 'GLA'), ('جي ال بي', 'GLB'), ('جي ال اس', 'GLS'), ('سي ال ايه', 'CLA'),
    ('سي ال اية', 'CLA'), ('سي ال اي', 'CLE'), ('سي ال إي', 'CLE'), ('اي', 'E'), ('إي', 'E'),
    ('سي', 'C'), ('اس', 'S'), ('إس', 'S'), ('ايه', 'A'), ('اية', 'A'), ('إيه', 'A'), ('بي', 'B'),
]


def _latin_classes(text):
    words = str(text or '').split()
    out, i = [], 0
    while i < len(words):
        for arabic, latin in _ARABIC_CLASS_NAMES:
            size = len(arabic.split())
            if ' '.join(words[i:i + size]) == arabic:
                out.append(latin)
                i += size
                break
        else:
            out.append(words[i])
            i += 1
    return ' '.join(out)


def find_model(text):
    """The catalogue model a customer's words name ("E200", "مرسيدس سي 180")."""
    from car_import.models import CarModel
    from car_import.services import catalogue

    text = _latin_classes(text)
    brand, car_model = catalogue.parse(text)
    if car_model is not None:
        return car_model
    words = [w for w in re.split(r'[\s,/|،]+', str(text or '')) if w and not year_in(w)]
    # "GLC 300 موديل 2026 زيرو": the Arabic around a Latin model name hid it
    # (live 2026-09-30 — the offer said the sheet had no value). Model names
    # are Latin letters and digits, so try those alone before gluing.
    latin = [w for w in words if re.search(r'[A-Za-z0-9]', w)]
    candidates = ([' '.join(latin), ''.join(latin)] if latin and len(latin) < len(words) else []) \
        + [''.join(words)]
    for candidate in candidates:
        if not candidate:
            continue
        # "C 180" / "c180": the words glued together, then a loose match.
        brand, car_model = catalogue.parse(candidate)
        if car_model is not None:
            return car_model
        hits = [m for m in CarModel.objects.all()
                if catalogue.norm(candidate) in {catalogue.norm(n) for n in m.names()}]
        if len(hits) == 1:
            return hits[0]
    return None


def rows(car_model, year=None, tier=None, region=None):
    from car_import.models import DepositTier
    filters = {'car_model': car_model}
    if year:
        filters['model_year'] = int(year)
    if tier:
        filters['tier'] = tier
    if region:
        filters['region'] = region
    return list(DepositTier.in_force(**filters).order_by('model_year', 'tier', 'region'))


def _usd(value):
    return f'{value:,.0f} $'


def lookup(model_text, year=None, tier=None, region=None):
    """What the tool returns: every matching figure, labelled in Arabic."""
    from car_import.models import CarModel, DepositTier

    year = int(year) if str(year or '').strip().isdigit() else year_in(model_text)
    tier, region = normalise_tier(tier), normalise_region(region)

    car_model = find_model(model_text)
    if car_model is None:
        token = re.sub(r'\s+', '', re.sub(r'\b(19|20)\d\d\b', '', str(model_text or ''))).lower()
        close = [str(m) for m in CarModel.objects.filter(deposit_values__isnull=False).distinct()
                 if token and token[:3] in re.sub(r'\s+', '', str(m)).lower()][:6]
        return {'found': False, 'why': f'No model in the deposit sheet matches "{model_text}".',
                'models_with_values_like_it': close}

    found = rows(car_model, year, tier, region)
    available_years = sorted(set(DepositTier.in_force(car_model=car_model)
                                 .values_list('model_year', flat=True)))
    if not found:
        return {'found': False, 'car': str(car_model),
                'why': f'The sheet has no value for {car_model} {year or ""}'.strip(),
                'years_in_the_sheet': available_years}

    values = [{'year': r.model_year, 'tier': TIER_AR.get(r.tier, r.tier),
               'region': REGION_AR.get(r.region, r.region), 'deposit_usd': _usd(r.deposit_usd)}
              for r in found]
    # Europe and outside are often the same figure (small engines): say it once.
    same_everywhere = {}
    for r in found:
        same_everywhere.setdefault((r.model_year, r.tier), set()).add(r.deposit_usd)
    return {
        'found': True,
        'car': str(car_model),
        'values': values,
        'same_inside_and_outside_europe': all(len(v) == 1 for v in same_everywhere.values()),
        'years_in_the_sheet': available_years,
    }


def normalise_tier(value):
    return value if value in TIER_AR else _pick(value, _TIER_WORDS)


def normalise_region(value):
    return value if value in REGION_AR else _pick(value, _REGION_WORDS)


def car_of(listing=None, text=''):
    """(catalogue model, model year) of an advert, else of the words describing the car."""
    if listing is not None and getattr(listing, 'car_model_id', None):
        return listing.car_model, listing.model_year or year_in(text)
    return find_model(text), year_in(text)


def quote_note(car_model, year, tier, region):
    """One line for a quotation: the deposit for this exact car, or ''."""
    tier, region = normalise_tier(tier), normalise_region(region)
    if car_model is None or not year or tier not in TIER_AR or region not in REGION_AR:
        return ''
    found = rows(car_model, year, tier, region)
    if not found:
        return ''
    return (f'قيمة وديعة المبادرة لـ {car_model} موديل {year} ({TIER_AR[tier]}، {REGION_AR[region]}): '
            f'{_usd(found[0].deposit_usd)} — بتتدفع بالدولار وبترجع لصاحب المبادرة بعد 5 سنين، ومش جزء من '
            f'الإجمالي باليورو.')
