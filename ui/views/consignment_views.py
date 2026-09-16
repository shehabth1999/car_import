# -*- coding: utf-8 -*-
"""The consignment screens — L6, the sixth revenue line.

The form is laid out around the question the business actually asks about one
of these: *is a commission owed, and how much?* Everything that decides the
answer — the dates, the tail, the introduction date, the price band — sits in
one section rather than scattered among the car's details, because those four
fields are the ones a dispute turns on.
"""
from django.utils.translation import gettext as _

_ACTIONS = [
    {
        "name": "action_mark_sold",
        "string": _("Mark as sold"),
        "icon": "BadgeCheck",
        "type": "server",
        "as": "button",
        "variant": "primary",
        "view_type": ["form", "list"],
    },
]


car_consignment_list_view = {
    "key": "car_import_consignment_list_view",
    "name": _("Consignment mandates"),
    "model": "car_import.consignmentmandate",
    "menu_item": "car_import_menu_consignment",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions": _ACTIONS},
        "tree": {"fields": [
            {"name": "name", "widget": "text", "string": _("Reference"), "width": "130"},
            {"name": "owner", "widget": "relation", "displayField": "name",
             "string": _("Owner"), "width": "190"},
            {"name": "car_description", "widget": "text", "string": _("Car"), "width": "210"},
            {"name": "price_floor_egp", "widget": "number", "string": _("From (EGP)"),
             "width": "140"},
            {"name": "price_ceiling_egp", "widget": "number", "string": _("To (EGP)"),
             "width": "140"},
            {"name": "commission_pct", "widget": "number", "string": _("Comm. %"), "width": "110"},
            {"name": "expires_on", "widget": "date", "string": _("Runs until"), "width": "130"},
            {"name": "sold_price_egp", "widget": "number", "string": _("Sold for"), "width": "140"},
            {"name": "commission_due_egp", "widget": "number", "string": _("Commission"),
             "width": "140"},
            {"name": "state", "widget": "status", "string": _("Status"), "width": "130"},
        ]},
    },
}


car_consignment_form_view = {
    "key": "car_import_consignment_form_view",
    "name": _("Consignment mandate"),
    "model": "car_import.consignmentmandate",
    "menu_item": "car_import_menu_consignment",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions_list": [], "actions": _ACTIONS},
        "sheet": {
            "ribbon": {
                "field_text": "state",
                "color": {
                    "success": {"field": "state", "operator": "eq", "value": "sold"},
                    "danger": {"field": "state", "operator": "eq", "value": "withdrawn"},
                    "warning": {"field": "state", "operator": "eq", "value": "expired"},
                },
                "invisible": {"field": "state", "operator": "eq", "value": "draft"},
            },
            "sections": [
                {"title": _("Whose car"), "groups": [
                    {"fields": [
                        {"name": "state", "string": _("Status"), "widget": "select",
                         "invisible": True},
                        {"name": "name", "string": _("Reference"), "widget": "text",
                         "readonly": True},
                        {"name": "owner", "string": _("Owner"), "widget": "relation",
                         "displayField": "name", "required": True, "multiSelect": False},
                        {"name": "assigned_to", "string": _("Broker"), "widget": "relation",
                         "displayField": "name", "multiSelect": False},
                    ]},
                    {"fields": [
                        # Most consignment cars are not ours and never will be,
                        # so the description is the normal case and the vehicle
                        # link is the exception.
                        {"name": "car_description", "string": _("Car"), "widget": "text"},
                        {"name": "vehicle", "string": _("…or one of our cars"),
                         "widget": "relation", "displayField": "name", "multiSelect": False},
                    ]},
                ]},
                {"title": _("What decides the commission"), "groups": [
                    {"fields": [
                        {"name": "signed_on", "string": _("Signed on"), "widget": "date"},
                        {"name": "expires_on", "string": _("Runs until"), "widget": "date"},
                        {"name": "tail_days", "string": _("Tail (days)"), "widget": "number"},
                        {"name": "cure_days", "string": _("Cure period (days)"),
                         "widget": "number"},
                    ]},
                    {"fields": [
                        {"name": "is_exclusive", "string": _("Exclusive"), "widget": "switch"},
                        {"name": "auto_renews", "string": _("Renews automatically"),
                         "widget": "switch"},
                        {"name": "price_floor_egp", "string": _("Price band — from (EGP)"),
                         "widget": "number"},
                        {"name": "price_ceiling_egp", "string": _("Price band — to (EGP)"),
                         "widget": "number"},
                    ]},
                ]},
                {"title": _("The commission"), "groups": [
                    {"fields": [
                        # No default anywhere. It is blank in their own template,
                        # and a plausible guess here becomes a number somebody
                        # quotes to an owner.
                        {"name": "commission_pct", "string": _("Commission %"),
                         "widget": "number"},
                        {"name": "commission_fixed_egp", "string": _("…or a fixed amount (EGP)"),
                         "widget": "number"},
                    ]},
                    {"fields": [
                        {"name": "marketing_cost_note", "string": _("Marketing costs"),
                         "widget": "text"},
                    ]},
                ]},
                {"title": _("The sale"), "groups": [
                    {"fields": [
                        {"name": "buyer", "string": _("Buyer"), "widget": "relation",
                         "displayField": "name", "multiSelect": False},
                        {"name": "buyer_introduced_on", "string": _("Buyer introduced on"),
                         "widget": "date"},
                        {"name": "deposit_taken_egp", "string": _("Deposit taken as agent (EGP)"),
                         "widget": "number"},
                    ]},
                    {"fields": [
                        {"name": "sold_on", "string": _("Sold on"), "widget": "date"},
                        {"name": "sold_price_egp", "string": _("Sold for (EGP)"),
                         "widget": "number"},
                        {"name": "commission_due_egp", "string": _("Commission due (EGP)"),
                         "widget": "number", "readonly": True},
                        {"name": "commission_paid", "string": _("Commission received"),
                         "widget": "switch"},
                    ]},
                ]},
                {"title": _("Notes"), "groups": [
                    {"fullWidth": True, "fields": [
                        {"name": "notes", "string": _("Notes"), "widget": "textarea"},
                    ]},
                ]},
            ],
        },
    },
}


car_consignment_search_view = {
    "key": "car_import_consignment_search_view",
    "name": _("Consignment search"),
    "model": "car_import.consignmentmandate",
    "menu_item": "car_import_menu_consignment",
    "view_type": "search",
    "priority": 20,
    "module": "car_import",
    "body": {"search": {
        "search_fields": [
            {"name": ["name"], "string": _("Reference"), "widget": "text"},
            {"name": ["owner__name"], "string": _("Owner"), "widget": "text"},
            {"name": ["car_description"], "string": _("Car"), "widget": "text"},
        ],
        "filters": [
            {"name": "active", "string": _("Active"),
             "filter": {"field": "state", "operator": "eq", "value": "active"}},
            {"name": "sold", "string": _("Sold"),
             "filter": {"field": "state", "operator": "eq", "value": "sold"}},
            # The one that costs money if nobody looks: a commission earned and
            # never collected.
            {"name": "commission_unpaid", "string": _("Commission not received"),
             "filter": {"field": "commission_paid", "operator": "eq", "value": False}},
            {"name": "no_commission_set", "string": _("No commission agreed"),
             "filter": {"field": "commission_pct", "operator": "is_empty", "value": True}},
        ],
        "group_by": [
            {"name": "state", "string": _("Status")},
            {"name": "assigned_to", "string": _("Broker")},
        ],
        "order_by": [
            {"name": "expires_on", "string": _("Expiring soonest"), "direction": "asc"},
            {"name": "id", "string": _("Newest"), "direction": "desc"},
        ],
    }},
}
