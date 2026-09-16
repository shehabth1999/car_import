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
# One voice for every number and every channel. There used to be three
# (Aya, Ramy, Social), one workflow each; the owner asked for a single agent,
# so the voice file blends them and adapts by channel inside the prompt.
VOICE = _read('voice.md')


def system_prompt():
    """The full system prompt: the rules, the voice, the sales lane."""
    return "\n\n".join([CORE, VOICE, LANE_SALES])
