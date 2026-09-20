# -*- coding: utf-8 -*-
"""The tools that let the assistant run the sale itself (`services/policy.py`).

Seven of them, in the order a sale actually goes:

    ka_search_showroom_cars     is it in the showroom in Egypt?
    ka_send_car_photos          the advert's photos, to the customer
    ka_price_car                the whole price of one car — read only
    ka_send_quotation           the formal offer, recorded and sent
    ka_issue_proforma_invoice   customer said yes → deal + proforma + bank details
    ka_record_payment_receipt   the transfer screenshot → ready for the accountant
    ka_save_contract_details    name and national ID as on the card → the contract
    ka_request_discount         management decides; the assistant keeps talking

Two rules shape every one of them.

**A figure comes from the engine or from a stored advert, never from the
model.** The price tool takes an advert reference and reads the price off the
row; a number the customer typed is accepted, marked as such on the quotation,
and shown to the people watching.

**A tool that messages the customer says so, and the assistant still writes a
line.** The channel bridge reads an empty reply as a failed run and re-runs the
whole turn — that is how a hand-over went out twice on 2026-09-17. So these
tools send the document and tell the model to follow with one short sentence.
"""
import logging
from datetime import date
from typing import Any, Dict, Optional

from django.core.exceptions import ValidationError

from modules.aistudio.tools import tool

logger = logging.getLogger(__name__)

_OPTIONS_SCHEMA = {
    "with_eur1": {"type": "boolean",
                  "description": "True when the car is EU-built and the customer wants the EUR 1 certificate"},
    "shipping_type": {"type": "string",
                      "description": "Leave empty for standard shipping, or vip_roro, or container"},
    "port": {"type": "string", "description": "alexandria (default) or port_said"},
    "collect_from_showroom": {"type": "boolean",
                              "description": "True when the customer collects the car from the Cairo showroom"},
}


def _fmt(value, symbol='€'):
    if value is None:
        return None
    text = f'{value:,.2f}'
    if text.endswith('.00'):
        text = text[:-3]
    return f'{text} {symbol}'


def _refused_by_policy():
    return {"success": False, "error": "The assistant is not selling by itself on this system",
            "error_type": "policy_off", "must_escalate": True}


def _partner(context):
    return getattr(context, 'partner', None)


def _resolve_price(listing_reference, gross_price_eur):
    """(listing, gross, source_note) or an error dict."""
    from car_import.services import policy, sales_flow

    if listing_reference:
        listing = sales_flow.find_listing(listing_reference)
        if listing is None:
            return {"success": False, "error": f"No stored advert with reference '{listing_reference}'. "
                                               "Search again and use a reference from the result.",
                    "error_type": "unknown_listing"}
        if listing.is_simulated and not policy.may_quote_simulated_cars():
            return {"success": False, "error": "This advert is simulated test data and must not be quoted",
                    "error_type": "simulated_listing", "must_escalate": True}
        if not listing.still_available:
            return {"success": False, "error": "This advert is no longer listed",
                    "error_type": "listing_gone",
                    "say_to_customer_ar": "الإعلان ده اتشال من الموقع — أدوّر لحضرتك على بديل؟"}
        if not listing.price_gross_eur:
            return {"success": False, "error": "The advert has no price", "error_type": "no_price",
                    "must_escalate": True}
        return listing, listing.price_gross_eur, ''

    gross = sales_flow.to_decimal(gross_price_eur)
    if gross is None or gross <= 0:
        return {"success": False, "error": "Give an advert reference, or the advert's price with VAT in EUR",
                "error_type": "no_price_source"}
    return None, gross, 'السعر ده العميل هو اللي قاله (أو من لينك بعته) — مش من إعلان محفوظ. راجعه.'


def _stack(result):
    """The calculator's answer in the words the customer will hear."""
    lines = [{'label': line['label_ar'], 'amount': _fmt(line['amount'])}
             for line in result['lines_eur'] if line['amount'] or line['code'] in ('gross', 'net')]
    egp = [{'label': line['label_ar'], 'amount': _fmt(line['amount'], 'ج.م')}
           for line in result['lines_egp'] if line['amount']]
    data = {
        "total_selling_price": _fmt(result['total_eur']),
        "deposit_percent": f"{float(result['deposit_pct']):g}%",
        "deposit_now": _fmt(result['deposit_eur']),
        "balance_after_deposit": _fmt(result['balance_eur']),
        "lines_eur": lines,
        "due_in_egypt_on_arrival": _fmt(result['egp_due_on_arrival'], 'ج.م'),
        "lines_egp": egp,
        "band": result['band'],
        "rules": ("State these figures exactly as written — do not round, convert or add to them. "
                  "The balance is due within 5 working days of contracting with the supplier. "
                  "Licensing is not included."),
    }
    if result.get('total_egp_indicative'):
        data["indicative_total_egp"] = _fmt(result['total_egp_indicative'], 'ج.م')
        data["egp_note"] = "Indicative only, at today's rate. The company does not promise a rate."
    return data


# ── showroom stock ───────────────────────────────────────────────────────────
@tool(
    name="ka_search_showroom_cars",
    display_name="Cars in the Egypt showroom",
    description=(
        "Use this tool when the customer asks whether a car is available in the showroom in Egypt, "
        "or wants a car that is ready now rather than imported. Before calling it you SHOULD have a "
        "make or model, but it also works with none to list what is in stock. Returns the available "
        "showroom cars with their price in Egyptian pounds, mileage and whether they are licensed. "
        "State the price exactly as returned. If nothing matches, say so and offer to import one."
    ),
    category="car_import",
    parameters_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Make and/or model, e.g. 'Mercedes GLA' or 'C200'"},
            "limit": {"type": "integer", "description": "How many to return, default 5", "default": 5},
        },
        "required": [],
    },
)
def ka_search_showroom_cars(context, query: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
    """Available showroom stock, with EGP prices."""
    try:
        from django.db.models import Q

        from car_import.models import ShowroomListing

        rows = ShowroomListing.objects.filter(state='available').select_related('vehicle')
        for word in str(query or '').split():
            rows = rows.filter(Q(title__icontains=word) | Q(vehicle__make__icontains=word)
                               | Q(vehicle__model__icontains=word) | Q(vehicle__trim__icontains=word))
        cars = [{
            'reference': f'SR-{row.pk}',
            'title': row.title,
            'price': _fmt(row.price_egp, 'ج.م') if row.price_egp else None,
            'negotiable': row.negotiable,
            'mileage_km': row.mileage_km,
            'licensed': row.licensed,
            'location': row.location or 'معرض التجمع الخامس',
            'photos_available': len([p for p in (row.photos or []) if p]),
        } for row in rows.order_by('-id')[:max(1, min(int(limit or 5), 15))]]
        return {"success": True, "data": {"count": len(cars), "cars": cars,
                                          "note": "A showroom price is in EGP and is final as listed; "
                                                  "the import calculator does not apply to these cars."}}
    except Exception as e:
        logger.exception("ka_search_showroom_cars failed")
        return {"success": False, "error": str(e), "error_type": "unknown"}


# ── photos ───────────────────────────────────────────────────────────────────
@tool(
    name="ka_send_car_photos",
    display_name="Send the car's photos",
    description=(
        "Use this tool when the customer asks to see a car, or right after you describe one they are "
        "interested in. Before calling it you MUST have the car's `reference` from "
        "ka_search_vehicle_listings or ka_search_showroom_cars. It sends up to three photos to the "
        "customer directly. After it succeeds, write one short line — do not describe the photos."
    ),
    category="car_import",
    side_effect=True,
    parameters_schema={
        "type": "object",
        "properties": {
            "reference": {"type": "string", "description": "The car's reference from a search result"},
            "count": {"type": "integer", "description": "How many photos, 1 to 3", "default": 3},
        },
        "required": ["reference"],
    },
)
def ka_send_car_photos(context, reference: str, count: int = 3) -> Dict[str, Any]:
    """Send the advert's photos on the customer's channel."""
    try:
        from car_import.models import ShowroomListing
        from car_import.services import sales_flow
        from car_import.services import stage_notifier

        partner = _partner(context)
        if partner is None:
            return {"success": False, "error": "No customer in context", "error_type": "no_partner"}
        ref = str(reference or '').strip()
        if ref.upper().startswith('SR-'):
            row = ShowroomListing.objects.filter(pk=ref[3:] if ref[3:].isdigit() else 0).first()
            photos, label = (row.photos if row else []), (row.title if row else '')
        else:
            row = sales_flow.find_listing(ref)
            photos, label = (row.images if row else []), (sales_flow.listing_label(row) if row else '')
        if row is None:
            return {"success": False, "error": f"No car with reference '{ref}'", "error_type": "not_found"}
        urls = [p if isinstance(p, str) else (p or {}).get('url') for p in (photos or [])]
        urls = [u for u in urls if u and str(u).startswith(('http://', 'https://', '/'))]
        if not urls:
            return {"success": False, "error": "This car has no photos on file", "error_type": "no_photos",
                    "say_to_customer_ar": "الصور مش عندي دلوقتي — هجيبهالك من زميلي."}
        if not stage_notifier.messages_enabled():
            return {"success": False, "error": "Customer messages are switched off",
                    "error_type": "messages_off"}

        from modules.chat.services.omnichannel_send_service import OmnichannelSendService
        sender, sent = OmnichannelSendService(), 0
        for index, url in enumerate(urls[:max(1, min(int(count or 3), 3))]):
            result = sender.send_and_broadcast(
                partner, {'url': sales_flow.absolute_url(url)}, message_type='image',
                caption=label if index == 0 else None) or {}
            if not (result.get('success') is False or result.get('status') is False):
                sent += 1
        if not sent:
            return {"success": False, "error": "The photos could not be sent", "error_type": "send_failed"}
        return {"success": True, "data": {"photos_sent": sent, "car": label,
                                          "next_step": "Write one short line, e.g. ask what they think."}}
    except Exception as e:
        logger.exception("ka_send_car_photos failed")
        return {"success": False, "error": str(e), "error_type": "unknown"}


# ── price ────────────────────────────────────────────────────────────────────
@tool(
    name="ka_price_car",
    display_name="Price a car (full stack)",
    description=(
        "Use this tool whenever the customer asks what a car will cost them. Before calling it you MUST "
        "have EITHER the car's `listing_reference` from ka_search_vehicle_listings (preferred — the price "
        "is read from the advert) OR the advert's price with VAT in EUR that the customer gave you. "
        "Returns the full price: net, shipping, company fees, total selling price, the deposit percent "
        "and amount, the balance, and what is due in Egyptian pounds on arrival. It writes nothing and "
        "sends nothing. State the figures exactly as returned. Do NOT use it for showroom cars."
    ),
    category="car_import",
    parameters_schema={
        "type": "object",
        "properties": {
            "listing_reference": {"type": "string",
                                  "description": "The advert reference from ka_search_vehicle_listings"},
            "gross_price_eur": {"type": "number",
                                "description": "Only when there is no reference: the advert price with VAT, in EUR"},
            **_OPTIONS_SCHEMA,
        },
        "required": [],
    },
)
def ka_price_car(context, listing_reference: Optional[str] = None,
                 gross_price_eur: Optional[float] = None, with_eur1: bool = False,
                 shipping_type: str = '', port: str = 'alexandria',
                 collect_from_showroom: bool = False) -> Dict[str, Any]:
    """The calculator's answer for one car. Read only."""
    try:
        from car_import.services import policy, pricing, sales_flow

        if not policy.ai_first():
            return _refused_by_policy()
        resolved = _resolve_price(listing_reference, gross_price_eur)
        if isinstance(resolved, dict):
            return resolved
        listing, gross, source_note = resolved
        try:
            result = sales_flow.price(gross, with_eur1=with_eur1, shipping_type=shipping_type,
                                      port=port, collect_from_showroom=collect_from_showroom)
        except pricing.PricingError as exc:
            return {"success": False, "error": str(exc), "error_type": "no_band", "must_escalate": True}
        data = _stack(result)
        data["car"] = sales_flow.listing_label(listing) if listing is not None else None
        data["advert_price_with_vat"] = _fmt(gross)
        if source_note:
            data["price_source"] = "customer_stated"
        data["next_step"] = ("If the customer is interested, send the formal offer with ka_send_quotation "
                             "using the same inputs.")
        return {"success": True, "data": data}
    except Exception as e:
        logger.exception("ka_price_car failed")
        return {"success": False, "error": str(e), "error_type": "unknown"}


# ── quotation ────────────────────────────────────────────────────────────────
@tool(
    name="ka_send_quotation",
    display_name="Send a formal quotation",
    description=(
        "Use this tool when the customer wants the offer in writing, or is ready to decide on a car you "
        "already priced. Before calling it you MUST have the same inputs you gave ka_price_car: the "
        "`listing_reference` (preferred) or the advert price with VAT, and the options. It records a "
        "numbered quotation, and sends the customer the full offer as a message by itself. After it "
        "succeeds, write ONE short line asking whether to go ahead — do not repeat the figures. "
        "Do NOT call it twice for the same car in one conversation unless the options changed."
    ),
    category="car_import",
    side_effect=True,
    parameters_schema={
        "type": "object",
        "properties": {
            "listing_reference": {"type": "string",
                                  "description": "The advert reference from ka_search_vehicle_listings"},
            "gross_price_eur": {"type": "number",
                                "description": "Only when there is no reference: the advert price with VAT, in EUR"},
            "car_description": {"type": "string",
                                "description": "Only when there is no reference: make, model, year, colour"},
            **_OPTIONS_SCHEMA,
        },
        "required": [],
    },
)
def ka_send_quotation(context, listing_reference: Optional[str] = None,
                      gross_price_eur: Optional[float] = None, car_description: str = '',
                      with_eur1: bool = False, shipping_type: str = '', port: str = 'alexandria',
                      collect_from_showroom: bool = False) -> Dict[str, Any]:
    """Record the quotation and send the offer text to the customer."""
    try:
        from car_import.services import policy, quote_document, sales_flow

        if not policy.ai_first():
            return _refused_by_policy()
        partner = _partner(context)
        if partner is None:
            return {"success": False, "error": "No customer in context", "error_type": "no_partner"}
        resolved = _resolve_price(listing_reference, gross_price_eur)
        if isinstance(resolved, dict):
            return resolved
        listing, gross, source_note = resolved
        conversation = getattr(context, 'conversation', None)
        try:
            quote = sales_flow.make_quote(
                partner, gross, car_label=car_description, listing=listing,
                conversation=conversation, with_eur1=with_eur1, shipping_type=shipping_type,
                port=port, collect_from_showroom=collect_from_showroom, price_source=source_note)
        except ValidationError as exc:
            return {"success": False, "error": "; ".join(exc.messages), "error_type": "refused",
                    "must_escalate": True}

        sent = sales_flow.send_text(partner, quote_document.as_text(quote))
        url = sales_flow.form_url('car_import_menu_quotes', 'car_import.quote', quote.pk)
        sales_flow.note(
            partner,
            f'🧮 المساعد عمل عرض سعر {quote.name}: {quote.car_label or "—"}\n'
            f'الإجمالي {quote.total_eur:,.2f} € — الجدية {float(quote.deposit_pct):g}% '
            f'({quote.deposit_eur:,.2f} €)'
            + (f'\n⚠️ {source_note}' if source_note else '')
            + ('' if sent.get('sent') else f'\n⚠️ العرض متبعتش: {sent.get("error")}'),
            recipients=sales_flow.owners(partner), conversation=conversation,
            subject=f'عرض سعر من المساعد — {quote.name}', url=url)
        return {"success": True, "data": {
            "quotation_reference": quote.name,
            "offer_sent_to_customer": bool(sent.get('sent')),
            "total_selling_price": _fmt(quote.total_eur),
            "deposit_now": _fmt(quote.deposit_eur),
            "valid_until": str(quote.valid_until) if quote.valid_until else None,
            "next_step": ("The offer is already in the chat. Write ONE short line asking if they want to "
                          "go ahead. When they say yes, call ka_issue_proforma_invoice."),
        }}
    except Exception as e:
        logger.exception("ka_send_quotation failed")
        return {"success": False, "error": str(e), "error_type": "unknown"}


# ── the customer said yes ────────────────────────────────────────────────────
@tool(
    name="ka_issue_proforma_invoice",
    display_name="Issue the proforma invoice",
    description=(
        "Use this tool when the customer clearly accepts a quotation and wants to pay the deposit. "
        "Before calling it you MUST have sent them a quotation with ka_send_quotation. It opens the "
        "customer's deal, issues a numbered proforma invoice for the deposit, and sends the invoice file "
        "and the company's approved bank details to the customer by itself. After it succeeds, write a "
        "short message: ask them to send a screenshot of the transfer here, and ask for whatever "
        "`contract_details_missing` lists. Never type bank details yourself."
    ),
    category="car_import",
    side_effect=True,
    parameters_schema={
        "type": "object",
        "properties": {
            "quotation_reference": {"type": "string",
                                    "description": "Optional. Defaults to the customer's latest quotation"},
        },
        "required": [],
    },
)
def ka_issue_proforma_invoice(context, quotation_reference: Optional[str] = None) -> Dict[str, Any]:
    """Accept the quotation, open the deal, issue and send the proforma."""
    try:
        from car_import.models import Quote
        from car_import.services import policy, sales_flow

        if not policy.ai_first():
            return _refused_by_policy()
        partner = _partner(context)
        if partner is None:
            return {"success": False, "error": "No customer in context", "error_type": "no_partner"}
        conversation = getattr(context, 'conversation', None)

        quote = None
        if quotation_reference:
            quote = Quote.all_objects.filter(partner=partner,
                                             name__iexact=quotation_reference.strip()).first()
        quote = quote or sales_flow.latest_open_quote(partner)
        if quote is None:
            return {"success": False, "error": "This customer has no quotation yet — send one first",
                    "error_type": "no_quotation"}
        if quote.valid_until and quote.valid_until < date.today():
            return {"success": False, "error": "The quotation expired — price the car again",
                    "error_type": "quotation_expired",
                    "say_to_customer_ar": "عرض السعر مدته خلصت — هحدّثه لحضرتك حالاً."}

        try:
            deal, opened = sales_flow.ensure_deal(partner, quote)
            sales_flow.accept_quote(quote, deal)
        except ValidationError as exc:
            return {"success": False, "error": "; ".join(exc.messages), "error_type": "refused",
                    "must_escalate": True}

        invoice, created = sales_flow.issue_proforma(quote, deal)
        sent = sales_flow.send_proforma(invoice) if (created or not invoice.sent_at) else {'sent': True}
        contract, missing = sales_flow.save_contract_details(deal)
        labels = [sales_flow.CONTRACT_DETAIL_LABELS.get(m, m) for m in missing
                  if m in ('customer_name', 'customer_national_id')]

        url = sales_flow.form_url('car_import_menu_proformas', 'car_import.proformainvoice', invoice.pk)
        sales_flow.note(
            partner,
            f'🧾 المساعد أصدر فاتورة مبدئية {invoice.name} على {quote.name}'
            + (f' وفتح الصفقة {deal.name}' if opened else f' — الصفقة {deal.name}') + '\n'
            f'المطلوب: {invoice.amount_due:,.2f} € (الجدية {float(invoice.deposit_pct):g}%)'
            + ('' if invoice.bank_details_text else
               '\n⚠️ بيانات الحساب مش متسجّلة (car_import.bank_details_text) — ابعتها للعميل بنفسك.')
            + ('' if sent.get('sent') else f'\n⚠️ الفاتورة متبعتش: {sent.get("error")}'),
            recipients=(sales_flow.owners(partner) + sales_flow.accountants()),
            conversation=conversation, subject=f'فاتورة مبدئية من المساعد — {invoice.name}', url=url)

        return {"success": True, "data": {
            "proforma_reference": invoice.name,
            "deal_reference": deal.name,
            "amount_due_now": _fmt(invoice.amount_due),
            "invoice_sent_to_customer": bool(sent.get('sent')),
            "bank_details_sent": bool(sent.get('sent') and invoice.bank_details_text),
            "contract_details_missing": labels,
            "next_step": ("Ask the customer to send a screenshot of the transfer here"
                          + (", and ask for: " + "، ".join(labels) if labels else "")
                          + (". The bank details come from the accounts team — say so."
                             if not invoice.bank_details_text else ".")),
        }}
    except Exception as e:
        logger.exception("ka_issue_proforma_invoice failed")
        return {"success": False, "error": str(e), "error_type": "unknown"}


# ── the screenshot ───────────────────────────────────────────────────────────
@tool(
    name="ka_record_payment_receipt",
    display_name="Record a transfer screenshot",
    description=(
        "Use this tool the moment the customer sends a screenshot or photo of a bank transfer, deposit "
        "slip or payment confirmation. Before calling it you MUST read the image and extract what it "
        "shows: the amount, the currency, the date, the sender's name, the bank and the transfer "
        "reference — leave out anything you cannot read rather than guessing. It files the newest image "
        "the customer sent as a payment waiting for the accountant, who confirms it with one click. "
        "After it succeeds, thank the customer in one line and say the accounts team is reviewing it. "
        "NEVER say the money arrived or was received — only the accountant can confirm that."
    ),
    category="car_import",
    side_effect=True,
    parameters_schema={
        "type": "object",
        "properties": {
            "amount": {"type": "number", "description": "The amount on the screenshot, digits only"},
            "currency": {"type": "string", "description": "EUR, EGP or USD as shown on the screenshot"},
            "transfer_date": {"type": "string", "description": "The transfer date as YYYY-MM-DD"},
            "sender_name": {"type": "string", "description": "The account holder who sent it, as written"},
            "bank_name": {"type": "string", "description": "The sending bank"},
            "reference": {"type": "string", "description": "The transfer or transaction reference number"},
            "confidence": {"type": "string",
                           "description": "high when every field was clearly readable, medium, or low"},
            "remarks": {"type": "string",
                        "description": "In Arabic: anything unclear, cropped, edited-looking or unusual"},
        },
        "required": [],
    },
)
def ka_record_payment_receipt(context, amount: Optional[float] = None, currency: str = 'EUR',
                              transfer_date: Optional[str] = None, sender_name: str = '',
                              bank_name: str = '', reference: str = '', confidence: str = '',
                              remarks: str = '') -> Dict[str, Any]:
    """File the newest inbound image as a payment waiting for the accountant."""
    try:
        from django.utils.dateparse import parse_date

        from car_import.models import PaymentReceipt
        from car_import.services import policy, sales_flow
        from car_import.tools.document_tools import _mirror, _newest_inbound_attachment

        if not policy.ai_first():
            return _refused_by_policy()
        partner = _partner(context)
        if partner is None:
            return {"success": False, "error": "No customer in context", "error_type": "no_partner"}
        conversation = getattr(context, 'conversation', None)

        source = _newest_inbound_attachment(conversation)
        if source is None:
            return {"success": False, "error": "The customer has not sent an image or file",
                    "error_type": "no_attachment",
                    "say_to_customer_ar": "مش لاقية صورة التحويل — ممكن حضرتك تبعتها تاني؟"}

        # The same screenshot, filed once. A retried turn must not create a
        # second payment for the accountant to accept.
        stored_name = getattr(getattr(source, 'file', None), 'name', '') or ''
        twin = (PaymentReceipt.all_objects.filter(partner=partner, state='pending',
                                                  screenshot__file=stored_name).first()
                if stored_name else None)
        if twin is not None:
            return {"success": True, "data": {"receipt_reference": twin.name, "already_recorded": True,
                                              "next_step": "Tell the customer the accounts team is reviewing it."}}

        screenshot = _mirror(source)
        if screenshot is None:
            return {"success": False, "error": "Could not register the screenshot",
                    "error_type": "attachment_failed", "must_escalate": True}

        receipt = sales_flow.record_receipt(
            partner, conversation, screenshot, amount=amount, currency_code=currency,
            transfer_date=parse_date(str(transfer_date)) if transfer_date else None,
            sender_name=sender_name, bank_name=bank_name, reference=reference,
            confidence=confidence, remarks=remarks)
        sales_flow.announce_receipt(receipt, conversation=conversation)

        return {"success": True, "data": {
            "receipt_reference": receipt.name,
            "state": "waiting for the accountant",
            "say_to_customer_ar": "استلمنا الصورة، شكراً لحضرتك 🙏 الحسابات بتراجعها وهنبلّغ حضرتك "
                                  "بالتأكيد، وبعدها العقد بيتبعتلك على طول.",
            "next_step": "Say that line (or close to it). Do NOT confirm that the money arrived.",
        }}
    except Exception as e:
        logger.exception("ka_record_payment_receipt failed")
        return {"success": False, "error": str(e), "error_type": "unknown"}


# ── the contract's blanks ────────────────────────────────────────────────────
@tool(
    name="ka_save_contract_details",
    display_name="Save the customer's contract details",
    description=(
        "Use this tool when the customer gives the details the contract needs: their full name exactly as "
        "on their national ID, the 14-digit national ID number, their address, their email. Before calling "
        "it you MUST have an open deal for the customer (ka_issue_proforma_invoice opens one). Pass only "
        "what the customer actually wrote — never guess or complete a number. It saves them on the "
        "contract draft and returns what is still missing. If the deposit was already confirmed, it "
        "issues the contract and sends it to the customer by itself."
    ),
    category="car_import",
    side_effect=True,
    parameters_schema={
        "type": "object",
        "properties": {
            "full_name": {"type": "string", "description": "The name exactly as on the national ID"},
            "national_id": {"type": "string", "description": "The 14-digit national ID number"},
            "address": {"type": "string", "description": "The customer's address"},
            "email": {"type": "string", "description": "The customer's email"},
        },
        "required": [],
    },
)
def ka_save_contract_details(context, full_name: str = '', national_id: str = '',
                             address: str = '', email: str = '') -> Dict[str, Any]:
    """Fill the contract draft; issue and send it when the deposit is confirmed."""
    try:
        from car_import.services import policy, sales_flow
        from car_import.tools.deal_tools import _deal_for

        if not policy.ai_first():
            return _refused_by_policy()
        deal = _deal_for(context)
        if deal is None:
            return {"success": False, "error": "No open deal for this customer", "error_type": "not_found"}
        try:
            contract, missing = sales_flow.save_contract_details(
                deal, full_name=full_name or '', national_id=national_id or '',
                address=address or '', email=email or '')
        except ValidationError as exc:
            return {"success": False, "error": "; ".join(exc.messages), "error_type": "invalid",
                    "say_to_customer_ar": "الرقم القومي لازم يكون 14 رقم — ممكن حضرتك تبعته تاني؟"}

        labels = [sales_flow.CONTRACT_DETAIL_LABELS.get(m, m) for m in missing]
        data = {"saved": True, "still_missing": labels, "deal_reference": deal.name}
        if not missing and deal.payment_state in ('deposit_paid', 'fully_paid') \
                and contract.state == 'draft':
            outcome = sales_flow.issue_and_send_contract(deal)
            data["contract_sent"] = bool(outcome.get('sent'))
            data["next_step"] = ("The contract was sent. Ask them to review and sign it."
                                 if outcome.get('sent') else
                                 "The contract could not be sent; a colleague will follow up.")
            sales_flow.note(deal.partner, f'📄 العقد بعد استكمال البيانات: '
                                          f'{sales_flow._contract_summary(outcome)}',
                            recipients=sales_flow.owners(deal.partner),
                            conversation=getattr(context, 'conversation', None),
                            subject='العقد بعد استكمال بيانات العميل')
        else:
            data["next_step"] = ("Ask for: " + "، ".join(labels)) if labels else \
                "Everything the contract needs is on file. It is sent once the deposit is confirmed."
        return {"success": True, "data": data}
    except Exception as e:
        logger.exception("ka_save_contract_details failed")
        return {"success": False, "error": str(e), "error_type": "unknown"}


# ── a discount is still management's ─────────────────────────────────────────
@tool(
    name="ka_request_discount",
    display_name="Ask management for a discount",
    description=(
        "Use this tool when the customer asks for a discount or a better price. A discount on the "
        "company's fees is decided by management only — never offer, promise or hint at one yourself. "
        "Before calling it you MUST have a one-line reason. It files the request in management's approval "
        "queue and notifies them; the conversation stays with you. After it succeeds, tell the customer "
        "you passed the request to management and will come back with their answer, and carry on."
    ),
    category="car_import",
    side_effect=True,
    parameters_schema={
        "type": "object",
        "properties": {
            "reason": {"type": "string",
                       "description": "One line, in Arabic: what the customer asked for and why"},
            "amount_eur": {"type": "number",
                           "description": "Only if the customer named a figure: the discount they asked for, in EUR"},
        },
        "required": ["reason"],
    },
)
def ka_request_discount(context, reason: str, amount_eur: Optional[float] = None) -> Dict[str, Any]:
    """File a fee-discount approval request without handing the conversation over."""
    try:
        from car_import.models.approval import ApprovalPolicy, ApprovalRequest
        from car_import.services import sales_flow
        from car_import.tasks import _users_in_groups
        from car_import.tools.deal_tools import _deal_for

        partner = _partner(context)
        if partner is None:
            return {"success": False, "error": "No customer in context", "error_type": "no_partner"}
        pending = (ApprovalRequest.objects.filter(subject='fee_discount', partner=partner,
                                                  state='pending').order_by('-id').first())
        if pending is None:
            deal = _deal_for(context)
            policy_row = ApprovalPolicy.for_subject('fee_discount')
            pending = ApprovalRequest.objects.create(
                subject='fee_discount', policy=policy_row, deal=deal if getattr(deal, 'pk', None) else None,
                quote=sales_flow.latest_open_quote(partner), partner=partner,
                amount=sales_flow.to_decimal(amount_eur), currency=getattr(policy_row, 'currency', None),
                reason=f'طلب خصم من العميل عن طريق المساعد: {reason}')
            url = sales_flow.form_url('car_import_menu_approval_requests', 'car_import.approvalrequest', pending.pk)
            sales_flow.note(partner, f'🏷️ العميل طلب خصم — محتاج قرار الإدارة.\nالسبب: {reason}'
                            + (f'\nالمبلغ المطلوب: {amount_eur:,.0f} €' if amount_eur else ''),
                            recipients=_users_in_groups(['car_import.management', 'car_import.sales_manager']),
                            conversation=getattr(context, 'conversation', None),
                            subject='طلب خصم — محتاج قرار', url=url)
        return {"success": True, "data": {
            "approval_request_id": pending.pk, "state": "waiting for management",
            "say_to_customer_ar": "طلبت من الإدارة تبص على موضوع الخصم، وهرجع لحضرتك بردّهم.",
            "next_step": "Say that, then carry on helping. Do not promise any discount.",
        }}
    except Exception as e:
        logger.exception("ka_request_discount failed")
        return {"success": False, "error": str(e), "error_type": "unknown"}
