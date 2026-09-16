# -*- coding: utf-8 -*-
"""File the paperwork a customer sends in the chat against what it satisfies.

Vision already reaches the assistant: an inbound photo is described by the
account's vision model before the workflow starts, and the model sees the
description (or the image itself). What did not exist was the last step —
nothing put the photo anywhere. A customer sent their bank statement, the
assistant said "thank you", and the document lived in a WhatsApp thread until
somebody scrolled back to find it.

This tool takes the newest image or document the customer sent and files it as
the `DealDocument` for the requirement the assistant names. The chat keeps its
own attachment model (`chat.MessageAttachment`); the deal's document points at
the platform's (`base.Attachment`). Rather than copying bytes, a second record
is opened over the **same stored file**, so there is one file on disk and two
things that know where it is.

The sensitivity rule is the same one the checklist tool applies: a national ID
or passport that arrives in a social thread is filed — refusing would lose it
— but the reply tells the assistant not to invite more of them into the chat.
"""
import logging
from typing import Any, Dict

from modules.aistudio.tools import tool

logger = logging.getLogger(__name__)

#: Message types that can carry paperwork. Stickers and voice notes cannot.
DOCUMENT_MESSAGE_TYPES = ('image', 'document', 'file')

#: chat file_type -> base Attachment type
ATTACHMENT_TYPE = {'image': 'image', 'pdf': 'pdf', 'document': 'document', 'file': 'document'}


@tool(
    name="ka_file_customer_document",
    display_name="File a document the customer sent",
    description=(
        "Use this tool the moment the customer sends a photo or scan of a required document "
        "(ID, passport, residence permit, bank statement, deposit receipt, import approval, "
        "power of attorney). Before calling it you MUST know which requirement the picture "
        "satisfies — take the `requirement_code` from ka_get_document_checklist's list. It files "
        "the newest image or file the customer sent against that requirement on their open deal "
        "and returns what is still missing. Call it once per document. Do NOT call it for photos "
        "of cars, screenshots of adverts, or anything that is not paperwork."
    ),
    category="car_import",
    side_effect=True,
    parameters_schema={
        "type": "object",
        "properties": {
            "requirement_code": {
                "type": "string",
                "description": "The requirement this document satisfies, e.g. national_id_front_back, "
                               "passport, residence_permit, bank_statement_6m, deposit_receipts, "
                               "import_approval, customs_broker_poa",
            },
            "note": {"type": "string",
                     "description": "Optional: anything the customer said about it, in Arabic"},
        },
        "required": ["requirement_code"],
    },
)
def ka_file_customer_document(context, requirement_code: str, note: str = '') -> Dict[str, Any]:
    """File the newest inbound attachment as the deal's document for that requirement."""
    try:
        from car_import.models import DealDocument, DocumentRequirement
        from car_import.services.documents import checklist_status
        from car_import.tools.deal_tools import _deal_for

        deal = _deal_for(context)
        if deal is None:
            return {"success": False, "error": "No open deal for this customer",
                    "error_type": "not_found",
                    "say_to_customer_ar": "هحتفظ بالصورة لحد ما زميلي يفتح لحضرتك ملف — ثانية واحدة وهوصّلك بيه."}

        requirement = DocumentRequirement.objects.filter(code=(requirement_code or '').strip()).first()
        if requirement is None:
            known = list(DocumentRequirement.objects.values_list('code', flat=True))
            return {"success": False, "error": f"Unknown requirement '{requirement_code}'",
                    "error_type": "unknown_requirement", "data": {"known_codes": known}}

        source = _newest_inbound_attachment(getattr(context, 'conversation', None))
        if source is None:
            return {"success": False, "error": "The customer has not sent an image or file",
                    "error_type": "no_attachment",
                    "say_to_customer_ar": "مش لاقية الصورة — ممكن حضرتك تبعتها تاني؟"}

        attachment = _mirror(source)
        if attachment is None:
            return {"success": False, "error": "Could not register the attachment",
                    "error_type": "attachment_failed"}

        row, created = DealDocument.objects.get_or_create(
            deal=deal, requirement=requirement,
            defaults={'name': requirement.name, 'state': 'uploaded'})
        row.file = attachment
        row.state = 'uploaded'          # pre_save stamps received_at
        if note:
            row.note = (row.note + '\n' if row.note else '') + note.strip()
        row.save()
        deal.message_post(body=f"العميل بعت: {requirement.name} — اتحفظ للمراجعة.")

        status = checklist_status(deal)
        reply = {
            "success": True,
            "data": {
                "filed": requirement.name,
                "requirement_code": requirement.code,
                "state": "uploaded",
                "deal_reference": deal.name,
                "still_missing": [r['name'] for r in status['outstanding'] if r['state'] == 'missing'],
                "waiting_check": status['waiting_check'],
                "complete": status['complete'],
            },
        }
        if requirement.is_sensitive:
            # Filed — losing it would be worse — but say so, once.
            reply["data"]["note"] = ("This is a sensitive document. Thank the customer, do not ask for "
                                     "more of these in the chat; a colleague arranges the rest.")
        return reply
    except Exception as e:
        logger.exception("ka_file_customer_document failed")
        return {"success": False, "error": str(e), "error_type": "unknown"}


def _newest_inbound_attachment(conversation):
    """The last image/file the CUSTOMER sent — never something we sent them."""
    if conversation is None:
        return None
    try:
        from modules.chat.models import Message
        message = (Message.objects.filter(conversation=conversation, direction='inbound',
                                          type__in=DOCUMENT_MESSAGE_TYPES)
                   .select_related('attachment').order_by('-created_at').first())
    except Exception:
        logger.exception('car_import: could not read the conversation for an attachment')
        return None
    if message is None:
        return None
    return getattr(message, 'attachment', None)


def _mirror(source):
    """A `base.Attachment` over the chat attachment's stored file.

    No bytes are copied: `file.name` is the storage path, and pointing a second
    record at it gives the deal a document without a second copy on disk.
    """
    try:
        from modules.base.models.attachment import Attachment
        if not getattr(source, 'file', None) or not source.file.name:
            return None
        row = Attachment(
            name=source.file_name or source.file.name.rsplit('/', 1)[-1],
            mime_type=source.mime_type or 'application/octet-stream',
            type=ATTACHMENT_TYPE.get(source.file_type, 'document'),
            size=source.file_size or 0,
            original_url=source.platform_url or None,
        )
        row.file.name = source.file.name
        row.save()
        return row
    except Exception:
        logger.exception('car_import: could not mirror chat attachment %s', getattr(source, 'pk', None))
        return None
