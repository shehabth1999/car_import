# -*- coding: utf-8 -*-
"""Pull call recordings out of Dropbox — with a simulator, as with mobile.de.

Dropbox is the only source: the owner ruled the Vodafone IVR out on 2026-09-14.

**What was verified, and what was not.** The OAuth refresh grant was checked
against `docs.dropboxapi.com/dropbox-api/docs/oauth` on 2026-09-16: call
`/oauth2/token` with `grant_type=refresh_token` and the refresh token, and it
returns a new short-lived access token. The RPC and content paths below
(`files/list_folder`, `/continue`, `files/download`, and the `Dropbox-API-Arg`
header the content endpoints take their arguments in) are the documented
shapes, but the docs pages would not render for automated fetching today, so
**they are unconfirmed and must be proved against a real token before anyone
relies on them.** Until then the simulator answers, and `sync_calls` says which
backend served it every single time.

The cursor matters more than it looks. `list_folder` returns a cursor;
`/continue` takes it and returns only what changed since. Store it, and a
nightly poll costs one call and catches whatever a missed webhook dropped.
Lose it, and every sync re-reads the whole folder — which is survivable only
because imports are deduplicated on the Dropbox **file id**, not the path.
"""
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

TOKEN_URL = 'https://api.dropbox.com/oauth2/token'
RPC_BASE = 'https://api.dropboxapi.com/2'
CONTENT_BASE = 'https://content.dropboxapi.com/2'

APP_KEY = 'car_import.dropbox_app_key'
APP_SECRET = 'car_import.dropbox_app_secret'
REFRESH_TOKEN = 'car_import.dropbox_refresh_token'
FOLDER_KEY = 'car_import.dropbox_folder'
CURSOR_KEY = 'car_import.dropbox_cursor'
FORCE_SIMULATION_KEY = 'car_import.dropbox_force_simulation'

AUDIO_SUFFIXES = ('.mp3', '.m4a', '.wav', '.ogg', '.opus', '.amr', '.aac')


class DropboxError(Exception):
    """Anything that stops a sync."""


# ───────────────────────────────────────────────────────────────────────────
# configuration
# ───────────────────────────────────────────────────────────────────────────
def _config(key, default=''):
    try:
        from modules.base.models import ConfigParameter
        row = ConfigParameter.objects.filter(key=key).values('value').first()
    except Exception:
        return default
    return ((row or {}).get('value') or default)


def _set_config(key, value):
    from modules.base.models import ConfigParameter
    ConfigParameter.objects.update_or_create(key=key, defaults={'value': value})


def is_live():
    if str(_config(FORCE_SIMULATION_KEY)).strip().lower() in ('1', 'true', 'yes', 'on'):
        return False
    return bool(_config(APP_KEY) and _config(APP_SECRET) and _config(REFRESH_TOKEN))


# ───────────────────────────────────────────────────────────────────────────
# backends
# ───────────────────────────────────────────────────────────────────────────
class LiveBackend:
    """Talks to Dropbox. Only used when all three credentials exist."""

    simulated = False

    def __init__(self):
        self._access_token = None

    # -- auth ---------------------------------------------------------------
    def access_token(self):
        """A short-lived token, minted from the refresh token.

        Verified: POST /oauth2/token, grant_type=refresh_token. The long-lived
        token is the refresh token; this one expires in hours, which is why it
        is fetched per run and never stored.
        """
        if self._access_token:
            return self._access_token
        data = urllib.parse.urlencode({
            'grant_type': 'refresh_token',
            'refresh_token': _config(REFRESH_TOKEN),
            'client_id': _config(APP_KEY),
            'client_secret': _config(APP_SECRET),
        }).encode()
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(TOKEN_URL, data=data), timeout=20) as response:
                payload = json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            raise DropboxError(f'Dropbox refused the refresh token (HTTP {exc.code})') from exc
        except urllib.error.URLError as exc:
            raise DropboxError(f'Dropbox unreachable: {exc.reason}') from exc
        self._access_token = payload.get('access_token')
        if not self._access_token:
            raise DropboxError('Dropbox returned no access token')
        return self._access_token

    def _rpc(self, path, body):
        request = urllib.request.Request(
            f'{RPC_BASE}/{path}', data=json.dumps(body).encode(),
            headers={'Authorization': f'Bearer {self.access_token()}',
                     'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            detail = ''
            try:
                detail = exc.read().decode('utf-8', 'replace')[:300]
            except Exception:
                pass
            raise DropboxError(f'{path} failed (HTTP {exc.code}): {detail}') from exc
        except urllib.error.URLError as exc:
            raise DropboxError(f'{path} unreachable: {exc.reason}') from exc

    # -- listing ------------------------------------------------------------
    def list_new(self, folder, cursor=None):
        """Everything added since the cursor, and the cursor to store next."""
        if cursor:
            payload = self._rpc('files/list_folder/continue', {'cursor': cursor})
        else:
            payload = self._rpc('files/list_folder',
                                {'path': folder or '', 'recursive': True,
                                 'include_deleted': False, 'limit': 500})
        entries = list(payload.get('entries') or [])
        # `has_more` means the listing is paged, not that new files arrived.
        while payload.get('has_more'):
            payload = self._rpc('files/list_folder/continue', {'cursor': payload['cursor']})
            entries.extend(payload.get('entries') or [])
        return entries, payload.get('cursor')

    def download(self, path):
        """The bytes of one file."""
        request = urllib.request.Request(
            f'{CONTENT_BASE}/files/download',
            headers={'Authorization': f'Bearer {self.access_token()}',
                     # Content endpoints take their arguments in a header, not
                     # a body — the body is the file.
                     'Dropbox-API-Arg': json.dumps({'path': path})})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            raise DropboxError(f'download failed (HTTP {exc.code}) for {path}') from exc


class SimulatedBackend:
    """A folder of plausible recordings, so the pipeline runs before the app exists."""

    simulated = True

    def __init__(self, entries=None):
        self.entries = entries if entries is not None else load_fixture()

    def list_new(self, folder, cursor=None):
        # A cursor means "only what is new"; the simulator has nothing new to
        # offer on a second run, which is exactly how the real one behaves.
        if cursor:
            return [], cursor
        return list(self.entries), 'simulated-cursor-1'

    def download(self, path):
        return b''          # no audio: the transcript comes from the fixture


def load_fixture():
    import os
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'fixtures', 'dropbox_sample_calls.json')
    try:
        with open(path, encoding='utf-8') as handle:
            return json.load(handle)
    except Exception:
        logger.exception('car_import: could not read the Dropbox fixture')
        return []


def get_backend():
    return LiveBackend() if is_live() else SimulatedBackend()


# ───────────────────────────────────────────────────────────────────────────
# the import itself
# ───────────────────────────────────────────────────────────────────────────
def sync_calls(limit=None, reset_cursor=False):
    """Import whatever is new, match it, and say which backend answered.

    Deduplicated on the Dropbox **file id**: a file that is renamed or moved is
    the same call, and a cursor that gets lost must not re-import the lot.
    """
    from django.utils import timezone

    from car_import.models import CallRecording
    from car_import.services import call_matching

    backend = get_backend()
    folder = _config(FOLDER_KEY, '')
    cursor = '' if reset_cursor else _config(CURSOR_KEY, '')

    entries, next_cursor = backend.list_new(folder, cursor or None)
    created, skipped, ambiguous = [], 0, 0

    for entry in entries:
        if entry.get('.tag') == 'folder':
            continue
        name = entry.get('name') or ''
        if not name.lower().endswith(AUDIO_SUFFIXES):
            continue
        file_id = entry.get('id') or ''
        if not file_id:
            continue
        if CallRecording.objects.filter(dropbox_file_id=file_id).exists():
            skipped += 1
            continue

        path = entry.get('path_lower') or entry.get('path_display') or ''
        found = call_matching.identify(name, path)

        recorded_at = found['recorded_at']
        if recorded_at is None and entry.get('client_modified'):
            try:
                recorded_at = timezone.datetime.fromisoformat(
                    entry['client_modified'].replace('Z', '+00:00'))
            except Exception:
                recorded_at = None
        if recorded_at is not None and timezone.is_naive(recorded_at):
            recorded_at = timezone.make_aware(recorded_at)

        row = CallRecording.create(
            dropbox_file_id=file_id,
            dropbox_path=path,
            file_name=name,
            size_bytes=entry.get('size'),
            recorded_at=recorded_at,
            duration_seconds=entry.get('simulated_duration'),
            customer_phone=found['customer_phone'],
            agent_folder=found['agent_folder'],
            agent=found['agent'],
            partner=found['partner'],
            deal=found['deal'],
            match_state=found['match_state'],
            match_note=found['match_note'],
            candidates=found['candidates'],
            is_simulated=backend.simulated,
            # The fixture carries its own transcript so the summarising step
            # can be exercised without a speech-to-text bill.
            transcript=entry.get('simulated_transcript', ''),
            summary=entry.get('simulated_summary', ''),
            action_items=entry.get('simulated_actions') or [],
            process_state='summarised' if entry.get('simulated_summary') else 'new',
        )
        created.append(row)
        if row.needs_review:
            ambiguous += 1

        if limit and len(created) >= limit:
            break

    if next_cursor:
        _set_config(CURSOR_KEY, next_cursor)

    result = {'simulated': backend.simulated, 'seen': len(entries),
              'imported': len(created), 'already_had': skipped,
              'needs_review': ambiguous, 'folder': folder or '(root)'}
    logger.info('car_import: dropbox sync %s', result)
    return result
