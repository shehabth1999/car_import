# -*- coding: utf-8 -*-
"""The currencies this business quotes in, as rows rather than strings.

Money in this module is always two fields: a number and a relation to
`base.Currency`. Never a `money` widget (it prints the company's symbol on any
figure), never a free-text code. These helpers hand back the rows by code so
model defaults and seeds do not carry primary keys.
"""
from functools import lru_cache


def by_code(code):
    """The `base.Currency` row for an ISO code, or None."""
    if not code:
        return None
    from modules.base.models.currency import Currency
    return Currency.objects.filter(code__iexact=str(code).strip()).first()


@lru_cache(maxsize=16)
def id_by_code(code):
    row = by_code(code)
    return row.pk if row is not None else None


def eur():
    return by_code('EUR')


def egp():
    return by_code('EGP')


def code_of(row):
    """'EUR' for a currency row, '' for None — for text people read."""
    return getattr(row, 'code', '') or ''
