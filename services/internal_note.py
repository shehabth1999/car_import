# -*- coding: utf-8 -*-
"""Say it in the conversation, not only in somebody's notification bell.

The client's instruction on 2026-09-16: whenever the system pulls a colleague
into a conversation, *"write message type note with the price you will say and
then let someone continue the chatting"* — and *"before make notification for
users to come to conversations, write the same notification message as a note
mention too"*.

They are right, and the reason is worth writing down. A notification says
"someone needs you" and then sends you somewhere to work out why. A note sitting
in the thread says what is needed, where the answer will be typed, next to the
customer's own words. The colleague who opens the chat reads the note and the
question together, and the note is still there tomorrow for whoever picks the
conversation up next — which a notification, read once and cleared, is not.

`is_internal=True` is the platform's own flag for this (`chat/models.py:2250`):
the message renders in the thread and is never handed to WhatsApp, Messenger or
any other provider. Nothing here can reach a customer.

One thing this has to do itself. Mentions normally notify from the websocket
consumer (`_dispatch_mention_notifications`), which only runs when a human types
into a socket — a message created from Python fires nothing. So this posts the
note, broadcasts it, and sends the inbox/push notification explicitly. Skipping
that last step would produce a note nobody is told about, which is the quietest
possible way to lose a customer's money question.
"""
import logging

logger = logging.getLogger(__name__)

#: Falls back through these when no better author exists. The note is written by
#: the system, and attributing it to whichever human happens to be online would
#: put words in their mouth.
AI_PARTNER_EMAIL = 'genie@genie-erp.com'


def post(conversation, body, recipients=(), subject='', url='', category='car_import'):
    """Post an internal note that @-mentions people, and notify them.

    `recipients` is an iterable of Django users. Returns True when the note was
    written — the notification is best-effort and never takes the note down
    with it, because a note in the thread is the part that still helps tomorrow.
    """
    if conversation is None or not (body or '').strip():
        return False

    users = [u for u in recipients if u is not None]
    mentions, prefix = _mentions_for(users)
    text = f'{prefix}{body}' if prefix else body

    message = _write(conversation, text, mentions)
    if message is None:
        return False

    _broadcast(conversation, message)
    _notify(users, subject or _first_line(body), body, url or _chat_url(conversation), category)
    return True


# ── the note ───────────────────────────────────────────────────────────────
def _write(conversation, text, mentions):
    try:
        from modules.base.models import Partner
        from modules.chat.models import Message
    except Exception:
        logger.warning('car_import: chat is not installed; internal note skipped')
        return None

    author = (Partner.all_objects.filter(ai_agent=True, email=AI_PARTNER_EMAIL).first()
              or Partner.all_objects.filter(ai_agent=True).first())
    if author is None:
        # Without an author there is no message. Better to say so than to
        # attribute a system note to a random person.
        logger.warning('car_import: no AI partner to author the internal note')
        return None

    try:
        return Message.objects.create(
            conversation=conversation,
            sender=author,
            type='text',
            content={'text': text},
            # Deliberately NOT 'outbound'. Direction is what the send path reads
            # to decide a message is bound for a provider; an internal note has
            # no destination outside this screen.
            is_internal=True,
            mentions=mentions,
        )
    except Exception:
        logger.exception('car_import: could not write the internal note')
        return None


def _mentions_for(users):
    """`[{id, name, type}]` plus the `@id` tokens the composer would have typed.

    The stored text carries `@<user id>`, not `@<name>` — that is the platform's
    format (`chat/utils/mentions.py`), and every preview expands the tokens back
    to names from this same payload. Writing the name directly would look right
    in the thread and read as a dead string everywhere else.
    """
    mentions, tokens = [], []
    for user in users:
        name = (getattr(user, 'name', '') or getattr(user, 'username', '') or '').strip()
        if not name:
            continue
        mentions.append({'id': str(user.id), 'name': name, 'type': 'user'})
        tokens.append(f'@{user.id}')
    return mentions, (' '.join(tokens) + '\n') if tokens else ''


def _broadcast(conversation, message):
    """Push the note to the agents who already have the chat open."""
    try:
        from modules.chat.services.chat_bridge_service import ChatBridgeService
        ChatBridgeService()._send_to_conversation_participants_personalized(
            conversation, message.id)
    except Exception:
        # A note that failed to broadcast is still in the thread on next load.
        logger.exception('car_import: could not broadcast the internal note')


# ── telling them it is there ───────────────────────────────────────────────
def _notify(users, subject, body, url, category):
    partner_ids = [u.partner_id for u in users if getattr(u, 'partner_id', None)]
    if not partner_ids:
        return
    try:
        from modules.notifications.services.post_notification import post_notification
        # `subject`, not `title` — the wrong keyword raised on every call once
        # before, and the except swallowed it while the caller reported success.
        post_notification(partner_ids=partner_ids, subject=subject, body=body,
                          url=url, category=category)
    except Exception:
        logger.exception('car_import: could not notify about the internal note')


def _chat_url(conversation):
    return f'/chat/?chat={conversation.pk}'


def _first_line(body):
    for line in (body or '').splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned[:120]
    return 'ملاحظة داخلية'
