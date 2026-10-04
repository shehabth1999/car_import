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


def _model_class(model):
    """'C' for «C-Class», «سي كلاس», «c class» — a class, not a model. None for
    a model name. A customer who said "سي كلاس" was told nothing matched, then
    shown GLCs because "C" is inside "GLC" (live, 2026-10-01)."""
    import re

    from car_import.services.initiative_values import _latin_classes
    text = _latin_classes(' '.join(str(model or '').replace('-', ' ').split()))
    match = re.fullmatch(r'([A-Za-z]{1,3})\s*(?:class|klasse|كلاس)', text.strip(), re.IGNORECASE)
    return match.group(1).upper() if match else None


def _eur_egp_rate():
    """EGP per EUR as management published it, or None."""
    try:
        from car_import.models import FxReference
        row = (FxReference.in_force(currency_from__code='EUR', currency_to__code='EGP')
               .order_by('-effective_from', '-id').first())
        if row is not None and row.rate:
            return float(row.rate)
        row = (FxReference.in_force(currency_from__code='EGP', currency_to__code='EUR')
               .order_by('-effective_from', '-id').first())
        return (1 / float(row.rate)) if row is not None and row.rate else None
    except Exception:
        logger.exception("car_import: could not read the exchange rate")
        return None


def _import_budget_eur(price_max, currency):
    """(ceiling on the German advert price in EUR or None, what to tell the model).

    The budget is converted HERE, at the company's rate — never by the model,
    which turned 3,000,000 EGP into 30,000 € on 2026-10-01."""
    if not price_max:
        return None, ''
    amount = float(price_max)
    code = (currency or '').strip().upper() or ('EGP' if amount >= 500000 else 'EUR')
    if code == 'EUR':
        return amount, f"Adverts at or under {amount:,.0f} € (the German advert price, not the customer's total)."
    rate = _eur_egp_rate()
    if not rate:
        return None, ("The budget is in EGP and no EUR/EGP rate is published, so the import search was NOT "
                      "narrowed by budget. Do not say these cars fit the budget and never convert it yourself: "
                      "show them as options and ask ONE question for the budget in euros.")
    ceiling = round(amount / rate)
    return ceiling, (f"The budget of {amount:,.0f} EGP is about {ceiling:,.0f} € at the company's rate "
                     f"({rate:g} EGP per EUR); adverts at or under that German advert price are shown. It is "
                     f"indicative — the customer's total cost is the price from ka_quote_car. Do not state the "
                     f"rate or the converted figure to the customer.")


# ── find a car ───────────────────────────────────────────────────────────────
@tool(
    name="ka_search_cars",
    display_name="Find cars (ours, and to import)",
    description=(
        "Use this tool when the customer wants a car or asks what cars you have. It is the ONLY source of "
        "the company's current cars — never list or promise a car you did not get from it. Call it with "
        "whatever the customer already said — one brand, model, budget or year is enough; do not question "
        "them first. With nothing at all it returns the website link to browse instead of cars. If the "
        "customer does not know what they want, send them the website link the tool gives you so they can "
        "browse and come back with the car they like. Set `source` to `our_cars` for the cars the company "
        "has NOW (Egypt showroom with immediate delivery, and cars in Germany), `import` to search cars to "
        "import from Europe, or `both` when the customer did not choose. A budget goes in `price_min` / "
        "`price_max` EXACTLY as the customer said it, with `currency` = the currency THEY used (EGP or EUR) — "
        "NEVER convert a budget yourself; the tool converts it at the company's rate and tells you what it "
        "did. `model` may be a model (C200) or a class (C-Class, سي كلاس). Put the references the customer "
        "already turned down in `exclude_references` so they are not offered again. Returns at most "
        "a few cars, each with a `reference` (use it for photos), year, mileage, price, where it is and its "
        "`link`; `matching` is how many match in all and `see_all_on_website` links to all of them — share "
        "that link instead of listing more cars. Import cars carry the German advert price, NOT the "
        "customer's cost — price those with ka_quote_car. Do NOT offer a car whose `quotable` is false."
    ),
    category="car_import",
    parameters_schema={
        "type": "object",
        "properties": {
            "source": {"type": "string", "enum": ["our_cars", "import", "both"],
                       "description": "our_cars = the company's cars now; import = cars to import; both"},
            "where": {"type": "string", "enum": ["any", "egypt", "germany"],
                      "description": "our_cars only: egypt = ready in the showroom now; default any"},
            "brand": {"type": "string", "description": "The brand the customer named, as they wrote it, "
                                                       "e.g. Mercedes, مرسيدس, BMW"},
            "model": {"type": "string", "description": "The model or class if they named one, e.g. C200, "
                                                       "GLA 180, X1, C-Class, سي كلاس"},
            "price_min": {"type": "number", "description": "Lowest price the customer mentioned"},
            "price_max": {"type": "number", "description": "The customer's budget ceiling, as they said it — "
                                                           "3 million EGP is 3000000 with currency EGP"},
            "currency": {"type": "string", "enum": ["EGP", "EUR"],
                         "description": "The currency the CUSTOMER used for the budget. Never convert"},
            "exclude_references": {"type": "array", "items": {"type": "string"},
                                   "description": "References already shown that the customer turned down"},
            "year_min": {"type": "integer", "description": "Oldest acceptable model year"},
            "year_max": {"type": "integer", "description": "Newest acceptable model year"},
            "max_mileage": {"type": "integer", "description": "Highest acceptable odometer in km (import only)"},
            "limit": {"type": "integer", "description": "How many cars, 1 to 5, default 3", "default": 3},
        },
        "required": ["source"],
    },
)
def ka_search_cars(context, source: str = 'both', brand: Optional[str] = None,
                   model: Optional[str] = None, price_min: Optional[float] = None,
                   price_max: Optional[float] = None, currency: Optional[str] = None,
                   year_min: Optional[int] = None, year_max: Optional[int] = None,
                   max_mileage: Optional[int] = None, limit: int = 3,
                   where: str = 'any', make: Optional[str] = None,
                   exclude_references=None) -> Dict[str, Any]:
    """The company's own cars, and the market to import from — always narrowed first."""
    try:
        from car_import.services import website_catalog

        from .market_tools import ka_search_vehicle_listings

        brand = brand or make                    # `make` is the old name, from older conversations
        source = (source or 'both').strip().lower()
        if source == 'showroom':                 # the old name, from older conversations
            source, where = 'our_cars', 'egypt'
        if source not in ('import', 'our_cars', 'both'):
            source = 'both'
        place = where if where in ('egypt', 'germany') else None

        # Nothing to narrow on: the tool does not read the stock out. The
        # customer says what they want, or browses the website and comes back.
        if not any([brand, model, price_min, price_max, year_min, year_max]):
            return {"success": True, "data": {
                "searched": False,
                "why": "No brand, budget or model year was given, so nothing was searched.",
                "do_now": ("Ask the customer ONE short question: which brand (and model if they know it), "
                           "what budget, or which model year. If they do not know or want to see everything, "
                           "send them `website_link` to browse and ask them to come back with the car they "
                           "like. Do not list cars."),
                "website_link": website_catalog.cars_link(),
                "stock": website_catalog.totals(),
            }}

        data, errors = {}, []
        if source in ('our_cars', 'both'):
            found = website_catalog.our_cars(
                brand=brand, model=model, price_min=price_min, price_max=price_max,
                year_min=year_min, year_max=year_max, location=place, limit=limit, currency=currency)
            found['note'] = ('The company\'s cars now, as on our website. Egypt: final EGP price, immediate '
                             'delivery. Germany: EUR price as listed, shipping to Egypt still to come. Offer '
                             'these few and share `see_all_on_website` for the rest.')
            data['our_cars'] = found
        if source in ('import', 'both'):
            # The marketplace wants its own spelling ("Mercedes-Benz"), not the
            # customer's ("مرسيدس"): the catalogue translates, once.
            from car_import.services import catalogue
            model_class = _model_class(model)
            named_model = None if model_class else model
            brand_row, model_row = catalogue.resolve(brand, named_model) if brand else (None, None)
            if brand_row is None and (brand or named_model):
                brand_row, model_row = catalogue.parse(' '.join(x for x in [brand, named_model] if x))
            ceiling_eur, budget_note = _import_budget_eur(price_max, currency)
            found = ka_search_vehicle_listings(
                context, make=brand_row.name if brand_row else brand,
                model=model_row.name if model_row else named_model, year_min=year_min, year_max=year_max,
                max_mileage=max_mileage, limit=max(1, min(int(limit or 3), 5)),
                price_max_eur=ceiling_eur, model_class=model_class,
                exclude_references=exclude_references)
            if found.get('success'):
                data['import'] = found['data']
                if budget_note:
                    data['import']['budget'] = budget_note
                if ceiling_eur and not found['data'].get('count'):
                    data['import']['do_now'] = (
                        f"Nothing is advertised at or under {ceiling_eur:,.0f} € for this search. Say so "
                        f"plainly — do NOT show a dearer car as if it fits. Offer ONE of: a higher budget, "
                        f"another model, or an older model year.")
                if model_class:
                    data['import']['class_searched'] = f"{model_class}-Class: models named {model_class} + a number"
            else:
                errors.append(f"import: {found.get('error')}")
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
        "Use this tool whenever the customer asks what an imported car will cost, sends a mobile.de link, "
        "wants the offer in writing, or wants an earlier offer again. Give it ONE of: the `listing_reference` "
        "from ka_search_cars, the mobile.de LINK the customer sent (put the link in `listing_reference`), the "
        "advert price with VAT in EUR that the customer typed or that you read off their screenshot "
        "(`gross_price_eur` + `car_description`), or an earlier quotation number Q/… in "
        "`quotation_reference`. NEVER pass a total from an earlier offer as `gross_price_eur`. The car's MODEL "
        "YEAR and whether it is NEW or USED decide the programme, the port and what the price must state "
        "(the tool decides — never ask the customer which programme): a used current-year car or a car of "
        "the three model years before is an initiative car to Alexandria and the answer carries the "
        "INITIATIVE VALUE (USD deposit) — plus the POWERS OF ATTORNEY when the company provides the "
        "initiative; a NEW current-year car goes on the customer's own initiative if they hold one (Alexandria, "
        "like every initiative car), else as a personal import to Port Said whose answer carries its CUSTOMS. "
        "Pass `has_own_initiative` true / "
        "false when the customer said whether they hold an initiative; for a new current-year car the tool "
        "asks you to find out. Pass `model_year` and `condition` when there is no advert reference (read them "
        "off the screenshot). With `send_offer` false it only calculates: total, deposit percent and amount, "
        "balance, what is due in EGP on arrival, and the `programme` block — state them exactly as returned, "
        "the customs or the initiative value and powers of attorney included. With `send_offer` true it records a numbered "
        "quotation and sends the offer as a PDF by itself; it needs the customer's name as on their national "
        "ID (four parts) on file and refuses with `id_name_needed` otherwise — never with the WhatsApp name. "
        "Then write ONE short line asking whether to go ahead, without figures. `quotation_reference` with "
        "`send_offer` true resends that same offer while it is valid, and prices it again when it expired. "
        "Pass `initiative_tier` / `initiative_region` only if the customer said them — otherwise every "
        "variant is stated. To send the offer for the car you just priced, call it with `send_offer` true and "
        "NOTHING else — it reuses that car and its inputs; never ask for the screenshot again and NEVER make "
        "up a link (`listing_reference` takes only a reference from ka_search_cars or a link the customer "
        "sent). A personal import always includes the EUR 1 certificate. Do NOT use it for showroom cars "
        "(WC-…), and do not send the same offer twice."
    ),
    category="car_import",
    side_effect=True,
    parameters_schema={
        "type": "object",
        "properties": {
            "send_offer": {"type": "boolean",
                           "description": "false = calculate only. true = record the quotation and send it as a PDF"},
            "listing_reference": {"type": "string",
                                  "description": "The advert reference from ka_search_cars, OR the mobile.de link "
                                                 "exactly as the customer sent it"},
            "quotation_reference": {"type": "string",
                                    "description": "An earlier quotation number (Q/2026/0007) to resend or renew"},
            "gross_price_eur": {"type": "number",
                                "description": "Only when there is no reference: the ADVERT price with VAT in EUR, as "
                                               "the customer typed it or as shown on their screenshot"},
            "car_description": {"type": "string",
                                "description": "Only when there is no reference: make, model, year, trim"},
            "model_year": {"type": "integer",
                           "description": "Only when there is no reference: the car's model year, e.g. 2024"},
            "condition": {"type": "string", "enum": ["new", "used"],
                          "description": "Only when there is no reference: new = zero km (under ~100 km), "
                                         "used = anything else. Read the mileage off the screenshot"},
            "has_own_initiative": {"type": "boolean",
                                   "description": "true = the customer said they hold their own initiative; false "
                                                  "= they said they don't. Leave it out when not known"},
            "initiative_tier": {"type": "string", "enum": ["full", "medium"],
                                "description": "Only if the customer said it: full (فئة كاملة) or medium"},
            "initiative_region": {"type": "string", "enum": ["europe", "outside"],
                                  "description": "Only if the customer said it: lives in the EU (europe) or not"},
            "with_eur1": {"type": "boolean",
                          "description": "True when the car is EU-built and the customer wants the EUR 1 certificate"},
            "shipping_type": {"type": "string",
                              "description": "Leave empty for standard shipping, or vip_roro, or container"},
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
                 collect_from_showroom: bool = False, quotation_reference: Optional[str] = None,
                 initiative_tier: Optional[str] = None, initiative_region: Optional[str] = None,
                 model_year: Optional[int] = None, condition: str = '',
                 has_own_initiative: Optional[bool] = None) -> Dict[str, Any]:
    """The calculator; and, when asked, the quotation.

    `port` is no longer the model's to choose: the programme sets it
    (owner, 2026-09-30). The argument stays for turns stored before."""
    try:
        import re
        from datetime import date

        from car_import.models import Quote
        from car_import.services import identity, sales_flow

        from .sales_tools import _quote_sent_reply, id_name_needed, ka_price_car, ka_send_quotation

        partner = getattr(context, 'partner', None)

        # An earlier offer, by its number. On 2026-09-29 the assistant put
        # "Q/2026/0005" in listing_reference, failed, and then re-priced the car
        # from the old offer's TOTAL as if it were the advert price.
        qref = str(quotation_reference or '').strip()
        if not qref and re.fullmatch(r'Q/\d{4}/\d+', str(listing_reference or '').strip(), re.IGNORECASE):
            qref, listing_reference = str(listing_reference).strip(), None
        if qref:
            old = (Quote.all_objects.filter(partner=partner, name__iexact=qref).first()
                   if partner is not None else None)
            if old is None:
                theirs = (list(Quote.all_objects.filter(partner=partner).order_by('-id')
                               .values_list('name', flat=True)[:5]) if partner is not None else [])
                return {"success": False, "error_type": "unknown_quotation",
                        "error": f"This customer has no quotation {qref}",
                        "data": {"their_quotations": theirs}}
            new_inputs = bool(gross_price_eur or listing_reference)
            valid = old.valid_until is None or old.valid_until >= date.today()
            if send_offer and not identity.full_id_name(partner):
                return id_name_needed()
            # An offer made before programmes (2026-09-30) carries neither the
            # customs nor the initiative value: it is priced again, not resent.
            if send_offer and valid and old.state in ('sent', 'accepted') and not new_inputs \
                    and old.total_eur and old.programme:
                # The same offer, rebuilt (the ID card may have been read since) and sent again.
                sent = sales_flow.send_quote(old, rerender=True)
                return {"success": True, "data": _quote_sent_reply(old, sent, resent=True)}
            if not new_inputs:
                if old.listing_id:
                    listing_reference = old.listing.ad_id
                else:
                    gross_price_eur = float(old.gross_price_eur or 0) or None
                    car_description = car_description or old.car_label
            with_eur1 = with_eur1 or old.with_eur1
            shipping_type = shipping_type or old.shipping_type
            model_year = model_year or old.model_year
            condition = condition or old.car_condition
            if has_own_initiative is None:
                has_own_initiative = old.own_initiative
            collect_from_showroom = collect_from_showroom or old.collect_from_showroom

        # A link the customer never sent is a link the model made up (live,
        # 2026-10-01: asked for the offer, it passed an invented mobile.de URL,
        # failed, and asked for the screenshot it already had). Drop it.
        from car_import.services import agent_help
        link = str(listing_reference or '').strip()
        if link.lower().startswith(('http', 'www.')) and not agent_help.customer_sent_link(
                getattr(context, 'conversation', None), link):
            logger.warning("ka_quote_car: dropped a link the customer never sent: %s", link[:120])
            listing_reference = None

        # The offer, or a re-price, with nothing to price from: it is the car
        # that was just priced, with the inputs it was priced with.
        if not (listing_reference or gross_price_eur or qref):
            last = agent_help.last_pricing(partner)
            if not last:
                return {"success": False, "error_type": "no_price_source",
                        "error": "There is no car to price: no advert reference, no advert price, and no car "
                                 "priced earlier in this chat.",
                        "do_now": "Use the price and car you already read off the customer's screenshot "
                                  "(gross_price_eur, car_description, model_year, condition). Ask for a "
                                  "screenshot only if the customer never sent one. NEVER invent a link."}
            listing_reference = last.get('listing_reference')
            gross_price_eur = last.get('gross_price_eur')
            car_description = car_description or last.get('car_description', '')
            model_year = model_year or last.get('model_year')
            condition = condition or last.get('condition', '')
            with_eur1 = with_eur1 or bool(last.get('with_eur1'))
            shipping_type = shipping_type or last.get('shipping_type', '')
            collect_from_showroom = collect_from_showroom or bool(last.get('collect_from_showroom'))
            initiative_tier = initiative_tier or last.get('initiative_tier')
            initiative_region = initiative_region or last.get('initiative_region')
            if has_own_initiative is None:
                has_own_initiative = last.get('has_own_initiative')

        if str(listing_reference or '').strip().upper().startswith('WC-'):
            return {"success": False, "error_type": "our_own_car",
                    "error": "This is one of the company's own cars, not an import advert.",
                    "do_now": ("Do not price it here. Its price from ka_search_cars is the price: final in EGP "
                               "for the Egypt showroom, as listed in EUR for Germany. If the customer wants "
                               "to buy it, call ka_escalate_conversation_to_staff with topic=showroom_purchase "
                               "and the reference in the reason.")}

        options = dict(with_eur1=with_eur1, shipping_type=shipping_type,
                       collect_from_showroom=collect_from_showroom, car_description=car_description,
                       condition=condition or '', model_year=model_year, has_own_initiative=has_own_initiative,
                       initiative_tier=initiative_tier or '', initiative_region=initiative_region or '')
        if send_offer:
            return ka_send_quotation(context, listing_reference=listing_reference,
                                     gross_price_eur=gross_price_eur, **options)
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
        "of payment. You CAN read images — read it first. Set `kind` to `national_id` for an Egyptian national "
        "ID card: pass `full_name` exactly as printed in Arabic, the 14-digit `national_id` and the `address` "
        "on the card; it is saved on the customer and every quotation, proforma and contract then carries "
        "that name instead of the chat name. Never write the national ID number back in the chat. Set `kind` "
        "to `payment` for a bank transfer screenshot, deposit slip or InstaPay/Wise confirmation: pass what "
        "it shows — amount, currency, date, sender name, bank, reference — leaving out anything you cannot "
        "read; it is filed for the accountant, and you must NEVER say the money arrived. Set `kind` to "
        "`document` for a passport, residence permit, bank statement, import approval or power of attorney, "
        "and pass its `requirement_code`. Call it once per image. Do NOT call it for photos of cars or "
        "screenshots of adverts — read an advert screenshot yourself and price it with ka_quote_car."
    ),
    category="car_import",
    side_effect=True,
    parameters_schema={
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["national_id", "payment", "document"],
                     "description": "national_id = the customer's ID card. payment = proof of a transfer. "
                                    "document = any other required paper"},
            "full_name": {"type": "string",
                          "description": "national_id only: the full name exactly as printed on the card"},
            "national_id": {"type": "string",
                            "description": "national_id only: the 14-digit number as printed on the card"},
            "address": {"type": "string", "description": "national_id only: the address on the card"},
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
                           amount: Optional[float] = None, currency: str = '',
                           transfer_date: Optional[str] = None, sender_name: str = '',
                           bank_name: str = '', reference: str = '', confidence: str = '',
                           remarks: str = '', full_name: str = '', national_id: str = '',
                           address: str = '') -> Dict[str, Any]:
    """A transfer for the accountant, the ID card read onto the customer, or a paper for the file."""
    try:
        from .document_tools import ka_file_customer_document
        from .sales_tools import ka_record_payment_receipt

        kind = (kind or '').strip().lower()
        if kind == 'national_id' or full_name or national_id:
            return _read_id_card(context, full_name, national_id, address, note)
        if kind == 'payment':
            return ka_record_payment_receipt(
                context, amount=amount, currency=currency or '', transfer_date=transfer_date,
                sender_name=sender_name, bank_name=bank_name, reference=reference,
                confidence=confidence, remarks=remarks)
        if not (requirement_code or '').strip():
            return {"success": False, "error": "A document needs its requirement_code",
                    "error_type": "missing_requirement_code"}
        return ka_file_customer_document(context, requirement_code=requirement_code, note=note)
    except Exception as e:
        return _failed("ka_customer_sent_image", e)


def _read_id_card(context, full_name, national_id, address, note):
    """Save what the assistant read off the ID card, and file the photo when
    there is a deal to file it on.

    Until 2026-09-29 an ID photo was only filed: nothing read the name or the
    number off it, the quote kept the chat name, and the assistant told the
    owner it could not read the card it had just read the name from.
    """
    from car_import.services import identity

    from .document_tools import ka_file_customer_document

    partner = getattr(context, 'partner', None)
    if partner is None:
        return {"success": False, "error": "No customer in context", "error_type": "no_partner"}
    if not (full_name or national_id or address):
        return {"success": False, "error_type": "nothing_read",
                "error": "Read the card first and pass full_name, national_id and address as printed."}

    # The card prints the first name on one line and the father's, the
    # grandfather's and the family's on the next. A name in fewer than four
    # parts is a line that was not read — it never goes on a document.
    short_name = bool(full_name) and identity.name_parts(full_name) < identity.MIN_NAME_PARTS
    saved, problems = identity.save_id_card(partner, full_name='' if short_name else full_name,
                                            national_id=national_id, address=address)
    filed = ka_file_customer_document(context, requirement_code='national_id_front_back', note=note)
    digits = identity.normalise_national_id(national_id)
    data = {
        "saved": saved,
        "name_on_documents": identity.full_id_name(partner) or None,
        "national_id_on_file": identity.masked(partner.national_id or '') if partner.national_id else None,
        "photo_filed_on_deal": bool(filed.get('success')),
    }
    if short_name:
        data["name_problem"] = (f"The name passed has {identity.name_parts(full_name)} parts and was NOT saved. "
                                "The card shows the first name on one line and the rest on the next: read both "
                                "lines and call again with the whole name (four parts or more). If the photo "
                                "is unreadable, ask for the full name as on the card.")
    if problems:
        data["national_id_problem"] = problems
        data["next_step"] = ("The number could not be taken from the card as read "
                             f"({'; '.join(problems)}). Ask the customer to TYPE the 14 digits once, then call "
                             "this tool again with kind=national_id and national_id.")
    else:
        data["next_step"] = ("Saved. Thank them in one line. Never write the national ID number in the chat. "
                             "If they asked for the quotation or proforma with their ID data, resend it now: "
                             "ka_quote_car with send_offer=true and quotation_reference = their latest offer "
                             "(the file is rebuilt with the ID's name, number and address).")
    if digits and not problems and len(digits) == 14:
        data["checked"] = "14 digits, valid birth date"
    return {"success": True, "data": data}


# ── the initiative's deposit ─────────────────────────────────────────────────
@tool(
    name="ka_initiative_deposit",
    display_name="The initiative's deposit for a car",
    description=(
        "Use this tool whenever the customer asks for «قيمة المبادرة» or «قيمة الوديعة» (they are the same "
        "thing: the USD deposit an initiative car needs) for a model. Call it at once with the model as the "
        "customer wrote it (e.g. «E200», «سي 180», «GLC 200») and the model year if they gave one — do NOT "
        "ask about colour, options, sunroof, mileage or anything else first: only the model, the year, the "
        "tier (full / medium) and the region (inside / outside Europe) change the figure. Pass `tier` and "
        "`region` only when the customer already said them; otherwise the tool returns every variant and you "
        "state them all in one short message («فئة كاملة: …، فئة متوسطة: …»). State the figures exactly as "
        "returned, in US dollars. «فئة كاملة» is the full tier — never list the options to the customer. "
        "Europe = residence in an EU country; UK and Turkey count as outside Europe for this table."
    ),
    category="car_import",
    parameters_schema={
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "The model as the customer wrote it, e.g. E200, C 180"},
            "year": {"type": "integer", "description": "The model year, when the customer gave one"},
            "tier": {"type": "string", "enum": ["full", "medium"],
                     "description": "Only if known: full (فئة كاملة) or medium (فئة متوسطة)"},
            "region": {"type": "string", "enum": ["europe", "outside"],
                       "description": "Only if known: europe = lives in an EU country, outside = anywhere else"},
        },
        "required": ["model"],
    },
)
def ka_initiative_deposit(context, model: str, year: Optional[int] = None, tier: Optional[str] = None,
                          region: Optional[str] = None) -> Dict[str, Any]:
    """Straight from the owner's deposit workbook (DepositTier)."""
    try:
        from car_import.services import initiative_values

        found = initiative_values.lookup(model, year=year, tier=tier, region=region)
        if not found.get('found'):
            from car_import.services import agent_help
            found["colleague_tagged"] = agent_help.ask_staff(
                getattr(context, 'partner', None), getattr(context, 'conversation', None), 'initiative',
                found.get('car') or model, year or initiative_values.year_in(model))
            found["do_now"] = ("Say plainly that this model/year is not in the initiative table, that a colleague "
                               "is confirming the value now, and offer the closest year listed (labelled with its "
                               "year) — do not guess a figure, and do not escalate.")
            return {"success": True, "data": found}
        found["rules"] = ("State these USD figures exactly. It is paid in dollars and returned after 5 years; "
                          "it is not part of the car's EUR price. One short message, no questions about "
                          "options or colour.")
        return {"success": True, "data": found}
    except Exception as e:
        return _failed("ka_initiative_deposit", e)


# ── the customs of a new car ─────────────────────────────────────────────────
@tool(
    name="ka_customs_value",
    display_name="Customs for a new car (personal import)",
    description=(
        "Use this tool whenever the customer asks what the customs are — «الجمارك», «الجمرك», «الجمارك والضرايب» "
        "— for a model. A NEW current-year car imported personally pays customs instead of the initiative "
        "deposit. Call it at once with the model as the customer wrote it (e.g. «GLB 200», «سي 200») and the "
        "model year if they gave one. Do NOT answer customs from the knowledge search, do not explain engine "
        "sizes or countries of origin, and never guess. It returns the figure from the company's customs table "
        "in EUR — state it exactly and say it is paid on top of the car's price and the port fees. When the "
        "table has no figure, a colleague is tagged in the chat by the tool: tell the customer a colleague is "
        "confirming it now, and carry on."
    ),
    category="car_import",
    parameters_schema={
        "type": "object",
        "properties": {
            "model": {"type": "string", "description": "The model as the customer wrote it, e.g. GLB 200, C200"},
            "year": {"type": "integer", "description": "The model year, when the customer gave one"},
        },
        "required": ["model"],
    },
)
def ka_customs_value(context, model: str, year: Optional[int] = None) -> Dict[str, Any]:
    """Straight from the customs table (CustomsValuation) — the owner's list.

    Until 2026-10-01 the figure existed only inside a priced quotation, so
    "what are the customs for the GLB 200?" got a lecture about engine sizes
    and no number, three times, to the client's GM."""
    try:
        from car_import.services import agent_help, initiative_values
        from car_import.services import programme as rules

        car_model = initiative_values.find_model(model)
        wanted = int(year) if str(year or '').strip().isdigit() else (
            initiative_values.year_in(model) or rules.current_year())
        row = rules.customs_row(car_model, wanted) if car_model is not None else None
        if row is None:
            tagged = agent_help.ask_staff(getattr(context, 'partner', None),
                                          getattr(context, 'conversation', None), 'customs',
                                          car_model or model, wanted)
            return {"success": True, "data": {
                "found": False, "car": str(car_model) if car_model is not None else model, "year": wanted,
                "colleague_tagged": tagged,
                "say_to_customer_ar": "قيمة الجمارك للعربية دي زميلي بيأكدها لحضرتك دلوقتي وهرجعلك بيها.",
                "do_now": ("Say that line and carry on. Do not guess a figure, an engine size or a country of "
                           "origin, and do not advise buying the car in Egypt."),
            }}
        return {"success": True, "data": {
            "found": True, "car": str(car_model), "model_year_in_table": row.model_year,
            "customs_eur": rules.eur(row.value_eur),
            "rules": ("State this figure exactly, in euros. It is the customs of a NEW car imported personally: "
                      "paid on top of the car's price and the port fees (Port Said). A used car goes by the "
                      "initiative instead — a deposit, not customs."),
        }}
    except Exception as e:
        return _failed("ka_customs_value", e)


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


# ── the contract document ────────────────────────────────────────────────────
@tool(
    name="ka_contract_request",
    display_name="The contract: a blank copy, or a change",
    description=(
        "Use this tool when the customer asks about THE CONTRACT DOCUMENT itself. Set `request` to `blank_copy` "
        "when they want to see or read the contract, its terms or its clauses — before paying or before "
        "deciding: it sends the company's contract for their programme with every name, figure and date left "
        "empty and no stamp or signature. NEVER tell a customer to pay first to see the contract, and send it "
        "only when they ask. Set `request` to `change` when they already have a contract and want something "
        "in it changed: it sends them the invitation to review it with us at the company's office (address "
        "and map) — do NOT hand them over for that. Pass `programme` (initiative or personal, from the car "
        "being discussed) when they have no deal yet. After it succeeds write ONE short line. The customer's "
        "name and national ID for the contract go through ka_save_contract_details, not this tool."
    ),
    category="car_import",
    side_effect=True,
    parameters_schema={
        "type": "object",
        "properties": {
            "request": {"type": "string", "enum": ["blank_copy", "change"],
                        "description": "blank_copy = they want to read the contract. change = they want "
                                       "something in their existing contract changed"},
            "programme": {"type": "string", "enum": ["initiative", "personal"],
                          "description": "blank_copy only: the programme of the car being discussed "
                                         "(a new current-model-year car = personal, otherwise initiative)"},
        },
        "required": ["request"],
    },
)
def ka_contract_request(context, request: str, programme: Optional[str] = None) -> Dict[str, Any]:
    """The owner's two contract rules of 2026-09-30 (`services/contract_preview.py`)."""
    try:
        from car_import.services import contract_preview, sales_flow

        partner = getattr(context, 'partner', None)
        if partner is None:
            return {"success": False, "error": "No customer in context", "error_type": "no_partner"}
        conversation = getattr(context, 'conversation', None)

        if (request or '').strip().lower() == 'change':
            text = contract_preview.office_visit_text()
            sent = sales_flow.send_text(partner, text)
            sales_flow.note(partner, '📝 العميل طلب تعديل في العقد — اتبعتله دعوة يراجعه معانا في مقر الشركة.',
                            recipients=sales_flow.owners(partner), conversation=conversation,
                            subject='طلب تعديل في العقد')
            if not sent.get('sent'):
                return {"success": True, "data": {
                    "invitation_sent": False, "say_to_customer_exactly": text,
                    "next_step": "Send the text above exactly as written — the address and the map link unchanged."}}
            return {"success": True, "data": {
                "invitation_sent": True,
                "next_step": "The office address is already in the chat. Write ONE short line, e.g. that we "
                             "will be glad to see them. Do not repeat the address."}}

        chosen = contract_preview.programme_of(partner, programme)
        if chosen is None:
            return {"success": False, "error_type": "programme_needed",
                    "error": "The contract differs by programme and it is not known for this customer.",
                    "do_now": "Call again with `programme`: personal for a new car of the current model year, "
                              "initiative for anything else. Ask the customer only if the car is not known."}
        document, why = contract_preview.blank_copy(chosen)
        if document is None:
            logger.warning("ka_contract_request: %s", why)
            return {"success": False, "error_type": "no_template", "error": why, "must_escalate": True}
        label = contract_preview.PROGRAMME_AR.get(chosen, chosen)
        sent = sales_flow.send_document(
            partner, document,
            f'نسخة من عقد {label} للاطلاع على البنود — من غير بيانات ولا أختام ولا توقيعات')
        sales_flow.note(partner, f'📄 اتبعت للعميل نسخة فاضية من عقد {label} للاطلاع (طلبها قبل الدفع).'
                        + ('' if sent.get('sent') else f'\n⚠️ متبعتتش: {sent.get("error")}'),
                        recipients=sales_flow.owners(partner), conversation=conversation,
                        subject='نسخة العقد للاطلاع')
        if not sent.get('sent'):
            return {"success": False, "error_type": "send_failed", "error": sent.get('error') or 'send failed',
                    "say_to_customer_ar": "مش قادرة أبعت الملف دلوقتي — زميلي هيبعتهولك حالاً."}
        return {"success": True, "data": {
            "blank_contract_sent": True, "programme": label,
            "next_step": "The contract file is in the chat. Write ONE short line: it is for reading the terms, "
                         "and the final copy carries their data once they contract. Do not ask for payment."}}
    except Exception as e:
        return _failed("ka_contract_request", e)
