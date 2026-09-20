# -*- coding: utf-8 -*-
"""The tools the assistant actually holds — five that stand for thirteen.

By 2026-09-20 the agent node carried 21 tools and a retriever. Every one was
reasonable; together they were a menu a small model reads badly. The live
symptoms were the predictable ones: the right tool not called, a neighbour
called instead, a question answered from history because choosing was harder
than talking.

Two moves brought it to twelve and the retriever:

* **What is knowledge went to the knowledge base.** Published fees, instalment
  terms and the eligibility rules are text, not actions. They are generated
  from the settings tables into the approved-answers collection
  (`services/knowledge_figures.py`) — still one source of truth, and a
  retriever's result is stored like any tool's, so the outbound gate can still
  trace every figure.
* **Tools that answer one question became one tool.** "Find me a car" is one
  intent whether the car is in Germany or in the showroom; "the customer sent
  a picture" is one event whether it is a passport or a bank transfer. Each
  tool here is a thin front for the functions that already exist and are
  already tested — nothing is reimplemented, and the originals stay
  registered, so binding them again is a one-line change in `TOOL_NAMES`.

A flag or a `kind` decides the branch. That is a choice a model makes well:
it is a property of the situation, not a pick between look-alike names.
"""
import logging
from typing import Any, Dict, Optional

from modules.aistudio.tools import tool

logger = logging.getLogger(__name__)


def _failed(name, exc):
    logger.exception("%s failed", name)
    return {"success": False, "error": str(exc), "error_type": "unknown"}


# ── find a car ───────────────────────────────────────────────────────────────
@tool(
    name="ka_search_cars",
    display_name="Find cars (import and showroom)",
    description=(
        "Use this tool whenever the customer wants a car, asks what is available, or asks whether a car "
        "is in the showroom. Before calling it you SHOULD have a make, or a make and model. Set `source` to "
        "`import` for cars to import from Europe, `showroom` for cars ready now in the Egypt showroom, or "
        "`both` when the customer did not choose or said 'check both'. Returns each car with a `reference`, "
        "year, mileage, colour and gearbox; import cars carry the German advert price (NOT the customer's "
        "cost — price it with ka_quote_car), showroom cars carry their final price in EGP. Do NOT offer a "
        "car whose `quotable` is false. If nothing matches, say so and offer the other source."
    ),
    category="car_import",
    parameters_schema={
        "type": "object",
        "properties": {
            "source": {"type": "string", "enum": ["import", "showroom", "both"],
                       "description": "Where to look. Use both when the customer did not choose"},
            "make": {"type": "string", "description": "e.g. Mercedes-Benz, BMW, Audi"},
            "model": {"type": "string", "description": "e.g. C200, GLA 180, X1"},
            "year_min": {"type": "integer", "description": "Oldest acceptable model year (import only)"},
            "max_mileage": {"type": "integer", "description": "Highest acceptable odometer in km (import only)"},
            "limit": {"type": "integer", "description": "How many per source, default 5", "default": 5},
        },
        "required": ["source"],
    },
)
def ka_search_cars(context, source: str = 'both', make: Optional[str] = None,
                   model: Optional[str] = None, year_min: Optional[int] = None,
                   max_mileage: Optional[int] = None, limit: int = 5) -> Dict[str, Any]:
    """One search, two stocks."""
    try:
        from .market_tools import ka_search_vehicle_listings
        from .sales_tools import ka_search_showroom_cars

        source = (source or 'both').strip().lower()
        if source not in ('import', 'showroom', 'both'):
            source = 'both'
        data, errors = {}, []
        if source in ('import', 'both'):
            found = ka_search_vehicle_listings(context, make=make, model=model, year_min=year_min,
                                               max_mileage=max_mileage, limit=limit)
            if found.get('success'):
                data['import'] = found['data']
            else:
                errors.append(f"import: {found.get('error')}")
        if source in ('showroom', 'both'):
            query = ' '.join(x for x in [make, model] if x)
            found = ka_search_showroom_cars(context, query=query, limit=limit)
            if found.get('success'):
                data['showroom'] = found['data']
            else:
                errors.append(f"showroom: {found.get('error')}")
        if not data:
            return {"success": False, "error": '; '.join(errors) or 'search failed',
                    "error_type": "search_failed"}
        if errors:
            data['partial'] = errors
        return {"success": True, "data": data}
    except Exception as e:
        return _failed("ka_search_cars", e)


# ── price it, and put it in writing ──────────────────────────────────────────
@tool(
    name="ka_quote_car",
    display_name="Price a car / send the quotation",
    description=(
        "Use this tool whenever the customer asks what an imported car will cost, and again when they want "
        "the offer in writing. Before calling it you MUST have EITHER the car's `listing_reference` from "
        "ka_search_cars (preferred — the price is read from the advert) OR the advert price with VAT in EUR "
        "that the customer gave you. With `send_offer` false it only calculates and returns the full price: "
        "total, deposit percent and amount, balance, and what is due in EGP on arrival — state them exactly "
        "as returned. With `send_offer` true it records a numbered quotation and sends the customer the full "
        "offer by itself; then write ONE short line asking whether to go ahead, without repeating figures. "
        "Do NOT use it for showroom cars, and do not send the same offer twice."
    ),
    category="car_import",
    side_effect=True,
    parameters_schema={
        "type": "object",
        "properties": {
            "send_offer": {"type": "boolean",
                           "description": "false = calculate only. true = record the quotation and send it"},
            "listing_reference": {"type": "string", "description": "The advert reference from ka_search_cars"},
            "gross_price_eur": {"type": "number",
                                "description": "Only when there is no reference: the advert price with VAT, in EUR"},
            "car_description": {"type": "string",
                                "description": "Only when there is no reference: make, model, year, colour"},
            "with_eur1": {"type": "boolean",
                          "description": "True when the car is EU-built and the customer wants the EUR 1 certificate"},
            "shipping_type": {"type": "string",
                              "description": "Leave empty for standard shipping, or vip_roro, or container"},
            "port": {"type": "string", "description": "alexandria (default) or port_said"},
            "collect_from_showroom": {"type": "boolean",
                                      "description": "True when the customer collects the car from the Cairo showroom instead of "
                                                     "door delivery. It LOWERS what is due in EGP on arrival"},
        },
        "required": ["send_offer"],
    },
)
def ka_quote_car(context, send_offer: bool = False, listing_reference: Optional[str] = None,
                 gross_price_eur: Optional[float] = None, car_description: str = '',
                 with_eur1: bool = False, shipping_type: str = '', port: str = 'alexandria',
                 collect_from_showroom: bool = False) -> Dict[str, Any]:
    """The calculator; and, when asked, the quotation."""
    try:
        from .sales_tools import ka_price_car, ka_send_quotation

        options = dict(with_eur1=with_eur1, shipping_type=shipping_type, port=port,
                       collect_from_showroom=collect_from_showroom)
        if send_offer:
            return ka_send_quotation(context, listing_reference=listing_reference,
                                     gross_price_eur=gross_price_eur,
                                     car_description=car_description, **options)
        return ka_price_car(context, listing_reference=listing_reference,
                            gross_price_eur=gross_price_eur, **options)
    except Exception as e:
        return _failed("ka_quote_car", e)


# ── the customer sent a picture ──────────────────────────────────────────────
@tool(
    name="ka_customer_sent_image",
    display_name="File an image the customer sent",
    description=(
        "Use this tool the moment the customer sends a photo, screenshot or file that is paperwork or proof "
        "of payment. Set `kind` to `payment` for a bank transfer screenshot, deposit slip or InstaPay/Wise "
        "confirmation: read the image first and pass what it shows — amount, currency, date, sender name, "
        "bank, reference — leaving out anything you cannot read; it is filed for the accountant, and you "
        "must NEVER say the money arrived. Set `kind` to `document` for an ID, passport, residence permit, "
        "bank statement, import approval or power of attorney, and pass its `requirement_code`. Call it once "
        "per image. Do NOT call it for photos of cars or screenshots of adverts."
    ),
    category="car_import",
    side_effect=True,
    parameters_schema={
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["payment", "document"],
                     "description": "payment = proof of a transfer. document = a required paper"},
            "requirement_code": {"type": "string",
                                 "description": "document only: national_id_front_back, passport, residence_permit, "
                                                "bank_statement_6m, deposit_receipts, import_approval, customs_broker_poa"},
            "note": {"type": "string", "description": "document only: anything the customer said about it"},
            "amount": {"type": "number", "description": "payment only: the amount on the screenshot"},
            "currency": {"type": "string", "description": "payment only: EUR, EGP or USD as shown"},
            "transfer_date": {"type": "string", "description": "payment only: YYYY-MM-DD"},
            "sender_name": {"type": "string", "description": "payment only: the account holder who sent it"},
            "bank_name": {"type": "string", "description": "payment only: the sending bank or app"},
            "reference": {"type": "string", "description": "payment only: the transfer reference number"},
            "confidence": {"type": "string", "description": "payment only: high, medium or low readability"},
            "remarks": {"type": "string",
                        "description": "payment only, in Arabic: anything unclear, cropped or unusual"},
        },
        "required": ["kind"],
    },
)
def ka_customer_sent_image(context, kind: str, requirement_code: str = '', note: str = '',
                           amount: Optional[float] = None, currency: str = 'EUR',
                           transfer_date: Optional[str] = None, sender_name: str = '',
                           bank_name: str = '', reference: str = '', confidence: str = '',
                           remarks: str = '') -> Dict[str, Any]:
    """A transfer for the accountant, or a paper for the file."""
    try:
        from .document_tools import ka_file_customer_document
        from .sales_tools import ka_record_payment_receipt

        if (kind or '').strip().lower() == 'payment':
            return ka_record_payment_receipt(
                context, amount=amount, currency=currency or 'EUR', transfer_date=transfer_date,
                sender_name=sender_name, bank_name=bank_name, reference=reference,
                confidence=confidence, remarks=remarks)
        if not (requirement_code or '').strip():
            return {"success": False, "error": "A document needs its requirement_code",
                    "error_type": "missing_requirement_code"}
        return ka_file_customer_document(context, requirement_code=requirement_code, note=note)
    except Exception as e:
        return _failed("ka_customer_sent_image", e)


# ── an existing deal ─────────────────────────────────────────────────────────
@tool(
    name="ka_deal_status",
    display_name="The customer's deal: status and papers",
    description=(
        "Use this tool when a customer who already has a deal asks where their car is, about shipping, the "
        "arrival date, what they have paid, or which documents are still needed. It returns the deal's "
        "stage, vessel, ETA, port, payment state and a ready-to-say status text, plus the papers still "
        "missing. Set `send_update` to true only when the customer asks to be SENT the status as a message: "
        "it then sends it by itself, and you write one short line after. Never promise a delivery date "
        "beyond the ETA it returns."
    ),
    category="car_import",
    side_effect=True,
    parameters_schema={
        "type": "object",
        "properties": {
            "send_update": {"type": "boolean",
                            "description": "true only when the customer asks for the status to be sent to them"},
            "deal_reference": {"type": "string",
                               "description": "Optional. Defaults to the customer's newest open deal"},
        },
        "required": [],
    },
)
def ka_deal_status(context, send_update: bool = False,
                   deal_reference: Optional[str] = None) -> Dict[str, Any]:
    """Status, papers, and the written update on request."""
    try:
        from .deal_tools import (ka_get_deal_status, ka_get_document_checklist,
                                 ka_send_deal_status_update)

        status = ka_get_deal_status(context, deal_reference=deal_reference)
        if not status.get('success'):
            return status
        data = dict(status['data'])
        papers = ka_get_document_checklist(context)
        if papers.get('success'):
            data['documents'] = {k: v for k, v in papers['data'].items() if k != 'deal_reference'}
        if send_update:
            sent = ka_send_deal_status_update(context, deal_reference=deal_reference)
            data['update_sent_to_customer'] = bool(sent.get('success'))
            if not sent.get('success'):
                data['update_error'] = sent.get('error')
            data['next_step'] = "The status message is already in the chat. Write one short line only."
        return {"success": True, "data": data}
    except Exception as e:
        return _failed("ka_deal_status", e)


# ── the initiative market ────────────────────────────────────────────────────
@tool(
    name="ka_initiative_market",
    display_name="Initiatives: buy one, or offer one",
    description=(
        "Use this tool for the expatriate-initiative market. Set `action` to `search` when a customer wants "
        "to BUY someone else's initiative right or asks whether any are available — it returns the current "
        "offers with their asking price and terms. Set `action` to `register` when the customer holds an "
        "initiative and wants to SELL it — pass their asking price; a colleague verifies it before it is "
        "listed, so say so. Do NOT promise that a transfer will be approved."
    ),
    category="car_import",
    side_effect=True,
    parameters_schema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["search", "register"],
                       "description": "search = the customer wants to buy one. register = they want to sell theirs"},
            "initiative_type": {"type": "string", "description": "gulf or european"},
            "max_price_egp": {"type": "number", "description": "search only: the customer's ceiling in EGP"},
            "asking_price_egp": {"type": "number", "description": "register only: what the holder wants, in EGP"},
            "terms": {"type": "string", "description": "register only: anything the holder said about terms"},
            "limit": {"type": "integer", "description": "search only: how many to return, default 5", "default": 5},
        },
        "required": ["action"],
    },
)
def ka_initiative_market(context, action: str, initiative_type: Optional[str] = None,
                         max_price_egp: Optional[float] = None,
                         asking_price_egp: Optional[float] = None, terms: str = '',
                         limit: int = 5) -> Dict[str, Any]:
    """Both sides of the same market."""
    try:
        from .market_tools import ka_register_initiative_for_sale, ka_search_initiative_listings

        if (action or '').strip().lower() == 'register':
            if not asking_price_egp:
                return {"success": False, "error": "Ask the holder for their asking price in EGP first",
                        "error_type": "missing_price"}
            return ka_register_initiative_for_sale(context, asking_price_egp=asking_price_egp,
                                                   initiative_type=initiative_type, terms=terms)
        return ka_search_initiative_listings(context, max_price_egp=max_price_egp,
                                             initiative_type=initiative_type, limit=limit)
    except Exception as e:
        return _failed("ka_initiative_market", e)
