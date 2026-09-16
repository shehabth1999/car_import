# -*- coding: utf-8 -*-
"""Screens for the two marketplaces the company runs itself."""
from django.utils.translation import gettext as _

car_import_showroom_list_view = {
    "key": "car_import_showroom_list_view",
    "name": "Showroom cars",
    "model": "car_import.showroomlisting",
    "menu_item": "car_import_menu_showroom",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {
        "tree": {
            "fields": [
                {"name": "title", "string": _("Car"), "widget": "text", "width": "260"},
                {"name": "state", "string": _("State"), "widget": "status", "width": "130"},
                {"name": "price_egp", "string": _("Price (EGP)"), "widget": "number", "width": "140"},
                {"name": "mileage_km", "string": _("Km"), "widget": "number", "width": "100"},
                {"name": "licensed", "string": _("Licensed"), "widget": "switch", "width": "110"},
                {"name": "protection_film", "string": _("Film"), "widget": "switch", "width": "90"},
                {"name": "location", "string": _("Where"), "widget": "text", "width": "150"},
                {"name": "published_to_website", "string": _("On the website"),
                 "widget": "switch", "width": "140"},
            ],
        },
    },
}

car_import_showroom_form_view = {
    "key": "car_import_showroom_form_view",
    "name": "Showroom car",
    "model": "car_import.showroomlisting",
    "menu_item": "car_import_menu_showroom",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions_list": [], "actions": []},
        "sheet": {
            "sections": [
                {
                    "title": _("The car"),
                    "groups": [
                        {"fields": [
                            {"name": "title", "string": _("Title"), "widget": "text", "required": True},
                            {"name": "vehicle", "string": _("Car record"), "widget": "relation",
                             "displayField": "name", "multiSelect": False},
                            {"name": "state", "string": _("State"), "widget": "select"},
                            {"name": "mileage_km", "string": _("Odometer (km)"), "widget": "number"},
                            {"name": "location", "string": _("Where it is"), "widget": "text"},
                        ]},
                        {"fields": [
                            {"name": "price_egp", "string": _("Price (EGP)"), "widget": "number"},
                            {"name": "negotiable", "string": _("Negotiable"), "widget": "switch"},
                            {"name": "licensed", "string": _("Licensed"), "widget": "switch"},
                            {"name": "protection_film", "string": _("Protection film"), "widget": "switch"},
                        ]},
                    ],
                },
                {
                    "title": _("The shop window"),
                    "groups": [
                        {"fields": [
                            {"name": "published_to_website", "string": _("On the website"),
                             "widget": "switch"},
                            # Stamped once, on first publication: "listed since"
                            # means the first time, not the latest edit.
                            {"name": "published_at", "string": _("Published"),
                             "widget": "datetime", "readonly": True},
                            {"name": "photos", "string": _("Photos"), "widget": "json"},
                        ]},
                        {"fields": [
                            {"name": "reserved_for", "string": _("Reserved for"), "widget": "relation",
                             "displayField": "name", "multiSelect": False},
                            {"name": "sold_deal", "string": _("Sold on deal"), "widget": "relation",
                             "displayField": "name", "multiSelect": False},
                            {"name": "description", "string": _("Description"), "widget": "textarea"},
                        ]},
                    ],
                },
            ],
        },
    },
}

car_import_showroom_search_view = {
    "key": "car_import_showroom_search_view",
    "name": "Showroom search",
    "model": "car_import.showroomlisting",
    "menu_item": "car_import_menu_showroom",
    "view_type": "search",
    "priority": 20,
    "module": "car_import",
    "body": {
        "search": {
            "search_fields": ["title", "location", "description"],
            "filters": [
                {"name": "available", "string": _("Available"),
                 "filter": {"field": "state", "operator": "eq", "value": "available"}},
                {"name": "on_website", "string": _("On the website"),
                 "filter": {"field": "published_to_website", "operator": "eq", "value": True}},
                {"name": "licensed", "string": _("Licensed"),
                 "filter": {"field": "licensed", "operator": "eq", "value": True}},
            ],
            "group_by": [
                {"name": "state", "string": _("State")},
                {"name": "location", "string": _("Where")},
            ],
        },
    },
}

car_import_initiative_listing_list_view = {
    "key": "car_import_initiative_listing_list_view",
    "name": "Initiatives for sale",
    "model": "car_import.initiativelisting",
    "menu_item": "car_import_menu_initiative_market",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {
        "tree": {
            "fields": [
                {"name": "initiative", "string": _("Initiative"), "widget": "relation",
                 "displayField": "name", "width": "260"},
                {"name": "state", "string": _("State"), "widget": "status", "width": "140"},
                {"name": "asking_price_egp", "string": _("Asking (EGP)"), "widget": "number", "width": "150"},
                {"name": "participation_terms", "string": _("Terms"), "widget": "text", "width": "260"},
                {"name": "buyer", "string": _("Buyer"), "widget": "relation",
                 "displayField": "name", "width": "180"},
                {"name": "matched_at", "string": _("Matched"), "widget": "datetime", "width": "150"},
            ],
        },
    },
}

car_import_initiative_listing_form_view = {
    "key": "car_import_initiative_listing_form_view",
    "name": "Initiative for sale",
    "model": "car_import.initiativelisting",
    "menu_item": "car_import_menu_initiative_market",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions_list": [], "actions": []},
        "sheet": {
            "sections": [
                {
                    "title": _("The offer"),
                    "groups": [
                        {"fields": [
                            {"name": "initiative", "string": _("Initiative"), "widget": "relation",
                             "displayField": "name", "multiSelect": False, "required": True},
                            {"name": "state", "string": _("State"), "widget": "select"},
                            {"name": "asking_price_egp", "string": _("Asking price (EGP)"),
                             "widget": "number"},
                        ]},
                        {"fields": [
                            {"name": "participation_terms", "string": _("Terms"), "widget": "text"},
                            {"name": "buyer", "string": _("Buyer"), "widget": "relation",
                             "displayField": "name", "multiSelect": False},
                            {"name": "matched_at", "string": _("Matched"), "widget": "datetime"},
                        ]},
                    ],
                },
                {
                    "title": _("Notes"),
                    "groups": [{"fields": [{"name": "notes", "string": _("Notes"),
                                            "widget": "textarea"}]}],
                },
            ],
        },
    },
}

car_import_initiative_listing_search_view = {
    "key": "car_import_initiative_listing_search_view",
    "name": "Initiative market search",
    "model": "car_import.initiativelisting",
    "menu_item": "car_import_menu_initiative_market",
    "view_type": "search",
    "priority": 20,
    "module": "car_import",
    "body": {
        "search": {
            "search_fields": ["participation_terms", "notes"],
            "filters": [
                {"name": "available", "string": _("Available"),
                 "filter": {"field": "state", "operator": "eq", "value": "available"}},
                {"name": "matched", "string": _("Buyer found"),
                 "filter": {"field": "state", "operator": "eq", "value": "matched"}},
            ],
            "group_by": [{"name": "state", "string": _("State")}],
        },
    },
}
