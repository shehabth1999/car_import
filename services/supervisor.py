# -*- coding: utf-8 -*-
"""The last thing between the agent and the customer.

Agent A10 in the plan is a model that samples replies and reports. This is the
half that does not need a model at all, and it runs on every reply rather than a
sample: a set of checks that are *decidable* — a digit string that looks like an
IBAN, a Latin word in an Arabic sentence, a figure the tools never returned.

The production rule this implements: **the prompt cannot be the last line of
defence.** This session proved it twice — told not to state figures, the model
read the entire price list out; told to escalate money, it escalated a question
about a port. Prose loses arguments. A function does not.

Nothing here rewrites a reply. It flags, and the caller decides — because a
silent edit of what an agent said is its own kind of lie.
"""
import logging
import re

logger = logging.getLogger(__name__)

#: A run of digits long enough to be an account, IBAN or card.
ACCOUNT_LIKE = re.compile(r'(?:\d[\s\-]?){12,}')
IBAN_LIKE = re.compile(r'\b[A-Z]{2}\d{2}[A-Z0-9\s]{10,30}\b')
#: Latin letters inside otherwise-Arabic text. Brand names are allowed.
LATIN_RUN = re.compile(r'[A-Za-z]{3,}')
ALLOWED_LATIN = {
    'mercedes', 'benz', 'bmw', 'audi', 'skoda', 'volkswagen', 'vw', 'porsche',
    'amg', 'gmbh', 'acid', 'eur', 'usd', 'egp', 'km', 'cc', 'hp', 'suv', 'tfsi',
    'tsi', 'tdi', 'gla', 'glc', 'gle', 'cla', 'ka', 'whatsapp', 'bill', 'lading',
    'mobile', 'de', 'msc', 'euro',
}
MONEY_WORDS = ('جنيه', 'يورو', 'دولار', 'ألف', 'الف', '٪', '%')

# Sentences that promise something the company will not honour.
PROMISE_PATTERNS = [
    (re.compile(r'(أضمن|بضمن|متأكد\s+إن|أوعدك|بوعدك)'), 'a promise the company has not made'),
    (re.compile(r'(وصل|اتأكد).{0,12}(التحويل|الفلوس|المبلغ)'), 'confirming money arrived'),
    (re.compile(r'(خصم|تخفيض)\s*\d'), 'offering a discount'),
]


def check_reply(text, allowed_figures=None, expect_arabic=True):
    """Look at one outgoing reply and report what is wrong with it.

    `allowed_figures` are the numbers the tools actually returned this turn.
    Anything else that looks like money is flagged — not because every figure is
    wrong, but because a figure nobody can trace is exactly the failure mode the
    client asked us to prevent.
    """
    text = str(text or '')
    problems = []
    if not text.strip():
        return problems              # silence is a valid, deliberate reply

    if ACCOUNT_LIKE.search(text.replace('،', '')) or IBAN_LIKE.search(text):
        problems.append({'rule': 'bank_details', 'severity': 'block',
                         'why': 'the reply contains something shaped like an account number'})

    for pattern, why in PROMISE_PATTERNS:
        if pattern.search(text):
            problems.append({'rule': 'promise', 'severity': 'block', 'why': why})

    if expect_arabic and _has_arabic(text):
        stray = sorted({w.lower() for w in LATIN_RUN.findall(text)} - ALLOWED_LATIN)
        if stray:
            problems.append({'rule': 'language', 'severity': 'warn',
                             'why': f'English inside an Arabic reply: {", ".join(stray[:5])}'})

    untraceable = _untraceable_figures(text, allowed_figures or [])
    if untraceable:
        problems.append({'rule': 'untraceable_figure', 'severity': 'block',
                         'why': f'figures no tool returned this turn: {", ".join(untraceable[:5])}'})

    return problems


def _has_arabic(text):
    return any('؀' <= ch <= 'ۿ' for ch in text)


def _untraceable_figures(text, allowed):
    """Money-ish numbers in the reply that the tools did not supply."""
    allowed_digits = {_normalise_number(str(a)) for a in allowed}
    found = []
    for match in re.finditer(r'(\d[\d.,]{1,})', text):
        number = _normalise_number(match.group(1))
        if not number or len(number) < 3:
            continue                  # years, counts, small numbers
        window = text[max(0, match.start() - 24):match.end() + 24]
        if not any(word in window for word in MONEY_WORDS):
            continue                  # not presented as money
        if number in allowed_digits:
            continue
        found.append(match.group(1))
    return found


def _normalise_number(value):
    return ''.join(ch for ch in str(value) if ch.isdigit())


def review_and_log(deal, text, allowed_figures=None):
    """Check a reply and, when something is wrong, put it on the record.

    Used by a human reviewing the assistant's work, and available to a future
    outbound gate. It never edits and never blocks by itself — that decision
    belongs to whoever is sending.
    """
    problems = check_reply(text, allowed_figures=allowed_figures)
    if not problems and deal is not None:
        return problems
    if deal is not None and problems:
        lines = '\n'.join(f'- [{p["severity"]}] {p["why"]}' for p in problems)
        try:
            deal.message_post(body=f'مراجعة رد المساعد — فيه ملاحظات:\n{lines}')
        except Exception:
            logger.exception('car_import: could not log a supervisor note')
    return problems


# ── the outbound gate ────────────────────────────────────────────────────────
#: What the customer reads when a reply is stopped. The same sentence the
#: escalation tool sends, so a blocked reply and a deliberate hand-over look
#: identical from the customer's side — which they should: both mean a human
#: is now on it.
HOLDING_TEXT = "تمام يا فندم 🙏 هحوّل حضرتك لزميلي وهو هيرد على حضرتك حالاً."


def figures_from_tool_messages(conversation, since):
    """Every number the tools returned in this turn.

    The engine does not hand tool results back in a structured way, but every
    tool call and its result are written to the thread as `tool_call` / `tool`
    messages (all our tools are `store: True`). Reading those since the turn
    began is the honest source of "which figures may this reply contain".
    """
    if conversation is None or since is None:
        return []
    try:
        from modules.chat.models import Message
        # `objects_all`, not `objects`: the default manager EXCLUDES tool and
        # tool_call rows by design (chat/models.py:2292), so the obvious query
        # returns nothing, every figure looks untraceable, and the gate blocks
        # the very numbers the tools just supplied.
        rows = (Message.objects_all.filter(conversation=conversation, type='tool',
                                           created_at__gte=since)
                .values_list('content', flat=True))
    except Exception:
        logger.exception('car_import: could not read this turn\'s tool results')
        return []
    figures = []
    for content in rows:
        for match in re.finditer(r'\d[\d.,]{1,}', str(content or '')):
            figures.append(match.group(0))
    return figures


def gate(text, conversation=None, since=None, workflow_name=''):
    """Decide what leaves, and record why. Returns (text_to_send, problems).

    **Warn** — the reply goes out unchanged and a note lands in the thread, so
    a human sees it next to the customer's message without the customer
    waiting on us.

    **Block** — the customer gets the holding sentence, the conversation is
    handed to a human the same way `ka_escalate_conversation_to_staff` does
    it, and the note carries the reply that was stopped, word for word, with
    the rule that stopped it. Silently swallowing what the model tried to say
    would hide exactly the evidence the client needs to tune the prompt.

    Never returns an empty string: an empty output makes the channel bridge
    re-run the model and then send a failure email, which is neither silent
    nor free.
    """
    problems = check_reply(text, allowed_figures=figures_from_tool_messages(conversation, since))
    if not problems:
        return text, problems

    blocking = [p for p in problems if p['severity'] == 'block']
    lines = [f"- [{p['severity']}] {p['why']}" for p in problems]

    if not blocking:
        _note(conversation,
              '⚠️ ملاحظة على رد المساعد (اتبعت زي ما هو):\n' + '\n'.join(lines)
              + f'\n\nالرد:\n{text}',
              subject='ملاحظة على رد المساعد')
        return text, problems

    _hand_over(conversation, topic=blocking[0]['rule'])
    body = ('🛑 رد المساعد اتوقف قبل ما يوصل للعميل.\n'
            + '\n'.join(lines)
            + '\n\nالرد اللي كان هيتبعت:\n' + str(text)
            + '\n\nالعميل وصله: "' + HOLDING_TEXT + '"\nمحتاج حد يكمّل معاه من هنا.')
    if any(p['rule'] in ('untraceable_figure', 'promise') for p in blocking):
        body += _figures_for(conversation)
    _note(conversation, body, subject='رد المساعد اتوقف — محتاج زميل')
    return HOLDING_TEXT, problems


def _hand_over(conversation, topic='supervisor'):
    """The same hand-over the escalation tool performs, and stamped the same way
    so the chaser can tell "we handed over" from "never had an assistant"."""
    if conversation is None:
        return
    try:
        from django.utils import timezone
        data = conversation.social_platform_data
        if not isinstance(data, dict):
            data = {}
        data['car_import_escalated_at'] = timezone.now().isoformat()
        data['car_import_escalation_topic'] = f'supervisor:{topic}'
        conversation.handled_by_ai = False
        conversation.social_platform_data = data
        conversation.save(update_fields=['handled_by_ai', 'social_platform_data'])
    except Exception:
        logger.exception('car_import: supervisor could not hand the conversation over')


def _note(conversation, body, subject):
    if conversation is None:
        return
    try:
        from car_import.services import internal_note
        from car_import.tasks import _owner_users_for_partner
        owners = _owner_users_for_partner(getattr(conversation, 'social_partner', None))
        internal_note.post(conversation, body, recipients=owners, subject=subject)
    except Exception:
        logger.exception('car_import: supervisor could not leave its note')


def _figures_for(conversation):
    try:
        from car_import.services import money_briefing
        partner = getattr(conversation, 'social_partner', None)
        figures = money_briefing.build(partner, topic='money')
        return ('\n\n' + figures) if figures else ''
    except Exception:
        return ''
