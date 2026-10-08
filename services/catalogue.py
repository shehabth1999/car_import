# -*- coding: utf-8 -*-
"""Words → catalogue rows: which brand and model a piece of text means.

Everything that arrives as text goes through here once, at the edge — an
advert, a workbook row, a website form, what a customer typed — and from then
on the system holds the relation, never the string.

Two ways of asking:
  * `resolve(make, model, create=True)` for AUTHORITATIVE text (an advert, the
    owner's workbook, the website's own lists): a brand or model we do not have
    yet is added, so nothing is dropped.
  * `resolve(...)` / `parse(text)` without create for what a PERSON typed: it
    finds what exists or answers None. A customer's typo never becomes a brand.

Matching folds case, spaces and punctuation ("C 200" = "C200", "Mercedes-Benz"
= "mercedes benz") and reads each row's Arabic name and aliases, so
"مرسيدس" finds Mercedes.
"""
import re

_KEEP = re.compile(r'[^a-z0-9؀-ۿ]')
_ARABIC_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')


def norm(text):
    """'Mercedes-Benz' → 'mercedesbenz'; 'GLA 180' → 'gla180'; '' for nothing."""
    text = str(text or '').translate(_ARABIC_DIGITS).lower()
    text = text.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا').replace('ة', 'ه').replace('ى', 'ي')
    text = text.replace('ـ', '').replace('،', '').replace('؛', '').replace('؟', '')
    return _KEEP.sub('', text)


def _tidy(text):
    """How a new row is named: trimmed, one space, and 'KODIAQ' → 'Kodiaq'."""
    text = re.sub(r'\s+', ' ', str(text or '').strip())
    if text.isupper() and text.isalpha() and len(text) > 4:
        text = text.title()
    return text


# ── brands ───────────────────────────────────────────────────────────────────
def find_brand(text, loose=True):
    """The brand this text names, or None. Exact name / Arabic name / alias
    first; with `loose`, a unique prefix either way ("Mercedes" ↔ "Mercedes-Benz")."""
    from car_import.models import CarBrand
    wanted = norm(text)
    if not wanted:
        return None
    brands = list(CarBrand.objects.all())
    for brand in brands:
        if wanted in {norm(n) for n in brand.names()}:
            return brand
    if not loose or len(wanted) < 3:
        return None
    hits = [b for b in brands
            if any(len(n) >= 3 and (n.startswith(wanted) or wanted.startswith(n)) for n in map(norm, b.names()))]
    return hits[0] if len(hits) == 1 else None


def ensure_brand(text):
    """The brand for authoritative text, added when missing. None for empty text."""
    from car_import.models import CarBrand
    brand = find_brand(text)
    if brand is not None or not norm(text):
        return brand
    return CarBrand.objects.create(name=_tidy(text)[:64])


# ── models ───────────────────────────────────────────────────────────────────
def find_model(brand, text, loose=True):
    """The brand's model this text names, or None. With `loose`, the longest
    model name the text starts with ("C200 AMG Line" → C200)."""
    wanted = norm(text)
    if brand is None or not wanted:
        return None
    models = list(brand.car_models.all())
    for car_model in models:
        if wanted in {norm(n) for n in car_model.names()}:
            return car_model
    if not loose:
        return None
    best, best_len = None, 0
    for car_model in models:
        for name in map(norm, car_model.names()):
            if len(name) >= 2 and wanted.startswith(name) and len(name) > best_len:
                best, best_len = car_model, len(name)
    return best


def ensure_model(brand, text):
    """The brand's model for authoritative text, added when missing."""
    from car_import.models import CarModel
    if brand is None or not norm(text):
        return None
    car_model = find_model(brand, text, loose=False)
    if car_model is not None:
        return car_model
    return CarModel.objects.create(brand=brand, name=_tidy(text)[:128])


def resolve(make, model=None, create=False):
    """(brand, car_model) for a make and a model given apart."""
    if create:
        brand = ensure_brand(make)
        return brand, ensure_model(brand, model) if model else None
    brand = find_brand(make)
    return brand, find_model(brand, model) if (brand is not None and model) else None


def _model_in(brand, words):
    """The brand's model named anywhere in these words — "عايز C200 AMG" → C200.
    Longest run of words first, so "GLC 43 AMG" beats "GLC 43"."""
    for size in range(len(words), 0, -1):
        for start in range(0, len(words) - size + 1):
            car_model = find_model(brand, ' '.join(words[start:start + size]))
            if car_model is not None:
                return car_model
    return None


def parse(text):
    """(brand, car_model) from one phrase — "مرسيدس C200 2025", "BMW X1".
    Never creates. The brand may be absent from the phrase when the model is
    unmistakable ("GLC 200" is only ever a Mercedes)."""
    from car_import.models import CarModel
    words = [w for w in re.split(r'[\s,/|،]+', str(text or '').strip()) if w]
    if not words:
        return None, None
    # The brand: the longest run of leading words that names one.
    for size in range(min(3, len(words)), 0, -1):
        for start in range(0, len(words) - size + 1):
            brand = find_brand(' '.join(words[start:start + size]), loose=False)
            if brand is not None:
                rest = words[:start] + words[start + size:]
                rest = [w for w in rest if not re.fullmatch(r'(19|20)\d\d', w.translate(_ARABIC_DIGITS))]
                return brand, _model_in(brand, rest)
    # No brand named: a model name that exists under exactly one brand.
    phrase = norm(' '.join(w for w in words if not re.fullmatch(r'(19|20)\d\d', w.translate(_ARABIC_DIGITS))))
    if len(phrase) < 2:
        return None, None
    hits = [m for m in CarModel.objects.select_related('brand') if phrase in {norm(n) for n in m.names()}]
    if len(hits) == 1:
        return hits[0].brand, hits[0]
    return None, None


# ── keeping the stored names honest ─────────────────────────────────────────
def refresh_names(brand=None, car_model=None):
    """A renamed brand or model re-labels what shows its name."""
    from car_import.models import CarModel, Vehicle
    if brand is not None:
        for row in CarModel.objects.filter(brand=brand):
            CarModel.objects.filter(pk=row.pk).update(display_name=f'{brand.name} {row.name}'.strip())
        vehicles = Vehicle.objects.filter(brand=brand)
    else:
        vehicles = Vehicle.objects.filter(car_model=car_model)
    for vehicle in vehicles.select_related('brand', 'car_model'):
        Vehicle.objects.filter(pk=vehicle.pk).update(name=vehicle.compose_name())


# ── the website's lists ──────────────────────────────────────────────────────
def brand_for_website(website_id, name_en='', name_ar=''):
    """The catalogue brand behind a website brand id: linked, matched by name, or added."""
    from car_import.models import CarBrand
    if not website_id:
        return None
    brand = CarBrand.objects.filter(website_id=website_id).first()
    if brand is not None:
        return brand
    brand = (find_brand(name_en, loose=False) or find_brand(name_ar, loose=False)) if (name_en or name_ar) else None
    if brand is not None and brand.website_id is None:
        CarBrand.objects.filter(pk=brand.pk).update(website_id=website_id)
        brand.website_id = website_id
        return brand
    name = _tidy(name_en or name_ar or f'#{website_id}')[:64]
    if CarBrand.objects.filter(name=name).exists():
        name = f'{name} #{website_id}'[:64]
    return CarBrand.objects.create(name=name, name_ar=(name_ar or '')[:64], website_id=website_id)


def model_for_website(website_id, brand, name_en='', name_ar=''):
    """The catalogue model behind a website model id: linked, matched within the brand, or added."""
    from car_import.models import CarModel
    if not website_id:
        return None
    car_model = CarModel.objects.filter(website_id=website_id).first()
    if car_model is not None:
        return car_model
    if brand is None:
        return None
    car_model = find_model(brand, name_en, loose=False) or (find_model(brand, name_ar, loose=False)
                                                            if name_ar else None)
    if car_model is not None and car_model.website_id is None:
        CarModel.objects.filter(pk=car_model.pk).update(website_id=website_id)
        car_model.website_id = website_id
        return car_model
    name = _tidy(name_en or name_ar or f'#{website_id}')[:128]
    if CarModel.objects.filter(brand=brand, name=name).exists():
        name = f'{name} #{website_id}'[:128]
    return CarModel.objects.create(brand=brand, name=name, name_ar=(name_ar or '')[:128], website_id=website_id)


def made_in_eu(brand):
    """True / False for a catalogue brand against the EU-made list (Link
    Tracker → EU-Made Brands, the client's request of 2026-10-07), or None
    while that list is empty or the brand is not known: an empty list must
    not flag every car."""
    if brand is None:
        return None
    from car_import.models import EuMadeBrand
    if not EuMadeBrand.objects.exists():
        return None
    return EuMadeBrand.objects.filter(brand=brand).exists()
