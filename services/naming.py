# -*- coding: utf-8 -*-
"""One spelling of a car, so two tables can find each other.

The client's workbook and the marketplace do not agree, and nothing warns you:

    workbook        mobile.de          our own Vehicle rows
    Mercedes        Mercedes-Benz      Mercedes-Benz
    SKODA           Skoda              Skoda
    C 200           C200               C200
    E 300 e         E300e              E300e
    GLA 180         GLA180             GLA180

A join on those strings does not fail — it silently finds nothing, and a car
quietly has no deposit tier, no customs value and no price range. The pricing
engine would then either refuse for the wrong reason or, worse, fall through to
a default.

So both sides go through here. `normalise` is deliberately aggressive (case,
spaces, hyphens, the "-Benz" suffix) because these are catalogue names, not
prose: over-matching "C 200" to "C200" is right, and there is no pair in the
client's 23 models that collapses into another.
"""
import re

#: Marketplace spelling → the workbook's. Only where they genuinely differ.
MAKE_ALIASES = {
    'mercedesbenz': 'mercedes',
    'mercedes': 'mercedes',
    'vw': 'volkswagen',
    'landrover': 'landrover',
    'rangerover': 'landrover',
}


def normalise(value):
    """'C 200 AMG Line' → 'c200amgline'. Empty for anything falsy."""
    if not value:
        return ''
    text = str(value).strip().lower()
    text = text.replace('-', '').replace('_', '').replace('.', '')
    return re.sub(r'\s+', '', text)


def normalise_make(value):
    """Make names, with the aliases applied."""
    key = normalise(value)
    return MAKE_ALIASES.get(key, key)


def normalise_model(value):
    """Model names. 'GLA 180' and 'GLA180' become the same thing."""
    return normalise(value)


def same_make(a, b):
    return bool(a) and bool(b) and normalise_make(a) == normalise_make(b)


def same_model(a, b):
    return bool(a) and bool(b) and normalise_model(a) == normalise_model(b)


def find_reference_rows(car_model, model_year):
    """Every reference row for this catalogue model and year.

    The tables point at the car catalogue now, so this is a plain filter — the
    spelling problem above is solved once, where text enters the system
    (`services/catalogue.py`). Returns what was found and what was not, rather
    than raising: "we have no deposit value for this model" is an answer the
    agent and the quote both need to be able to give.
    """
    from car_import.models import CustomsValuation, DepositTier, ModelPriceRange

    found = {'deposits': [], 'customs': None, 'price_range': None, 'matched_on': None, 'missing': []}
    if car_model is None or not model_year:
        found['missing'].append('model or year not given')
        return found
    found['deposits'] = list(DepositTier.in_force(model_year=model_year).filter(car_model=car_model))
    found['customs'] = CustomsValuation.in_force(model_year=model_year).filter(car_model=car_model).first()
    found['price_range'] = ModelPriceRange.in_force(model_year=model_year).filter(car_model=car_model).first()
    found['matched_on'] = f'{car_model}/{model_year}'
    if not found['deposits']:
        found['missing'].append('no deposit value for this model and year')
    if found['customs'] is None:
        found['missing'].append('no customs value for this model and year')
    if found['price_range'] is None:
        found['missing'].append('no market price range for this model and year')
    return found


def deposit_for(car_model, model_year, tier, region):
    """One deposit figure, or None. Never a guess and never a default."""
    from car_import.models import DepositTier

    if car_model is None:
        return None
    return DepositTier.in_force(model_year=model_year, tier=tier, region=region).filter(car_model=car_model).first()
