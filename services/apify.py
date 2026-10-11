# -*- coding: utf-8 -*-
"""Apify — run an Actor and get back what it scraped, in one HTTP call.

Checked against the official reference on 2026-10-11, not written from memory
(https://docs.apify.com/api/v2/act-run-sync-get-dataset-items-post):

    POST https://api.apify.com/v2/acts/<owner>~<actor>/run-sync-get-dataset-items
    Authorization: Bearer <token>
    body: the Actor's input, as JSON
    ?timeout=<seconds>   stops the run
    ?maxItems=<n>        the most a pay-per-result Actor may bill for
    2xx + a JSON array of items · 400 bad input · 401 bad token ·
    402 no credit · 408 when the run passes 300 seconds

**The token is a secret and lives in the environment only** — `APIFY_TOKEN` in
the deployment's `.env`. It goes out in the `Authorization` header, so it is
never part of a URL, a log line or an error message. It is deliberately NOT a
row in مفاتيح التشغيل, where every manager could read it.

**Every result costs money**, so nothing here runs unmetered: a run declares
the most it may return, and the day's total is held under
`car_import.apify_daily_results_cap`. Past the cap a run is refused rather than
billed, and the caller falls back to whatever it did before Apify existed.
"""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

API_BASE = 'https://api.apify.com/v2'
TOKEN_ENV = 'APIFY_TOKEN'
SYNC_LIMIT_SECONDS = 300          # documented: a longer run answers 408
MIN_BILLING_CEILING = 30          # items; see run_sync

DAILY_CAP_KEY = 'car_import.apify_daily_results_cap'
DEFAULT_DAILY_CAP = 300

_USAGE_TTL = 2 * 24 * 60 * 60
_MODELS_TTL = 7 * 24 * 60 * 60

_KIND_BY_STATUS = {400: 'bad_input', 401: 'unauthorized', 402: 'no_credit',
                   403: 'unauthorized', 408: 'timeout'}


class ApifyError(Exception):
    """A run that returned nothing usable. `kind` says why: `no_token`,
    `unauthorized`, `no_credit`, `timeout`, `bad_input`, `cap`, `unreachable`
    or `http`."""

    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


# ───────────────────────────────────────────────────────────────────────────
# the token
# ───────────────────────────────────────────────────────────────────────────
def token():
    """`APIFY_TOKEN` from the process environment, else from the project's
    `.env` — the same file the settings read. '' when it is not there."""
    try:
        from decouple import AutoConfig
        from django.conf import settings
        value = AutoConfig(search_path=str(settings.BASE_DIR))(TOKEN_ENV, default='')
    except Exception:
        logger.exception('car_import: could not read %s', TOKEN_ENV)
        return ''
    return str(value or '').strip()


def is_configured():
    return bool(token())


# ───────────────────────────────────────────────────────────────────────────
# the spend guard
# ───────────────────────────────────────────────────────────────────────────
def daily_cap():
    """The most results a day may cost. 0 stops every run."""
    try:
        from modules.base.models import ConfigParameter
        row = ConfigParameter.objects.filter(key=DAILY_CAP_KEY).values('value').first()
        return max(0, int(str((row or {}).get('value') or '').strip()))
    except Exception:
        return DEFAULT_DAILY_CAP


def _usage_key():
    return 'car_import:apify:results:%s' % timezone.localdate().isoformat()


def used_today():
    return int(cache.get(_usage_key()) or 0)


def _record(count):
    if count <= 0:
        return
    key = _usage_key()
    cache.add(key, 0, _USAGE_TTL)
    try:
        cache.incr(key, count)
    except ValueError:
        cache.set(key, count, _USAGE_TTL)


# ───────────────────────────────────────────────────────────────────────────
# the call
# ───────────────────────────────────────────────────────────────────────────
def _actor_path(actor):
    return urllib.parse.quote(str(actor).replace('/', '~'), safe='~')


def _failure(exc):
    """(kind, text) for an HTTP error. Apify answers `{"error": {"type", "message"}}`."""
    try:
        body = exc.read().decode('utf-8', 'replace')
    except Exception:
        body = ''
    try:
        parsed = json.loads(body)
    except ValueError:
        parsed = None
    error = parsed.get('error') if isinstance(parsed, dict) else None
    error = error if isinstance(error, dict) else {}
    kind = _KIND_BY_STATUS.get(exc.code, 'http')
    if 'timed-out' in str(error.get('type') or ''):
        kind = 'timeout'
    return kind, f"Apify returned HTTP {exc.code}: {error.get('message') or body[:300]}"


def run_sync(actor, run_input, max_items, timeout=60):
    """Run `actor` with `run_input` and return its items (a list of dicts).

    `max_items` is the most this run may return and be billed for; it is
    counted against the day's cap BEFORE the run, so a refused run costs
    nothing. Raises ApifyError — never returns a half-answer.
    """
    secret = token()
    if not secret:
        raise ApifyError('no_token', f'{TOKEN_ENV} is not set in the environment')

    max_items = max(1, int(max_items))
    cap, used = daily_cap(), used_today()
    if used + max_items > cap:
        raise ApifyError('cap', f"Today's Apify limit is reached ({used} of {cap} results). "
                                f"Raise {DAILY_CAP_KEY} to allow more.")

    timeout = max(10, min(int(timeout), SYNC_LIMIT_SECONDS))
    # Apify refuses a run whose maximum cost comes to less than $0.01 ("Maximum
    # cost per run is less than the allowed minimum", first real run,
    # 2026-10-11) — a one-advert read asked for a ceiling of a fraction of a
    # cent. So the billing ceiling has a floor; how many items actually come
    # back is the Actor input's business, and that is what gets billed.
    query = urllib.parse.urlencode({'timeout': timeout, 'maxItems': max(max_items, MIN_BILLING_CEILING),
                                    'format': 'json', 'clean': 1})
    request = urllib.request.Request(
        f'{API_BASE}/acts/{_actor_path(actor)}/run-sync-get-dataset-items?{query}',
        data=json.dumps(run_input).encode('utf-8'), method='POST',
        headers={'Authorization': f'Bearer {secret}', 'Content-Type': 'application/json',
                 'Accept': 'application/json'})
    try:
        # A little longer than the run itself: the answer only starts once the
        # Actor has finished, and a client that gives up first learns nothing.
        with urllib.request.urlopen(request, timeout=timeout + 20) as response:
            payload = json.loads(response.read().decode('utf-8') or '[]')
    except urllib.error.HTTPError as exc:
        kind, text = _failure(exc)
        raise ApifyError(kind, text) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        reason = getattr(exc, 'reason', exc)
        kind = 'timeout' if isinstance(reason, TimeoutError) or isinstance(exc, TimeoutError) else 'unreachable'
        raise ApifyError(kind, f'Apify did not answer: {reason}') from exc
    except ValueError as exc:
        raise ApifyError('http', 'Apify answered with something that is not JSON') from exc

    items = [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []
    _record(len(items))
    logger.info('car_import: Apify %s returned %s item(s); %s of %s used today',
                actor, len(items), used_today(), cap)
    return items


# ───────────────────────────────────────────────────────────────────────────
# what an Actor accepts
# ───────────────────────────────────────────────────────────────────────────
def model_choices(actor):
    """The Actor's own list of `Make|Model` values.

    The mobile.de Actor refuses a model that is not on its list, and its
    spelling is the marketplace's ("C 200"), not ours ("C200"). The list is
    part of the Actor's public input schema — reading it needs no token and
    costs nothing — and it is kept for a week.
    """
    key = 'car_import:apify:models:%s' % _actor_path(actor)
    choices = cache.get(key)
    if choices:
        return choices
    request = urllib.request.Request(
        f'{API_BASE}/acts/{_actor_path(actor)}/builds/default/openapi.json',
        headers={'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            schema = json.loads(response.read().decode('utf-8'))
        choices = list(schema['components']['schemas']['inputSchema']['properties']['models']['items']['enum'])
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, TypeError) as exc:
        raise ApifyError('unreachable', f"Could not read the Actor's list of models: {exc}") from exc
    cache.set(key, choices, _MODELS_TTL)
    return choices
