# -*- coding: utf-8 -*-
"""The consignment screens — L6, the sixth revenue line.

The form is laid out around the question the business actually asks about one
of these: *is a commission owed, and how much?* The four things that decide it
— the dates, the tail, the introduction date, the price band — sit together in
one tab, the sale in the next, and the commission recomputes in the footer as
the figures are typed.
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
                         "displayField": "name", "required": True, "multiSelect": False,
                         "help": _("The person whose car we sell for them — the contract's first party")},
                        {"name": "assigned_to", "string": _("Broker"), "widget": "relation",
                         "displayField": "name", "multiSelect": False},
                    ]},
                    {"fields": [
                        {"name": "car_description", "string": _("Car"), "widget": "text",
                         "help": _("Free text when the car is not one of ours — most of them are not")},
                        {"name": "vehicle", "string": _("…or one of our cars"),
                         "widget": "relation", "displayField": "name", "multiSelect": False},
                    ]},
                ]},
            ],
            "footer": {
                "fields": [
                    {"name": "sold_price_egp", "string": _("Sold for EGP"), "widget": "number"},
                    {"separator": "thin"},
                    {"name": "commission_due_egp", "string": _("Commission due EGP"), "widget": "number",
                     "highlight": True},
                ],
                "position": "end",
            },
        },
        "tabs": [
            {
                "title": _("The mandate"),
                "sections": [{
                    "title": _("What decides whether a commission is owed"),
                    "groups": [
                        {"title": _("Dates"), "fields": [
                            {"name": "signed_on", "string": _("Signed on"), "widget": "date"},
                            {"name": "expires_on", "string": _("Runs until"), "widget": "date",
                             "help": _("A sale after this date owes nothing — unless the buyer was ours and the tail applies")},
                            {"name": "tail_days", "string": _("Tail (days)"), "widget": "number",
                             "help": _("A buyer we introduced who signs within this many days after the mandate ends still owes commission")},
                            {"name": "cure_days", "string": _("Cure period (days)"),
                             "widget": "number",
                             "help": _("Days the owner has to put a breach right before it counts")},
                            {"name": "is_exclusive", "string": _("Exclusive"), "widget": "switch",
                             "help": _("While it runs, the owner may not sell the car themselves")},
                            {"name": "auto_renews", "string": _("Renews automatically"),
                             "widget": "switch"},
                        ]},
                        {"title": _("The price band and the commission"), "fields": [
                            {"name": "currency", "string": _("Currency"), "widget": "relation", "displayField": "code", "multiSelect": False,
                             "help": _("Pounds — the showroom's currency")},
                            {"name": "price_floor_egp", "string": _("Price band — from (EGP)"),
                             "widget": "number", "onChange": True,
                             "help": _("Selling below this is selling the owner's car for less than they allowed — management is asked")},
                            {"name": "price_ceiling_egp", "string": _("Price band — to (EGP)"),
                             "widget": "number", "onChange": True},
                            {"name": "commission_pct", "string": _("Commission %"),
                             "widget": "number", "onChange": True,
                             "help": _("Of the final price. Blank in the client's own template — ask before quoting a number")},
                            {"name": "commission_fixed_egp", "string": _("…or a fixed amount (EGP)"),
                             "widget": "number", "onChange": True,
                             "help": _("Wins over the percentage when both are set")},
                            {"name": "marketing_cost_note", "string": _("Marketing costs"),
                             "widget": "text",
                             "help": _("Borne by the broker; anything extraordinary needs the owner in writing")},
                        ]},
                    ],
                }],
            },
            {
                "title": _("The sale"),
                "sections": [{
                    "title": "",
                    "groups": [
                        {"title": _("The buyer"), "fields": [
                            {"name": "buyer", "string": _("Buyer"), "widget": "relation",
                             "displayField": "name", "multiSelect": False},
                            {"name": "buyer_introduced_on", "string": _("Buyer introduced on"),
                             "widget": "date", "onChange": True,
                             "help": _("The date that decides whether the tail applies. Undated means no claim")},
                            {"name": "deposit_taken_egp", "string": _("Deposit taken as agent (EGP)"),
                             "widget": "number",
                             "help": _("Held for the owner, not the company's money")},
                        ]},
                        {"title": _("The close"), "fields": [
                            {"name": "sold_on", "string": _("Sold on"), "widget": "date", "onChange": True},
                            {"name": "sold_price_egp", "string": _("Sold for (EGP)"),
                             "widget": "number", "onChange": True},
                            {"name": "commission_due_egp", "string": _("Commission due (EGP)"),
                             "widget": "number", "readonly": True,
                             "help": _("Computed: inside the mandate or its tail, by the percentage or the fixed amount")},
                            {"name": "commission_paid", "string": _("Commission received"),
                             "widget": "switch"},
                        ]},
                    ],
                }],
            },
            {
                "title": _("Notes"),
                "sections": [{
                    "title": "",
                    "groups": [{"fullWidth": True, "fields": [
                        {"name": "notes", "string": _("Notes"), "widget": "textarea", "rows": 5},
                    ]}],
                }],
            },
        ],
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
