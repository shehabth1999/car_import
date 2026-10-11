# -*- coding: utf-8 -*-
"""The last thing between the agent and the customer.

Agent A10 in the plan is a model that samples replies and reports. This is the
half that does not need a model at all, and it runs on every reply rather than a
sample: a set of checks that are *decidable* — a digit string that looks like an
IBAN, a promise, a foreign link, a figure the tools never returned.

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
MONEY_WORDS = ('جنيه', 'يورو', 'دولار', 'ألف', 'الف', '٪', '%')
#: Hosts a reply may link to: the company website, Genie itself, the adverts
#: the tools return, and the office's map pin (the contract-change invitation,
#: `services/contract_preview.py`). A live run invented "khaled-automobile.com".
LINK_HOSTS = ('khaledautomobilegmbh.de', 'genie-erp.com', 'mobile.de', 'autoscout24.de', 'wise.com',
              'maps.app.goo.gl', 'goo.gl', 'maps.google.com', 'google.com')

# Sentences that promise something the company will not honour.
PROMISE_PATTERNS = [
    (re.compile(r'(أضمن|بضمن|متأكد\s+إن|أوعدك|بوعدك)'), 'a promise the company has not made'),
    # "The money arrived" is the accountant's sentence, and the system sends it
    # when they press Accept. These catch the assistant AFFIRMING it — not
    # "لما التحويل يوصل" or "استلمنا صورة التحويل", which it now says all day.
    # With or without «ال»: "وصلنا تحويل من حضرتك" went out to the client's GM
    # as the first line of a greeting (2026-10-01) because only «التحويل» was caught.
    (re.compile(r'(?<![يتهن])(وصل|وصلنا|وصلتنا|وصلت)\s+(ال)?(تحويل|فلوس|مبلغ)'), 'confirming money arrived'),
    (re.compile(r'(التحويل|الفلوس|المبلغ)\s+(وصل|وصلت|وصلنا|اتأكد|اتأكدت)(?!\w)'), 'confirming money arrived'),
    (re.compile(r'(تم|اتأكدنا\s+من)\s+(تأكيد\s+)?(استلام|وصول)\s+(ال)?(تحويل|فلوس|مبلغ|مقدم)'), 'confirming money arrived'),
    # The mandated name of the booking payment is «مقدم التعاقد», so the
    # affirmations use it too: "وصل مقدم التعاقد", "مقدم التعاقد وصل".
    (re.compile(r'(?<![يتهن])(وصل|وصلنا|وصلتنا|وصلت|اتسجل|اتسجّل)\s+(ال)?مقدم'), 'confirming money arrived'),
    (re.compile(r'مقدم\s+(ال)?تعاقد\s+(وصل|وصلنا|اتأكد|اتسجل|اتسجّل|اتقبل)(?!\w)'), 'confirming money arrived'),
    # "استلمنا التحويل/المبلغ" affirms the money; "استلمنا صورة التحويل" does not,
    # so the noun must follow the verb directly.
    (re.compile(r'(استلمنا|استلمت|اتسجّل|اتسجل)\s+(ال)?(تحويل|فلوس|مبلغ|مقدم)'), 'confirming money arrived'),
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

    # No language check (owner, 2026-09-30): an English address, car name or
    # word inside an Arabic reply is normal writing, and flagging it only put
    # noise in the thread. `expect_arabic` stays for callers that pass it.
    foreign =[host for host in re.findall(r'https?://([^/\s?#]+)', text)
               if not host.lower().split(':')[0].endswith(LINK_HOSTS)]
    if foreign:
        problems.append({'rule': 'foreign_link', 'severity': 'warn',
                         'why': f'a link that is not the company\'s: {", ".join(foreign[:3])}'})

    untraceable = _untraceable_figures(text, allowed_figures or [])
    if untraceable:
        problems.append({'rule': 'untraceable_figure', 'severity': 'block',
                         'why': f'figures no tool returned this turn: {", ".join(untraceable[:5])}'})

    return problems


#: An Egyptian national ID: 14 digits, the first 2 (born 1900s) or 3 (2000s).
NATIONAL_ID = re.compile(r'^[23]\d{13}$')


def _unapproved_account(text, allowed_text):
    """An account-shaped string the tools did not hand over this conversation.
    The approved bank template arrives through a tool; relaying it is the job.

    Two long numbers are not accounts: a national ID (the assistant reads it
    back when it saves the contract details) and a phone number written with
    its + — both used to block a correct reply and hand the customer over."""
    approved = _normalise_number(allowed_text)
    clean = text.replace('،', '')
    hits = [m.group(0) for m in ACCOUNT_LIKE.finditer(clean)
            if not clean[max(0, m.start() - 1):m.start()] == '+']
    hits += [m.group(0) for m in IBAN_LIKE.finditer(text)]
    for hit in hits:
        digits = _normalise_number(hit)
        if NATIONAL_ID.match(digits or ''):
            continue
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


_UNIT_AFTER = re.compile(r'^\s{0,2}(مليون|ألف|الف|آلاف)')
_PERCENT_AFTER = re.compile(r'^\s{0,2}[%٪]')


def _scaled(raw, factor):
    """'3.45' × a million as the digits a tool would have returned, or ''."""
    exact = [f for f in _canonical(raw) if not f.startswith('~')]
    try:
        return str(int(round(float(exact[0]) * factor))) if exact else ''
    except ValueError:
        return ''


def _untraceable_figures(text, allowed, with_percent=True):
    """Amounts of money in the reply that no tool, search or rule supplied.

    «3.8 مليون» is an amount though it is two digits: until 2026-10-09 the
    three-digit floor let «3.5 لـ 3.8 مليون جنيه» — a dealer's price the
    assistant made up — through without so much as a note. A figure in
    millions or thousands is also accepted when the tools returned it written
    out (3.45 مليون against 3,450,000)."""
    allowed_forms, allowed_exact = set(), set()
    for a in allowed:
        for form in _canonical(a):
            allowed_forms.add(form.lstrip('~'))
            if not form.startswith('~'):
                allowed_exact.add(form)
    text = _EUR1.sub(' ', str(text or '').translate(_ARABIC_DIGITS))
    found = []
    for match in _STANDALONE_NUMBER.finditer(text):
        raw = match.group(1)
        after = text[match.end():match.end() + 12]
        unit = _UNIT_AFTER.match(after)
        million = bool(unit and unit.group(1) == 'مليون')
        number = _normalise_number(raw)
        if not number or (len(number) < 3 and not million):
            continue                  # counts, small percentages, a year's last digits
        is_money = (_MONEY_AFTER.match(after)
                    or _MONEY_BEFORE.search(text[max(0, match.start() - 2):match.start()]))
        if not is_money:
            continue                  # a model, a year, an engine size, a mileage
        if not with_percent and _PERCENT_AFTER.match(after):
            continue
        forms = _canonical(raw)
        if million:
            if ({f for f in forms if not f.startswith('~')} & allowed_exact
                    or _scaled(raw, 1000000) in allowed_forms):
                continue
        elif ({f.lstrip('~') for f in forms} & allowed_forms
              or (unit and _scaled(raw, 1000) in allowed_forms)):
            continue
        found.append(f'{raw} {unit.group(1)}' if unit else raw)
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


def holding_text(topic=''):
    """The line a customer gets when this turn hands them over.

    One topic carries more than the holding line. Asked whether a car is full
    or medium, the customer is shown the six options that decide it, in the
    client's words, and told sales will explain (client, 2026-10-07: «نعرضلو
    الخيارات … ونقولو هنحولك لفريق المبيعات يشرحلك التفصيل»). It is sent from
    here, not written by the model: on 2026-10-07 the model listed six options
    of its own — Burmester, 360° cameras — and decided the tier itself."""
    if str(topic or '').strip().lower() == 'trim_check':
        from car_import.models.vehicle import TIER_OPTION_FIELDS, TIER_OPTIONS_AR
        options = '\n'.join(f'• {TIER_OPTIONS_AR[field]}' for field in TIER_OPTION_FIELDS)
        return ('الفئة (كاملة ولا متوسطة) بتتحدد من الكماليات دي:\n' + options
                + '\nهحوّل حضرتك لفريق المبيعات يشرحلك التفاصيل ويأكدلك فئة العربية دي.')
    return HOLDING_TEXT


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


def figures_from_customer(conversation, since):
    """Numbers the customer gave us: what they typed, and what their advert
    screenshots show (the channel stores a description of every image). A price
    read off the customer's own screenshot is not an invented figure — it was
    flagged as one twice on 2026-10-01."""
    if conversation is None or since is None:
        return []
    try:
        from modules.chat.models import Message
        rows = (Message.objects.filter(conversation=conversation, direction='inbound',
                                       created_at__gte=since).values_list('content', flat=True))
        return [m.group(0) for content in rows
                for m in re.finditer(r'\d[\d.,]{1,}', str(content or '').translate(_ARABIC_DIGITS))]
    except Exception:
        logger.exception("car_import: could not read the customer's own figures")
        return []


def figures_on_file(conversation):
    """The customer's own quotations and proforma invoices: the assistant is
    briefed with them every turn (`turn_context.sales_facts`) and may say them."""
    partner = getattr(conversation, 'social_partner', None) if conversation is not None else None
    if partner is None:
        return []
    figures = []
    try:
        from car_import.models import ProformaInvoice, Quote
        for row in Quote.all_objects.filter(partner_id=partner.pk).order_by('-id')[:5]:
            figures += [row.total_eur, row.deposit_eur, row.balance_eur, row.remaining_eur, row.paid_eur,
                        row.deposit_pct, row.customs_eur, row.poa_usd, row.egp_due_on_arrival]
        for row in ProformaInvoice.all_objects.filter(partner_id=partner.pk).order_by('-id')[:5]:
            figures += [row.total_amount, row.amount_due, row.remaining_due]
    except Exception:
        logger.exception("car_import: could not read the customer's quotations for the gate")
    return [f'{value:,.2f}' for value in figures if value]


def say_from_tools(conversation, since):
    """The sentence the last tool of this turn asked to be said to the customer
    (`say_to_customer_ar`), or ''.

    A tool that needs one answer first — «حضرتك معاك مبادرة؟», the ID card —
    returns the sentence to say. The model usually says it; now and then it
    returns nothing at all (seen 2026-10-04, same input, one run in two), and
    the bridge reads silence as a failed run. The gate sends this instead."""
    if conversation is None or since is None:
        return ''
    try:
        import json

        from modules.chat.models import Message
        rows = list(Message.objects_all.filter(conversation=conversation, type='tool', created_at__gte=since)
                    .order_by('-created_at').values_list('content', flat=True)[:1])
        if not rows:
            return ''
        content = rows[0] if isinstance(rows[0], dict) else {}
        output = content.get('tool_output')
        payload = json.loads(output) if isinstance(output, str) else (output or {})
        if not isinstance(payload, dict):
            return ''
        data = payload.get('data') if isinstance(payload.get('data'), dict) else {}
        return str(payload.get('say_to_customer_ar') or data.get('say_to_customer_ar') or '').strip()
    except Exception:
        logger.exception("car_import: could not read the tool's sentence for the customer")
        return ''


FIGURE_WINDOW_HOURS = 72

#: Under the selling policy, the only replies worth stopping are the two that
#: cost money the moment they are read: an account number the accountant did
#: not write, and "your money arrived". Everything else is sent and FLAGGED —
#: a note to the people watching, next to the reply. A block hands the customer
#: to a queue, and the client's instruction is that staff monitor, not answer:
#: a false alarm there is a customer talking to nobody.
BLOCKING_UNDER_AI_FIRST = {'bank_details'}
DEPOSIT_PROMISE_WHY = 'promising the deposit back to a customer the company provides the initiative to'
#: …and one that promises a customer thousands of dollars that will never come
#: back to them (owner, 2026-10-07 and again 2026-10-09).
BLOCKING_WHY_UNDER_AI_FIRST = {'confirming money arrived', DEPOSIT_PROMISE_WHY}

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


def allowed_figures(conversation, since):
    """Every number the assistant may say this turn: what the tools returned in
    the last three days, what its rules tell it to say, what the customer wrote,
    what is on the customer's quotations, and the dealer sentence."""
    from datetime import timedelta
    window = (since - timedelta(hours=FIGURE_WINDOW_HOURS)) if since is not None else None
    figures = (figures_from_tool_messages(conversation, window) + _prompt_figures()
               + figures_from_customer(conversation, window) + figures_on_file(conversation))
    try:
        from car_import.services import policy
        figures += figures_in(policy.dealer_gap_text())
    except Exception:
        logger.exception('car_import: could not read the dealer sentence for the gate')
    return figures


# ── the owner's rules of 2026-10-09, as checks ───────────────────────────────
#: Two of these in one reply is a list of options. The owner: «مش عايزينه يكتب
#: إيه الكماليات أو يدي مثال» — the cars come «كاملة أو بريميوم بلس», full stop.
OPTION_TERMS = ('فتحة سقف', 'فتحه سقف', 'بانوراما', 'كراسي جلد', 'كراسي كهربا', 'ميموري', 'شنطة كهربا',
                'شنطه كهربا', 'عداد ديجيتال', 'إضاءة led', 'اضاءة led', 'مساعدة قيادة', 'كاميرا خلفية',
                'كاميرات 360', 'burmester', 'تعليق هوائي', 'مثبت سرعة', 'مقاعد مدف')

#: "It comes back to YOU" — the deposit, said to the customer.
_REFUND_TO_YOU = re.compile(
    r'(بترجعلك|بترجع لك|بترجع لحضرتك|بترجعهالك|بترجعها لك|بتترجعلك|بتترجع لك|بتترجع لحضرتك|هترجعلك|هترجع لك|'
    r'هترجع لحضرتك|هتترجعلك|هتترجع لحضرتك|ترجعلك|بتستردها|هتستردها|تستردها|هتسترد|بتسترد)')


def lists_options(text):
    low = str(text or '').lower()
    return sum(1 for term in OPTION_TERMS if term in low) >= 2


def promises_deposit_back(text):
    """True when the reply tells the customer the deposit returns to them —
    not when it denies it («مش بتستردها»), and not when it states the
    condition («لو حضرتك صاحب المبادرة … بترجعلك»)."""
    text = str(text or '')
    for match in _REFUND_TO_YOU.finditer(text):
        if 'مش' in text[max(0, match.start() - 12):match.start()]:
            continue
        lead = text[max(0, match.start() - 90):match.start()]
        if 'لو ' in lead and 'صاحب المبادر' in lead:
            continue
        return True
    return False


def company_provides_initiative(conversation):
    """True when this customer's initiative is the company's: they said they
    hold none, or their latest initiative offer charges the powers of attorney."""
    partner = getattr(conversation, 'social_partner', None) if conversation is not None else None
    if partner is None:
        return False
    try:
        from car_import.models import Quote
        from car_import.services import agent_help
        holds = agent_help.known_initiative(partner)
        if holds is not None:
            return holds is False
        quote = (Quote.all_objects.filter(partner_id=partner.pk, programme='initiative')
                 .exclude(total_eur=0).order_by('-id').first())
        return bool(quote is not None and quote.own_initiative is not True and quote.poa_usd is not None)
    except Exception:
        logger.exception('car_import: could not tell whose initiative it is')
        return False


def _owner_rule_problems(text, conversation):
    problems = []
    if lists_options(text):
        problems.append({'rule': 'options_list', 'severity': 'warn', 'why': 'a list of options'})
    if promises_deposit_back(text) and company_provides_initiative(conversation):
        problems.append({'rule': 'promise', 'severity': 'block', 'why': DEPOSIT_PROMISE_WHY})
    return problems


def correctable(text, conversation, since):
    """What is wrong with this reply that one more run can put right — as the
    sentences the model is told, or [] when the reply may go.

    The gate could only do two things with a reply: send it with a note to
    staff, or stop it and hand the customer over. Neither fits a made-up price:
    sent, the customer has read it; stopped, they wait for a person over
    something the assistant can simply say properly. So the reply is dropped
    unseen and written again, once (`patches._corrected`)."""
    from car_import.services import policy, turn_context
    reasons = []
    invented = _untraceable_figures(text, allowed_figures(conversation, since), with_percent=False)
    if invented:
        partner = getattr(conversation, 'social_partner', None) if conversation is not None else None
        sentence = turn_context.dealer_gap_line(partner) if partner is not None else policy.dealer_gap_text()
        reasons.append(
            'فيه أرقام فلوس مش راجعة من أي أداة (%s). ممنوع أي سعر لعربية في مصر أو عند الوكيل، وأي نطاق أسعار، وأي '
            'تحويل لجنيه، وأي مثال بالأرقام من عندك. لو الكلام عن الفرق عن الوكيل: «%s» وبس.'
            % ('، '.join(invented[:5]), sentence))
    if lists_options(text):
        reasons.append('فيه تعديد كماليات. ممنوع تعدّ كماليات أو تدي أمثلة: قول بس «%s».'
                       % turn_context.OPTIONS_LINE_AR)
    if promises_deposit_back(text) and company_provides_initiative(conversation):
        reasons.append('قلت إن الوديعة بترجع للعميل، والشركة هي اللي موفّرة المبادرة: «قيمة الوديعة مش بتستردها '
                       'حضرتك — بيستردها صاحب المبادرة بس».')
    return reasons


def retry_hint(reasons):
    return ('[SYSTEM — ردّك اللي فات اتلغى قبل ما يوصل للعميل، والعميل مشافوش. السبب: ' + ' '.join(reasons)
            + ' اكتب الرد على رسالة العميل من جديد، قصير، من غير الحاجات دي، ومن غير ما تذكر إن فيه رد اتلغى.]')


#: Tools that only read. A run that called anything else did something — sent
#: an offer, filed a receipt, handed over — and must not be run a second time.
READ_ONLY_TOOLS = {'search_ka_approved_answers', 'ka_search_cars', 'ka_initiative_deposit', 'ka_customs_value'}


def run_was_read_only(conversation, since):
    """True when every tool this run called only looked something up."""
    if conversation is None or since is None:
        return False
    try:
        from modules.chat.models import Message
        rows = Message.objects_all.filter(conversation=conversation, type='tool_call',
                                          created_at__gte=since).values_list('content', flat=True)
        for content in rows:
            content = content if isinstance(content, dict) else {}
            name = content.get('tool_name')
            args = content.get('tool_input') if isinstance(content.get('tool_input'), dict) else {}
            if name in READ_ONLY_TOOLS:
                continue
            if name == 'ka_quote_car' and not args.get('send_offer'):
                continue                  # a price only: nothing is recorded or sent
            if name == 'ka_deal_status' and not args.get('send_update'):
                continue
            return False
        return True
    except Exception:
        logger.exception("car_import: could not read this run's tool calls")
        return False


def note_correction(conversation, dropped, reasons):
    """The reply that was dropped, on the record for the people watching."""
    _note(conversation,
          '♻️ رد المساعد اتلغى قبل ما يوصل للعميل واتكتب تاني:\n' + '\n'.join(f'- {r}' for r in reasons)
          + '\n\nالرد اللي اتلغى (العميل مشافوش):\n' + str(dropped),
          subject='رد المساعد اتكتب تاني')


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
    problems = check_reply(text, allowed_figures=allowed_figures(conversation, since),
                           allowed_text=tool_text(conversation, window))
    problems += _owner_rule_problems(text, conversation)
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
