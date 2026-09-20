# -*- coding: utf-8 -*-
"""Tools for the two markets: German adverts, and initiatives for sale.

The search tool deliberately does NOT return the German purchase price. That
figure is cost data — the brief makes hiding it from agents a contractual
obligation, and a customer must never see it at all, because the price they pay
is the whole stack on top of it. The assistant gets the car, not the cost.
"""
import logging
from typing import Any, Dict, Optional

from modules.aistudio.tools import tool

logger = logging.getLogger(__name__)


@tool(
    name="ka_search_vehicle_listings",
    display_name="Search cars for sale",
    description=(
        "Use this tool to find cars to import matching what the customer asked for — make, model, "
        "year, mileage. Before calling it you MUST have at least a make, or a make and model. "
        "Returns the cars found with their year, mileage, colour, gearbox, the advert price in Germany "
        "and a `reference`. The advert price is NOT what the customer pays: to tell them the cost, "
        "call ka_price_car with the reference. Follow the `price_policy` in the result. Do NOT offer "
        "a car whose `quotable` is false."
    ),
    category="car_import",
    parameters_schema={
        "type": "object",
        "properties": {
            "make": {"type": "string", "description": "e.g. Mercedes-Benz, BMW, Audi"},
            "model": {"type": "string", "description": "e.g. C200, X1, A3"},
            "year_min": {"type": "integer", "description": "Oldest acceptable model year"},
            "max_mileage": {"type": "integer", "description": "Highest acceptable odometer in km"},
            "limit": {"type": "integer", "description": "How many to return, default 5", "default": 5},
        },
        "required": [],
    },
)
def ka_search_vehicle_listings(context, make: Optional[str] = None, model: Optional[str] = None,
                               year_min: Optional[int] = None, max_mileage: Optional[int] = None,
                               limit: int = 5) -> Dict[str, Any]:
    """Cars on the marketplace, without a price."""
    try:
        from car_import.services import mobile_de

        listings, meta = mobile_de.search(
            make=make, model=model, year_min=year_min, mileage_max=max_mileage,
            vatable=True, page_size=max(1, min(int(limit or 5), 20)))

        from car_import.services import policy
        ai_first = policy.ai_first()
        # Stored, so the reference the model hands back to the price tool
        # resolves to a row with a price on it — not to a number it remembered.
        try:
            mobile_de.import_listings(listings)
        except Exception:
            logger.exception("car_import: could not store the searched adverts")

        def _quotable(row):
            return not row.get('is_simulated', False) or policy.may_quote_simulated_cars()

        cars = [{
            'reference': row.get('ad_id'),
            'advert_price_with_vat': (f"{row.get('price_gross_eur'):,.0f} €"
                                      if ai_first and row.get('price_gross_eur') else None),
            'photos_available': len([i for i in (row.get('images') or []) if i]),
            'quotable': _quotable(row),
            'make': row.get('make'),
            'model': row.get('model'),
            'version': row.get('version'),
            'model_year': row.get('model_year'),
            'mileage_km': row.get('mileage_km'),
            'colour': row.get('colour_exterior'),
            'gearbox': row.get('gearbox'),
            'fuel': row.get('fuel'),
            'accident_free': row.get('accident_free'),
            'simulated': row.get('is_simulated', False),
        } for row in listings]

        return {
            "success": True,
            "data": {
                "count": len(cars),
                "cars": cars,
                "simulated": meta['simulated'],
                "price_policy": ("The advert price is the German price with VAT, not the customer's cost. "
                                 "Use ka_price_car with the reference for what they will pay."
                                 if ai_first else
                                 "Never state or estimate a price from this tool. A colleague prices the car."),
            },
        }
    except Exception as e:
        logger.exception("ka_search_vehicle_listings failed")
        return {"success": False, "error": str(e), "error_type": "unknown"}


@tool(
    name="ka_search_initiative_listings",
    display_name="Initiatives for sale",
    description=(
        "Use this tool when a customer wants to BUY someone else's expatriate-initiative right, "
        "or asks whether any are available. Registration for new participants closed in 2024, so "
        "buying an existing one is the only route left. Returns the offers currently available with "
        "their asking price and terms. Do NOT promise a transfer will be approved."
    ),
    category="car_import",
    parameters_schema={
        "type": "object",
        "properties": {
            "max_price_egp": {"type": "number", "description": "The customer's ceiling in EGP"},
            "initiative_type": {"type": "string", "description": "gulf or european"},
            "limit": {"type": "integer", "description": "How many to return, default 5", "default": 5},
        },
        "required": [],
    },
)
def ka_search_initiative_listings(context, max_price_egp: Optional[float] = None,
                                  initiative_type: Optional[str] = None,
                                  limit: int = 5) -> Dict[str, Any]:
    """Deposit rights currently on offer."""
    try:
        from car_import.models import InitiativeListing

        rows = (InitiativeListing.objects.filter(state='available')
                .select_related('initiative', 'initiative__holder'))
        if max_price_egp is not None:
            rows = rows.filter(asking_price_egp__lte=max_price_egp)
        if initiative_type:
            rows = rows.filter(initiative__initiative_type=initiative_type)

        offers = [{
            'reference': row.pk,
            'initiative_type': row.initiative.get_initiative_type_display(),
            'tier': row.initiative.get_tier_display() if row.initiative.tier else None,
            'deposit_usd': float(row.initiative.deposit_usd) if row.initiative.deposit_usd else None,
            'asking_price_egp': float(row.asking_price_egp) if row.asking_price_egp else None,
            'terms': row.participation_terms,
        } for row in rows.order_by('asking_price_egp')[:max(1, min(int(limit or 5), 20))]]

        return {"success": True, "data": {"count": len(offers), "offers": offers}}
    except Exception as e:
        logger.exception("ka_search_initiative_listings failed")
        return {"success": False, "error": str(e), "error_type": "unknown"}


@tool(
    name="ka_register_initiative_for_sale",
    display_name="Offer an initiative for sale",
    description=(
        "Use this tool when a customer says they hold an expatriate initiative and want to SELL it. "
        "Before calling it you MUST have confirmed they are the holder and have an asking price. "
        "It records the offer for the team to verify — it does NOT publish it or promise a buyer. "
        "Tell the customer a colleague will confirm the details before it is listed."
    ),
    category="car_import",
    side_effect=True,
    parameters_schema={
        "type": "object",
        "properties": {
            "asking_price_egp": {"type": "number", "description": "What the holder wants, in EGP"},
            "initiative_type": {"type": "string", "description": "gulf or european"},
            "terms": {"type": "string", "description": "Anything the holder said about terms"},
        },
        "required": ["asking_price_egp"],
    },
)
def ka_register_initiative_for_sale(context, asking_price_egp: float,
                                    initiative_type: Optional[str] = None,
                                    terms: Optional[str] = None) -> Dict[str, Any]:
    """Record a holder's offer — as a draft, for a human to verify."""
    try:
        from car_import.models import Initiative, InitiativeListing

        partner = getattr(context, 'partner', None)
        if partner is None:
            return {"success": False, "error": "No customer in context", "error_type": "no_partner"}

        initiative = Initiative.all_objects.filter(holder=partner).first() \
            if hasattr(Initiative, 'all_objects') else Initiative.objects.filter(holder=partner).first()
        if initiative is None:
            initiative = Initiative.create(
                holder=partner, initiative_type=(initiative_type or 'gulf'),
                status='for_sale', transferable=True,
                notes='Created from a customer conversation; not yet verified.')

        # Draft, never 'available': a stranger's claim over a deposit right is
        # exactly the thing a human checks before it goes on a list.
        listing = InitiativeListing.create(
            initiative=initiative, state='draft',
            asking_price_egp=asking_price_egp, participation_terms=terms or '',
            notes='Registered by the assistant from a conversation.')

        return {
            "success": True,
            "data": {
                "registered": True,
                "reference": listing.pk,
                "state": "draft",
                "say_to_customer_ar": "سجّلت طلب حضرتك، وزميلي هيتواصل معاك يتأكد من التفاصيل قبل ما نعرضها.",
            },
        }
    except Exception as e:
        logger.exception("ka_register_initiative_for_sale failed")
        return {"success": False, "error": str(e), "error_type": "unknown"}
