# -*- coding: utf-8 -*-
"""What the chat-header actions need: the customer behind a conversation, their
open deal and lead, and a note in the thread saying what was done.

The actions themselves (`extensions.py :: ConversationExtension`) are thin —
they resolve the customer, then open an existing form or wizard pre-filled.
Nothing here is a second business path: deals, quotes and stage moves are
created through the same forms and actions the module already has.
"""
from django.utils.translation import gettext as _


def partner_of(conversation):
    """The customer in a social conversation, or None for a company thread."""
    if conversation is None:
        return None
    partner = getattr(conversation, 'social_partner', None)
    return partner or None


def open_deal_for(partner):
    """The customer's most recent deal that is not cancelled or closed."""
    from car_import.models import CarDeal
    if partner is None:
        return None
    return (CarDeal.all_objects.filter(partner_id=partner.pk)
            .exclude(state__in=['cancelled', 'closed', 'done'])
            .order_by('-id').first())


def latest_conversation_for(partner):
    from modules.chat.models import Message
    last = (Message.objects.filter(sender_id=partner.pk).order_by('-created_at')
            .select_related('conversation').first())
    return last.conversation if last else None


def lead_for(partner, create=False):
    """The customer's latest lead. With `create`, a missing lead is created the
    way an organic first message creates one, so it carries the channel."""
    if partner is None:
        return None
    from modules.crm.models import Lead
    lead = Lead.all_objects.filter(partner_id=partner.pk).order_by('-id').first()
    if lead is not None or not create:
        return lead
    conversation = latest_conversation_for(partner)
    try:
        from modules.crm.services.ad_lead import record_organic_lead
        lead = record_organic_lead(channel=getattr(conversation, 'type', None) or 'whatsapp',
                                   partner=partner,
                                   account=getattr(conversation, 'social_account', None))
    except Exception:
        lead = None
    return lead or Lead.all_objects.filter(partner_id=partner.pk).order_by('-id').first()


def ref(instance):
    """A relation default the form understands."""
    if instance is None:
        return None
    return {'id': instance.pk, 'name': str(getattr(instance, 'name', None) or instance)}


def no_customer():
    return {'status': False, 'open_mode': 'message', 'data': {},
            'message': _("This conversation has no customer attached.")}


def qualification_summary(form):
    parts = []
    if form.program:
        parts.append(str(form.get_program_display()) + (f' / {form.initiative_type}' if form.initiative_type else ''))
    car = ' '.join(str(x) for x in [form.model_wanted, form.model_year_wanted, form.trim_wanted,
                                    form.colour_wanted] if x)
    if car:
        parts.append(car + (f' ({form.get_condition_wanted_display()})' if form.condition_wanted else ''))
    if form.budget_eur:
        parts.append(f'{form.budget_eur} €')
    if form.funds_ready_on:
        parts.append(_("funds on %(date)s") % {'date': form.funds_ready_on})
    if form.residence_country:
        parts.append(form.residence_country)
    return ' · '.join(parts) or _("nothing new")


def note(partner, body, extra=None, user=None):
    """An internal note in the customer's thread — the audit trail the agents
    actually read. Best effort: a failed note never fails the action."""
    conversation = latest_conversation_for(partner) if partner is not None else None
    if conversation is None:
        return False
    try:
        from car_import.services import internal_note
        text = body if not extra else f'{body}\n{extra}'
        return internal_note.post(conversation, text, recipients=[u for u in [user] if u],
                                  subject=_("From the chat"))
    except Exception:
        return False
