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
    # trim and drivetrain names the listings carry verbatim — "AMG Line",
    # "4MATIC", "xDrive" are the car's name, not the assistant slipping into
    # English. Seen flagged live on 2026-09-17 ("line", "matic").
    'line', 'matic', 'xdrive', 'quattro', 'sport', 'coupe', 'cabrio', 'sedan',
    'premium', 'avantgarde', 'exclusive', 'progressive', 'edition', 'plus',
    'hybrid', 'tron', 'night', 'package', 'sportline', 'style', 'ambition',
    'elegance', 'luxury', 'business', 'comfort', 'panorama', 'led', 'kit',
}
MONEY_WORDS = ('جنيه', 'يورو', 'دولار', 'ألف', 'الف', '٪', '%')

# Sentences that promise something the company will not honour.
PROMISE_PATTERNS = [
    (re.compile(r'(أضمن|بضمن|متأكد\s+إن|أوعدك|بوعدك)'), 'a promise the company has not made'),
    # "The money arrived" is the accountant's sentence, and the system sends it
    # when they press Accept. These catch the assistant AFFIRMING it — not
    # "لما التحويل يوصل" or "استلمنا صورة التحويل", which it now says all day.
    (re.compile(r'(?<![يتهن])(وصل|وصلنا|وصلتنا|وصلت)\s+(التحويل|الفلوس|المبلغ)'), 'confirming money arrived'),
    (re.compile(r'(التحويل|الفلوس|المبلغ)\s+(وصل|وصلت|وصلنا|اتأكد|اتأكدت)(?!\w)'), 'confirming money arrived'),
    (re.compile(r'(تم|اتأكدنا\s+من)\s+(تأكيد\s+)?(استلام|وصول)\s+(ال)?(تحويل|فلوس|مبلغ)'), 'confirming money arrived'),
    (re.compile(r'(خصم|تخفيض)\s*\d'), 'offering a discount'),
]


def check_reply(text, allowed_figures=None, expect_arabic=True, allowed_text=''):
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

    if _unapproved_account(text, allowed_text):
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


def _unapproved_account(text, allowed_text):
    """An account-shaped string the tools did not hand over this conversation.
    The approved bank template arrives through a tool; relaying it is the job."""
    approved = _normalise_number(allowed_text)
    hits = [m.group(0) for m in ACCOUNT_LIKE.finditer(text.replace('،', ''))]
    hits += [m.group(0) for m in IBAN_LIKE.finditer(text)]
    for hit in hits:
        digits = _normalise_number(hit)
        if not digits or digits not in approved:
            return True
    return False


def _canonical(value):
    """'12,000.00', '12.000,00', '12000' and '12 000' are one number.

    Digits alone are not enough: a tool returns 12,000.00 and the assistant
    says 12,000 — 1200000 against 12000 — and a correct reply is blocked.
    Returns the forms that should be treated as the same figure.
    """
    raw = re.sub(r'[^\d.,]', '', str(value)).strip('.,')
    if not any(ch.isdigit() for ch in raw):
        return set()
    last = max(raw.rfind(','), raw.rfind('.'))
    whole, cents = raw, ''
    if last != -1:
        tail = raw[last + 1:]
        both = (',' in raw) and ('.' in raw)
        if tail.isdigit() and len(tail) in (1, 2) and (both or raw.count(raw[last]) == 1):
            whole, cents = raw[:last], tail
    whole_digits = ''.join(ch for ch in whole if ch.isdigit()).lstrip('0') or '0'
    forms = {whole_digits}
    if cents and cents.strip('0'):
        forms = {whole_digits + '.' + cents.ljust(2, '0')}
        rounded = str(int(whole_digits) + (1 if int(cents.ljust(2, '0')) >= 50 else 0))
        forms.add('~' + rounded)          # the assistant may round a figure with cents
    return forms


#: A number is MONEY when a currency or a percent sign sits right against it.
#: "Near a money word" was the old test, and it is how "E200 زيرو بيورو 1" —
#: a model name next to the name of a certificate — became "an invented price
#: of 200", blocked a correct reply, and handed the client himself to a queue
#: nobody was watching (2026-09-20).
_CURRENCY = r'(?:€|\$|يورو|اليورو|euro|eur|جنيه|الجنيه|ج\.م|egp|le|دولار|usd|ألف|الف|آلاف|مليون|%|٪)'
_MONEY_AFTER = re.compile(r'^\s{0,2}' + _CURRENCY, re.I)
_MONEY_BEFORE = re.compile(r'(?:€|\$)\s?$')
#: Not glued to a letter or another digit: E200, GLA180, 1600cc, 4MATIC, X5.
_STANDALONE_NUMBER = re.compile(r'(?<![A-Za-z\d.,])(\d[\d.,]*\d|\d)(?![A-Za-z\d])')
#: The EUR 1 certificate is a document, not a price.
_EUR1 = re.compile(r'(يورو|اليورو|eur|euro)\s*\.?\s*(1|١|وان|one)(?![\d.,])', re.I)
_ARABIC_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩٫٬', '0123456789.,')


def figures_in(text):
    """Every number in a text, for building the allowed set."""
    return [m.group(1) for m in _STANDALONE_NUMBER.finditer(str(text or '').translate(_ARABIC_DIGITS))]


def _untraceable_figures(text, allowed):
    """Amounts of money in the reply that no tool, search or rule supplied."""
    allowed_forms = set()
    for a in allowed:
        for form in _canonical(a):
            allowed_forms.add(form.lstrip('~'))
    text = _EUR1.sub(' ', str(text or '').translate(_ARABIC_DIGITS))
    found = []
    for match in _STANDALONE_NUMBER.finditer(text):
        number = _normalise_number(match.group(1))
        if not number or len(number) < 3:
            continue                  # counts, small percentages, a year's last digits
        is_money = (_MONEY_AFTER.match(text[match.end():match.end() + 12])
                    or _MONEY_BEFORE.search(text[max(0, match.start() - 2):match.start()]))
        if not is_money:
            continue                  # a model, a year, an engine size, a mileage
        if {f.lstrip('~') for f in _canonical(match.group(1))} & allowed_forms:
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
        # Permissive on purpose: anything a tool printed may be said back.
        for match in re.finditer(r'\d[\d.,]{1,}', str(content or '').translate(_ARABIC_DIGITS)):
            figures.append(match.group(0))
    return figures


FIGURE_WINDOW_HOURS = 72

#: Under the selling policy, the only replies worth stopping are the two that
#: cost money the moment they are read: an account number the accountant did
#: not write, and "your money arrived". Everything else is sent and FLAGGED —
#: a note to the people watching, next to the reply. A block hands the customer
#: to a queue, and the client's instruction is that staff monitor, not answer:
#: a false alarm there is a customer talking to nobody.
BLOCKING_UNDER_AI_FIRST = {'bank_details'}
BLOCKING_WHY_UNDER_AI_FIRST = {'confirming money arrived'}

_PROMPT_FIGURES = None


def _prompt_figures():
    """Numbers the assistant's own rules tell it to say (27%, 3,000 جنيه, …).
    It is told to quote them; blocking it for obeying would be perverse."""
    global _PROMPT_FIGURES
    if _PROMPT_FIGURES is None:
        try:
            from car_import.agent_prompts import system_prompt
            _PROMPT_FIGURES = figures_in(system_prompt())
        except Exception:
            _PROMPT_FIGURES = []
    return list(_PROMPT_FIGURES)


def _apply_policy(problems):
    try:
        from car_import.services import policy
        if not policy.ai_first():
            return problems
    except Exception:
        return problems
    out = []
    for problem in problems:
        keep_block = (problem['rule'] in BLOCKING_UNDER_AI_FIRST
                      or problem.get('why') in BLOCKING_WHY_UNDER_AI_FIRST)
        out.append(problem if keep_block else dict(problem, severity='warn'))
    return out


def tool_text(conversation, since):
    """Everything the tools returned in the window, as one string."""
    if conversation is None or since is None:
        return ''
    try:
        from modules.chat.models import Message
        rows = (Message.objects_all.filter(conversation=conversation, type='tool',
                                           created_at__gte=since)
                .values_list('content', flat=True))
        return ' '.join(str(c or '') for c in rows)
    except Exception:
        logger.exception("car_import: could not read the tool results")
        return ''


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
    # "This turn" was the right window while the assistant only relayed a tool.
    # Now it sells: the customer asks "يعني المقدم كام؟" an hour after the offer,
    # and the honest answer is a figure a tool returned EARLIER in this same
    # conversation. Three days covers a sale; an invented number is still one
    # no tool ever returned.
    from datetime import timedelta
    window = (since - timedelta(hours=FIGURE_WINDOW_HOURS)) if since is not None else None
    allowed = figures_from_tool_messages(conversation, window) + _prompt_figures()
    problems = check_reply(text, allowed_figures=allowed,
                           allowed_text=tool_text(conversation, window))
    problems = _apply_policy(problems)
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
