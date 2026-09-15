# -*- coding: utf-8 -*-
"""
The agent's prompts, read once at import.

They live as markdown files so they can be reviewed in a pull request instead of
pasted into a node's configuration box. Editing one needs a Celery restart —
that is the trade for keeping them in git.
"""
import os

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prompts')


def _read(name):
    path = os.path.join(PROMPTS_DIR, name)
    try:
        with open(path, encoding='utf-8') as handle:
            return handle.read().strip()
    except FileNotFoundError:  # pragma: no cover - a missing prompt must be loud, not silent
        return f"[missing prompt file: {name}]"


CORE = _read('core.md')
LANE_SALES = _read('lane_sales.md')
VOICE_AYA = _read('voice_aya.md')
VOICE_RAMY = _read('voice_ramy.md')
VOICE_SOCIAL = _read('voice_social.md')

VOICES = {
    'aya': VOICE_AYA,
    'ramy': VOICE_RAMY,
    'social': VOICE_SOCIAL,
}


def system_prompt(voice='aya'):
    """The full system prompt for one WhatsApp number or channel."""
    return "\n\n".join([CORE, VOICES.get(voice, VOICE_AYA), LANE_SALES])
