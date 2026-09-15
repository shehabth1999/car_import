# -*- coding: utf-8 -*-
"""Screens for the supplier listings we pulled from the marketplace."""
from django.utils.translation import gettext as _

car_import_listing_list_view = {
    "key": "car_import_listing_list_view",
    "name": "Supplier listings",
    "model": "car_import.supplierlisting",
    "menu_item": "car_import_menu_listings",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {
        "tree": {
            "fields": [
                {"name": "ad_id", "string": _("Advert"), "widget": "text", "width": "130"},
                {"name": "make", "string": _("Make"), "widget": "text", "width": "130"},
                {"name": "model", "string": _("Model"), "widget": "text", "width": "110"},
                {"name": "version", "string": _("Version"), "widget": "text", "width": "200"},
                {"name": "model_year", "string": _("Year"), "widget": "number", "width": "80"},
                {"name": "mileage_km", "string": _("Km"), "widget": "number", "width": "90"},
                # "number", not "money": the money widget stamps the tenant's own
                # currency symbol on it, and rendered a German EUR price as
                # "$64,500.00". In a business quoting EUR, USD and EGP in the
                # same breath, a wrong symbol is a wrong number.
                {"name": "price_gross_eur", "string": _("Price (EUR)"), "widget": "number", "width": "120"},
                # The column the whole price stack depends on — visible, not buried.
                {"name": "vatable", "string": _("VAT deductible"), "widget": "switch", "width": "120"},
                {"name": "seller_name", "string": _("Seller"), "widget": "text", "width": "180"},
                {"name": "country", "string": _("Country"), "widget": "text", "width": "80"},
                {"name": "still_available", "string": _("Still listed"), "widget": "switch", "width": "100"},
                {"name": "is_simulated", "string": _("Simulated"), "widget": "switch", "width": "100"},
                {"name": "last_seen_at", "string": _("Last seen"), "widget": "datetime", "width": "150"},
            ],
        },
    },
}

car_import_listing_form_view = {
    "key": "car_import_listing_form_view",
    "name": "Supplier listing",
    "model": "car_import.supplierlisting",
    "menu_item": "car_import_menu_listings",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions_list": [], "actions": []},
        "sheet": {
            "ribbon": {
                "field_text": "is_simulated",
                "color": {"warning": {"field": "is_simulated", "operator": "eq", "value": True}},
                "invisible": {"field": "is_simulated", "operator": "eq", "value": False},
            },
            "sections": [
                {
                    "title": _("The advert"),
                    "groups": [
                        {
                            "fields": [
                                {"name": "is_simulated", "string": _("Simulated"),
                                 "widget": "switch", "invisible": True},
                                {"name": "source", "string": _("Source"), "widget": "select", "readonly": True},
                                {"name": "ad_id", "string": _("Advert number"), "widget": "text", "readonly": True},
                                {"name": "url", "string": _("Link"), "widget": "url"},
                                {"name": "still_available", "string": _("Still listed"), "widget": "switch"},
                                {"name": "last_seen_at", "string": _("Last seen"),
                                 "widget": "datetime", "readonly": True},
                            ],
                        },
                        {
                            "fields": [
                                {"name": "seller_name", "string": _("Seller"), "widget": "text"},
                                {"name": "seller_type", "string": _("Seller type"), "widget": "select"},
                                {"name": "seller_city", "string": _("City"), "widget": "text"},
                                {"name": "country", "string": _("Country"), "widget": "text"},
                            ],
                        },
                    ],
                },
                {
                    "title": _("The car"),
                    "groups": [
                        {
                            "fields": [
                                {"name": "make", "string": _("Make"), "widget": "text"},
                                {"name": "model", "string": _("Model"), "widget": "text"},
                                {"name": "version", "string": _("Version"), "widget": "text"},
                                {"name": "model_year", "string": _("Model year"), "widget": "number"},
                                {"name": "first_registration", "string": _("First registration"), "widget": "text"},
                                {"name": "mileage_km", "string": _("Odometer (km)"), "widget": "number"},
                            ],
                        },
                        {
                            "fields": [
                                {"name": "cc", "string": _("Engine (cc)"), "widget": "number"},
                                {"name": "power_hp", "string": _("Power (hp)"), "widget": "number"},
                                {"name": "fuel", "string": _("Fuel"), "widget": "text"},
                                {"name": "gearbox", "string": _("Gearbox"), "widget": "text"},
                                {"name": "colour_exterior", "string": _("Colour"), "widget": "text"},
                                {"name": "accident_free", "string": _("Accident-free"), "widget": "switch"},
                            ],
                        },
                    ],
                },
                {
                    "title": _("Price and VAT"),
                    "groups": [
                        {
                            "fields": [
                                {"name": "price_gross_eur", "string": _("Listed price (EUR)"), "widget": "number"},
                                {"name": "vatable", "string": _("VAT deductible"), "widget": "switch"},
                                {"name": "vat_rate_pct", "string": _("German VAT %"), "widget": "number"},
                            ],
                        },
                        {
                            "fields": [
                                {"name": "vehicle", "string": _("Car record"), "widget": "relation",
                                 "displayField": "name", "multiSelect": False},
                                {"name": "deal", "string": _("Deal"), "widget": "relation",
                                 "displayField": "name", "multiSelect": False},
                            ],
                        },
                    ],
                },
            ],
        },
    },
}

car_import_listing_search_view = {
    "key": "car_import_listing_search_view",
    "name": "Supplier listing search",
    "model": "car_import.supplierlisting",
    "menu_item": "car_import_menu_listings",
    "view_type": "search",
    "priority": 20,
    "module": "car_import",
    "body": {
        "search": {
            "search_fields": ["ad_id", "make", "model", "version", "seller_name"],
            "filters": [
                {"name": "available", "string": _("Still listed"),
                 "filter": {"field": "still_available", "operator": "eq", "value": True}},
                {"name": "vat_deductible", "string": _("VAT deductible"),
                 "filter": {"field": "vatable", "operator": "eq", "value": True}},
                {"name": "real_only", "string": _("Real adverts only"),
                 "filter": {"field": "is_simulated", "operator": "eq", "value": False}},
                {"name": "gone", "string": _("Sold or removed"),
                 "filter": {"field": "still_available", "operator": "eq", "value": False}},
            ],
            "group_by": [
                {"name": "make", "string": _("Make")},
                {"name": "model", "string": _("Model")},
                {"name": "seller_name", "string": _("Seller")},
                {"name": "country", "string": _("Country")},
            ],
        },
    },
}
