# -*- coding: utf-8 -*-
"""Work out whose call this was — or admit that we cannot.

The plan is explicit, and it is the right instinct: *anything ambiguous goes to
a review list instead of a guess*. A call summary filed against the wrong
customer is worse than one filed against nobody, because nobody checks the
chatter of a deal they were not expecting a call about.

Three signals, in order of trust:

1. the **phone number in the file name** — how the recorder names its files;
2. the **agent folder** it sat in;
3. the **call time**, which picks between two deals for the same customer.

Egyptian numbers arrive in every shape a human can type: +201012345678,
00201012345678, 01012345678, 1012345678. They are compared on the last nine
digits, which is the part that identifies the subscriber regardless of prefix.
"""
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)

#: Long enough to be a phone number, short enough not to swallow a timestamp.
PHONE_PATTERN = re.compile(r'(?:\+|00)?\d[\d\s\-]{7,17}\d')
#: 20260916_143005, 2026-09-16 14:30, 16-09-2026 …
TIMESTAMP_PATTERNS = [
    ('%Y%m%d_%H%M%S', re.compile(r'(\d{8}_\d{6})')),
    ('%Y%m%d%H%M%S', re.compile(r'(\d{14})')),
    ('%Y-%m-%d_%H-%M-%S', re.compile(r'(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})')),
    ('%Y-%m-%d %H:%M:%S', re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})')),
    ('%Y-%m-%d', re.compile(r'(\d{4}-\d{2}-\d{2})')),
]


def digits(value):
    return ''.join(ch for ch in str(value or '') if ch.isdigit())


def subscriber(value):
    """The last nine digits — what identifies a number whatever the prefix."""
    only = digits(value)
    return only[-9:] if len(only) >= 9 else only


def phone_from_name(file_name):
    """The customer's number as written in the file name, if there is one."""
    best = ''
    for match in PHONE_PATTERN.finditer(str(file_name or '')):
        candidate = digits(match.group())
        # A timestamp is digits too. Anything 14 long is almost certainly one.
        if len(candidate) in (14, 8, 6):
            continue
        if len(candidate) > len(best):
            best = candidate
    return best


def recorded_at_from_name(file_name):
    """The call time as written in the file name, if there is one."""
    text = str(file_name or '')
    for fmt, pattern in TIMESTAMP_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        try:
            return datetime.strptime(match.group(1), fmt)
        except ValueError:
            continue
    return None


def agent_from_path(path):
    """The agent's folder name — '/calls/ramy/2026/09/x.mp3' → 'ramy'."""
    parts = [p for p in str(path or '').split('/') if p]
    return parts[1] if len(parts) >= 3 else (parts[0] if parts else '')


def match_partner(phone):
    """Every contact whose number matches. Zero, one, or several — all valid."""
    from modules.base.models import Partner

    key = subscriber(phone)
    if not key or len(key) < 8:
        return []
    found = []
    for partner in Partner.all_objects.exclude(phone='').only('id', 'name', 'phone'):
        if subscriber(partner.phone) == key:
            found.append(partner)
    return found


def match_agent(folder_name):
    from modules.base.models.user import User

    name = (folder_name or '').strip().lower()
    if not name:
        return None
    for user in User.objects.filter(is_active=True).only('id', 'email', 'name'):
        label = (getattr(user, 'name', '') or user.email or '').lower()
        if name and (name in label or label.split('@')[0] == name):
            return user
    return None


def match_deal(partner, recorded_at=None):
    """The deal this call was probably about.

    The customer's only open deal, or the one they were in the middle of when
    the call happened. Two open deals and no time: no answer, on purpose.
    """
    from car_import.models import CarDeal

    deals = list(CarDeal.all_objects.filter(partner=partner).exclude(state='cancelled')
                 .order_by('-id'))
    if not deals:
        return None, 'the customer has no open deal'
    if len(deals) == 1:
        return deals[0], ''
    if recorded_at is None:
        return None, f'{len(deals)} open deals and no call time to choose between them'
    # The deal whose stage the call landed during.
    dated = [d for d in deals if d.stage_entered_at and d.stage_entered_at <= recorded_at]
    if len(dated) == 1:
        return dated[0], ''
    return None, f'{len(deals)} open deals; the call time did not separate them'


def identify(file_name, path=''):
    """Everything we can say about one recording, without guessing.

    Returns a dict the importer writes straight onto the row, including the
    match state — `ambiguous` is a real answer and it means a human looks.
    """
    phone = phone_from_name(file_name)
    recorded_at = recorded_at_from_name(file_name)
    folder = agent_from_path(path)
    partners = match_partner(phone)

    result = {
        'customer_phone': phone,
        'recorded_at': recorded_at,
        'agent_folder': folder,
        'agent': match_agent(folder),
        'partner': None,
        'deal': None,
        'lead': None,
        'match_state': 'unmatched',
        'match_note': '',
        'candidates': [],
    }

    if not phone:
        result['match_note'] = 'no phone number in the file name'
        return result
    if not partners:
        result['match_note'] = f'no contact with the number {phone}'
        return result
    if len(partners) > 1:
        result['match_state'] = 'ambiguous'
        result['match_note'] = f'{len(partners)} contacts share this number'
        result['candidates'] = [{'id': p.pk, 'name': p.name, 'phone': p.phone} for p in partners]
        return result

    partner = partners[0]
    result['partner'] = partner
    result['match_state'] = 'matched'
    deal, why = match_deal(partner, recorded_at)
    result['deal'] = deal
    if deal is None and why:
        # The customer is known even when the deal is not; that is still a
        # useful row, and the note says what is missing.
        result['match_note'] = why
    return result
