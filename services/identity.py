# -*- coding: utf-8 -*-
"""The customer as their national ID names them.

Quotes, proformas and contracts carry the name on the card, not the chat's
display name. On 2026-09-29 the owner tested with a chat called "Mr.Khaled",
buying on his brother's initiative with another man's ID; every document the
assistant sent still said "Mr.Khaled", and the assistant told him it could
not read the card it had just read. The card's data now lives on the contact
(`id_full_name`, `national_id`, `id_address` — the Partner extension) and every
document reads it from here.
"""
from datetime import date

_ARABIC_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')


def normalise_national_id(value):
    """The digits only, Arabic numerals accepted; '' when nothing was given."""
    return ''.join(ch for ch in str(value or '').translate(_ARABIC_DIGITS) if ch.isdigit())


def national_id_problem(digits):
    """None when the number is plausible, else why not.

    An Egyptian national ID is 14 digits: a century digit (2 = 1900s, 3 =
    2000s), the birth date as YYMMDD, then the governorate and a serial. A
    digit misread off a photo usually breaks one of those, so this catches the
    common OCR slip without pretending to verify the card.
    """
    if len(digits) != 14:
        return f'the national ID is 14 digits; this one has {len(digits)}'
    century = {'2': 1900, '3': 2000}.get(digits[0])
    if century is None:
        return 'a national ID starts with 2 or 3'
    try:
        date(century + int(digits[1:3]), int(digits[3:5]), int(digits[5:7]))
    except ValueError:
        return 'digits 2 to 7 of a national ID are the birth date, and these are not a valid date'
    return None


def masked(digits):
    """What the assistant may see of the number: enough to confirm, not to copy."""
    return f'{digits[:1]}{"•" * 9}{digits[-4:]}' if len(digits) == 14 else ''


def customer_name(partner):
    """The name every document prints."""
    return str(getattr(partner, 'id_full_name', None) or getattr(partner, 'name', '') or '').strip()


#: An Egyptian ID prints at least four names: the person's, the father's, the
#: grandfather's and the family's. The owner (2026-09-30): «المهم الاسم رباعي
#: كما مسجل ف البطاقة» — a shorter name is a name the customer shortened.
MIN_NAME_PARTS = 4


def name_parts(name):
    return len(str(name or '').split())


def full_id_name(partner):
    """The ID card's name when it is on file in four parts or more, else ''.
    The written offer waits for it — never the WhatsApp display name."""
    name = str(getattr(partner, 'id_full_name', None) or '').strip()
    return name if name_parts(name) >= MIN_NAME_PARTS else ''


def id_details(partner):
    return {
        'name': customer_name(partner),
        'national_id': str(getattr(partner, 'national_id', None) or '').strip(),
        'address': str(getattr(partner, 'id_address', None) or '').strip(),
        'from_id': bool(getattr(partner, 'id_full_name', None)),
    }


def save_id_card(partner, full_name='', national_id='', address=''):
    """Store what was read off the card on the contact, and on the open
    contract draft when there is one. Returns (saved, problems): the fields
    written, and the reasons anything was refused. Never raises for bad input.
    """
    saved, problems, changes = [], [], {}
    name = ' '.join(str(full_name or '').split())[:190]
    if name:
        changes['id_full_name'] = name
        saved.append('full_name')
    digits = normalise_national_id(national_id)
    if digits:
        problem = national_id_problem(digits)
        if problem:
            problems.append(problem)
        else:
            changes['national_id'] = digits
            saved.append('national_id')
    place = ' '.join(str(address or '').split())[:255]
    if place:
        changes['id_address'] = place
        saved.append('address')

    if changes:
        # A plain update: these are paperwork columns, and the contact's
        # save hooks (chatter, sync) have nothing to say about them.
        type(partner)._base_manager.filter(pk=partner.pk).update(**changes)
        for field, value in changes.items():
            setattr(partner, field, value)
        _copy_to_open_contract(partner, changes)
    return saved, problems


def _copy_to_open_contract(partner, changes):
    """The draft contract of the open deal learns the same facts."""
    try:
        from car_import.services import sales_flow
        from car_import.services.chat_actions import open_deal_for
        deal = open_deal_for(partner)
        if deal is None:
            return
        sales_flow.save_contract_details(
            deal, full_name=changes.get('id_full_name', ''),
            national_id=changes.get('national_id', ''), address=changes.get('id_address', ''))
    except Exception:  # noqa: BLE001 — the contact is saved; the draft can catch up later
        import logging
        logging.getLogger(__name__).exception('car_import: could not copy the ID onto the contract draft')
