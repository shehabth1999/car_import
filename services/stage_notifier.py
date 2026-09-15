# -*- coding: utf-8 -*-
"""
Telling the customer, every time their car moves.

The rule the client asked for: when a deal enters the next shipping stage, the
customer hears about it automatically, on whatever channel they already use.
Every stage sends automatically except cancellation (client, 2026-09-14).

Nothing here is AI-generated. The wording is fixed, owner-approved text held on
the stage, because mixing generated text into a Meta-approved template is how
templates get rejected.
"""
import logging
from collections import defaultdict
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

#: How long WhatsApp lets us send free text after the customer's last message.
WHATSAPP_WINDOW = timedelta(hours=24)

#: Turn every customer message off at once (data migrations, bulk edits).
KILL_SWITCH_KEY = 'car_import.stage_messages_enabled'


def messages_enabled():
    """False only when someone has explicitly switched stage messages off."""
    try:
        from modules.base.models import ConfigParameter
    except Exception:  # pragma: no cover - the parameter model is optional
        return True
    try:
        row = ConfigParameter.objects.filter(key=KILL_SWITCH_KEY).values('value').first()
    except Exception:
        return True
    if not row:
        return True
    return str(row['value']).strip().lower() not in ('0', 'false', 'no', 'off')


def log_and_notify_stage_change(deal, from_stage_id, to_stage_id):
    """
    Write the audit row for a stage move and queue the customer's message.

    Called from `CarDeal.post_save`, so it runs for a button, an automation rule
    or a list bulk-edit alike — which is exactly why the suppression switch lives
    here and not in the button.
    """
    from car_import.models import ImportStage, StageChangeLog

    stage = None
    if to_stage_id:
        stage = ImportStage.objects.filter(pk=to_stage_id).first()

    state = _initial_notification_state(deal, stage)

    log = StageChangeLog.objects.create(
        deal=deal,
        from_stage_id=from_stage_id,
        to_stage_id=to_stage_id,
        changed_by=_acting_user(deal),
        reason=deal.blocked_reason if deal.stage_is_blocked else '',
        notification_state=state,
    )

    if state == 'pending':
        from car_import.tasks import notify_stage_change
        delay = (stage.send_delay_minutes or 0) if stage else 0
        transaction.on_commit(
            lambda: notify_stage_change.apply_async((str(log.pk),), countdown=delay * 60)
        )
    return log


def _initial_notification_state(deal, stage):
    if stage is None:
        return 'skipped'
    if not stage.notify_customer:
        return 'skipped'
    if deal.state == 'cancelled':
        # Cancellation is the one stage a human always handles (client, 2026-09-14).
        return 'skipped'
    if deal.notifications_suppressed or not messages_enabled():
        return 'suppressed'
    if stage.requires_agent_approval:
        return 'awaiting_approval'
    return 'pending'


def _acting_user(deal):
    try:
        return getattr(deal.env, 'user', None) or None
    except Exception:
        return None


# ── the message itself ──────────────────────────────────────────────────────

def render_stage_message(deal, stage, language='ar'):
    """Fill the stage's text with this deal's facts. Missing values become ''."""
    template = (stage.fallback_text_ar if language == 'ar' else stage.fallback_text_en) or ''
    if not template:
        template = stage.fallback_text_en or stage.fallback_text_ar or ''
    return template.format_map(defaultdict(str, stage_placeholders(deal, stage)))


def stage_placeholders(deal, stage):
    vehicle = deal.vehicle
    partner = deal.partner
    values = {
        'customer_name': getattr(partner, 'name', '') or '',
        'agent_name': getattr(deal.assigned_to, 'name', '') or '',
        'stage_name': stage.name or stage.name_en or '',
        'deal_ref': deal.name or '',
        'model': f"{vehicle.make} {vehicle.model}".strip() if vehicle else '',
        'trim': getattr(vehicle, 'trim', '') or '',
        'model_year': str(getattr(vehicle, 'model_year', '') or ''),
        'colour': getattr(vehicle, 'colour_exterior', '') or '',
        'vin': getattr(vehicle, 'vin', '') or '',
        'port': deal.arrival_port or '',
        'vessel': deal.vessel or '',
        'bl_number': deal.bl_number or '',
        'acid_number': deal.acid_number or '',
        'eta': deal.eta.strftime('%Y-%m-%d') if deal.eta else '',
        'tracking_url': deal.tracking_url or '',
    }
    # Money is only ever what a human marked on the deal — never a computed figure.
    values['amount_paid'] = _money(deal.amount_paid_marked, deal.currency_note)
    values['amount_due'] = _money(deal.amount_due_marked, deal.currency_note)
    return values


def _money(amount, currency):
    if amount is None:
        return ''
    text = f"{amount:,.0f}".rstrip('0').rstrip('.') if amount == int(amount) else f"{amount:,.2f}"
    return f"{text} {currency}".strip()


# ── sending ─────────────────────────────────────────────────────────────────

def deliver(log):
    """
    Send one stage message and record what happened. Returns the updated log.

    Inside WhatsApp's 24-hour window (and on every other channel) the text goes
    out as a normal message; outside it, only an approved template may be used.
    """
    deal, stage = log.deal, log.to_stage
    if stage is None:
        return _mark(log, 'skipped', error='The stage was deleted before the message went out')

    partner = deal.partner
    if partner is None:
        return _mark(log, 'failed', error='The deal has no customer')

    text = render_stage_message(deal, stage)

    try:
        if _inside_whatsapp_window(partner) or not stage.whatsapp_template_id:
            result = _send_free_text(partner, text)
            channel = result.get('channel') or 'omnichannel'
            message_id = str(result.get('message_id') or result.get('social_id') or '')
            if result.get('success') is False or result.get('status') is False:
                return _mark(log, 'failed', text=text, channel=channel,
                             error=str(result.get('error') or result.get('message') or 'send failed'))
        else:
            result = stage.whatsapp_template.send_template_message(
                _sender_partner(deal), partner,
            )
            channel = 'whatsapp_template'
            message_id = str(result.get('message_id') or '') if isinstance(result, dict) else ''
            if isinstance(result, dict) and result.get('status') is False:
                return _mark(log, 'failed', text=text, channel=channel,
                             error=str(result.get('message') or 'template send failed'))
    except Exception as exc:  # noqa: BLE001 - the outcome belongs in the log, not a traceback
        logger.exception("car_import: stage message failed for deal %s", deal.pk)
        return _mark(log, 'failed', text=text, error=str(exc))

    return _mark(log, 'sent', text=text, channel=channel, message_id=message_id)


def _send_free_text(partner, text):
    from modules.chat.services.omnichannel_send_service import OmnichannelSendService
    return OmnichannelSendService().send_and_broadcast(partner, {'text': text}, message_type='text') or {}


def _sender_partner(deal):
    """Whose WhatsApp account the template goes out from."""
    return getattr(deal.assigned_to, 'partner', None)


def _inside_whatsapp_window(partner):
    from modules.chat.models import Conversation, Message

    conversation = (
        Conversation.objects
        .filter(social_partner=partner, type='whatsapp')
        .order_by('-last_message_time', '-id')
        .first()
    )
    if conversation is None:
        return False
    last_inbound = (
        Message.objects
        .filter(conversation=conversation, direction='inbound')
        .order_by('-created_at')
        .values('created_at')
        .first()
    )
    if not last_inbound:
        return False
    return timezone.now() - last_inbound['created_at'] < WHATSAPP_WINDOW


def _mark(log, state, text='', channel='', message_id='', error=''):
    log.notification_state = state
    if text:
        log.message_text = text
    if channel:
        log.channel_used = channel
    if message_id:
        log.message_id = message_id
    if error:
        log.error = error
    log.save(update_fields=['notification_state', 'message_text', 'channel_used',
                            'message_id', 'error', 'updated_at'])
    return log
