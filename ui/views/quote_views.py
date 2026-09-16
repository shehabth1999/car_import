# -*- coding: utf-8 -*-
"""The quotation screens — the calculator, as something a salesman can use.

The form reads top to bottom the way the client's spreadsheet does: type the
advertised price, tick the options, and read the stack underneath. Everything
below the input line is read-only on purpose. A figure a person can type over
is a figure nobody can defend three months later, and the whole reason this
model freezes its results is so that an old quote still explains itself.

No status pills in the header. Five states plus three buttons share one 30px
row with overflow hidden, and the pills win — the buttons get laid out at
negative x and quietly cease to exist. The state is a field and a ribbon
instead.
"""
from django.utils.translation import gettext as _

_QUOTE_ACTIONS = [
    {
        "name": "action_recalculate",
        "string": _("Recalculate"),
        "icon": "Calculator",
        "type": "server",
        "as": "button",
        "variant": "primary",
        "view_type": ["form", "list"],
    },
    {
        "name": "action_mark_sent",
        "string": _("Mark as sent"),
        "icon": "Send",
        "type": "server",
        "as": "button",
        "variant": "secondary",
        "view_type": ["form", "list"],
        "invisible": {"field": "state", "operator": "ne", "value": "draft"},
    },
    {
        "name": "action_print_offer",
        "string": _("Print the offer"),
        "icon": "Printer",
        "type": "server",
        "as": "button",
        "variant": "secondary",
        "view_type": ["form"],
    },
    {
        "name": "action_send_offer",
        "string": _("Send the offer to the customer"),
        "icon": "MessageCircle",
        "type": "server",
        "as": "dropdown",
        "view_type": ["form", "list"],
        # It messages a real customer. Nobody presses this by accident.
        "confirm_required": True,
    },
    {
        "name": "action_accept",
        "string": _("Customer accepted"),
        "icon": "BadgeCheck",
        "type": "server",
        "as": "dropdown",
        "view_type": ["form", "list"],
    },
]


car_quote_list_view = {
    "key": "car_import_quote_list_view",
    "name": _("Quotations"),
    "model": "car_import.quote",
    "menu_item": "car_import_menu_quotes",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions": _QUOTE_ACTIONS},
        "tree": {
            "fields": [
                {"name": "name", "widget": "text", "string": _("Reference"), "width": "130"},
                {"name": "quote_date", "widget": "date", "string": _("Date"), "width": "120"},
                {"name": "partner", "widget": "relation", "displayField": "name",
                 "string": _("Customer"), "width": "190"},
                {"name": "vehicle", "widget": "relation", "displayField": "name",
                 "string": _("Car"), "width": "200"},
                # `number`, not `money`: the money widget renders a dollar sign
                # regardless of the figure's actual currency, and a euro price
                # shown as $64,500.00 is a price the customer will argue about.
                {"name": "gross_price_eur", "widget": "number", "string": _("With VAT €"), "width": "130"},
                {"name": "total_eur", "widget": "number", "string": _("Total €"), "width": "130"},
                {"name": "deposit_pct", "widget": "number", "string": _("Deposit %"), "width": "110"},
                {"name": "deposit_eur", "widget": "number", "string": _("Deposit €"), "width": "130"},
                {"name": "paid_eur", "widget": "number", "string": _("Paid €"), "width": "120"},
                {"name": "remaining_eur", "widget": "number", "string": _("Owed €"), "width": "120"},
                {"name": "state", "widget": "status", "string": _("Status"), "width": "130"},
                {"name": "assigned_to", "widget": "relation", "displayField": "name",
                 "string": _("Agent"), "width": "150"},
            ],
        },
    },
}


car_quote_form_view = {
    "key": "car_import_quote_form_view",
    "name": _("Quotation"),
    "model": "car_import.quote",
    "menu_item": "car_import_menu_quotes",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions_list": [], "actions": _QUOTE_ACTIONS},
        "sheet": {
            "ribbon": {
                "field_text": "state",
                "color": {
                    "success": {"field": "state", "operator": "eq", "value": "accepted"},
                    "danger": {"field": "state", "operator": "eq", "value": "declined"},
                    "warning": {"field": "state", "operator": "eq", "value": "expired"},
                },
                "invisible": {"field": "state", "operator": "eq", "value": "draft"},
            },
            "sections": [
                {
                    "title": _("Who and what"),
                    "groups": [
                        {"fields": [
                            # Declared and hidden so the ribbon can read it: the
                            # ribbon renders from persisted data, not from the
                            # header alone.
                            {"name": "state", "string": _("Status"), "widget": "select",
                             "invisible": True},
                            {"name": "name", "string": _("Reference"), "widget": "text",
                             "readonly": True},
                            {"name": "partner", "string": _("Customer"), "widget": "relation",
                             "displayField": "name", "multiSelect": False},
                            {"name": "deal", "string": _("Deal"), "widget": "relation",
                             "displayField": "name", "multiSelect": False},
                        ]},
                        {"fields": [
                            {"name": "vehicle", "string": _("Car"), "widget": "relation",
                             "displayField": "name", "multiSelect": False},
                            {"name": "assigned_to", "string": _("Sales agent"), "widget": "relation",
                             "displayField": "name", "multiSelect": False},
                            {"name": "quote_date", "string": _("Date"), "widget": "date"},
                            {"name": "valid_until", "string": _("Valid until"), "widget": "date"},
                        ]},
                    ],
                },
                {
                    "title": _("What the salesman enters"),
                    "groups": [
                        {"fields": [
                            {"name": "gross_price_eur", "string": _("Price with VAT (€)"),
                             "widget": "number", "required": True},
                            {"name": "vat_rate_pct", "string": _("VAT %"), "widget": "number"},
                            {"name": "with_eur1", "string": _("EUR 1 certificate"), "widget": "switch"},
                            {"name": "shipping_type", "string": _("Shipping"), "widget": "select"},
                        ]},
                        {"fields": [
                            {"name": "port", "string": _("Port of arrival"), "widget": "select"},
                            {"name": "collect_from_showroom", "string": _("Collected from the showroom"),
                             "widget": "switch"},
                            {"name": "admin_fee_discount_eur",
                             "string": _("Discount on the admin fee (€)"), "widget": "number"},
                            {"name": "fx_rate_egp", "string": _("EGP per EUR (indicative only)"),
                             "widget": "number"},
                        ]},
                    ],
                },
                {
                    # The plan's shape, and the client's own habit: an agent
                    # answers "do you have a C200?" with five links at five
                    # prices. Each row carries its own whole stack, because a
                    # cheaper car can land in a band with a BIGGER deposit
                    # percentage — which is exactly the comparison the customer
                    # is making.
                    "title": _("Candidate cars — tick the one the customer chose"),
                    "groups": [{"fullWidth": True, "fields": [
                        {"name": "options", "string": "", "widget": "list",
                         "required": False, "minRows": 0, "maxRows": 12,
                         "createable": True, "deleteable": True, "selectable": False,
                         "editable": True,
                         "listConfig": {"fields": [
                             {"name": "options.sequence", "widget": "number", "string": _("#")},
                             {"name": "options.label", "widget": "text", "string": _("Car")},
                             {"name": "options.listing_url", "widget": "text",
                              "string": _("Advert link")},
                             {"name": "options.gross_price_eur", "widget": "number",
                              "string": _("With VAT €"), "required": True},
                             {"name": "options.with_eur1", "widget": "switch",
                              "string": _("EUR 1")},
                             {"name": "options.shipping_type", "widget": "select",
                              "string": _("Shipping")},
                             {"name": "options.port", "widget": "select", "string": _("Port")},
                             {"name": "options.total_eur", "widget": "number",
                              "string": _("Total €"), "readonly": True},
                             {"name": "options.deposit_pct", "widget": "number",
                              "string": _("Dep. %"), "readonly": True},
                             {"name": "options.deposit_eur", "widget": "number",
                              "string": _("Deposit €"), "readonly": True},
                             {"name": "options.is_accepted", "widget": "switch",
                              "string": _("Chosen")},
                         ]},
                         },
                    ]}],
                },
                {
                    "title": _("The price, as the customer sees it"),
                    "groups": [
                        {"fields": [
                            {"name": "band_label", "string": _("Band used"), "widget": "text",
                             "readonly": True},
                            {"name": "net_eur", "string": _("Net price (€)"), "widget": "number",
                             "readonly": True},
                            {"name": "vat_reclaimable_eur", "string": _("VAT reclaimed (€)"),
                             "widget": "number", "readonly": True},
                            {"name": "shipping_eur", "string": _("Shipping (€)"), "widget": "number",
                             "readonly": True},
                            {"name": "admin_fee_before_discount_eur", "string": _("Admin fee (€)"),
                             "widget": "number", "readonly": True},
                            {"name": "eur1_eur", "string": _("EUR 1 (€)"), "widget": "number",
                             "readonly": True},
                            {"name": "shipping_extra_eur", "string": _("Shipping option (€)"),
                             "widget": "number", "readonly": True},
                        ]},
                        {"fields": [
                            {"name": "total_eur", "string": _("Total selling price (€)"),
                             "widget": "number", "readonly": True},
                            {"name": "deposit_pct", "string": _("Deposit %"), "widget": "number",
                             "readonly": True},
                            {"name": "deposit_eur", "string": _("Deposit (€)"), "widget": "number",
                             "readonly": True},
                            {"name": "balance_eur", "string": _("Balance (€)"), "widget": "number",
                             "readonly": True},
                            {"name": "calculated_at", "string": _("Calculated at"),
                             "widget": "datetime", "readonly": True},
                            # Only ever filled when the engine refused. It is a
                            # sentence, not a code: "no band covers 30,000.50 €".
                            {"name": "pricing_error", "string": _("Why there is no price"),
                             "widget": "text", "readonly": True},
                        ]},
                    ],
                },
                {
                    # Kept in its own section, and never added to the euro
                    # total. These are collected in Egypt, on arrival, in
                    # pounds. Summing them with the euros would turn a quote
                    # into a promise about an exchange rate nobody made.
                    "title": _("Collected in Egypt, on arrival (EGP)"),
                    "groups": [
                        {"fields": [
                            {"name": "port_fee_egp", "string": _("Port fees (EGP)"),
                             "widget": "number", "readonly": True},
                            {"name": "showroom_fee_egp", "string": _("Showroom collection (EGP)"),
                             "widget": "number", "readonly": True},
                        ]},
                        {"fields": [
                            {"name": "egp_due_on_arrival", "string": _("Due on arrival (EGP)"),
                             "widget": "number", "readonly": True},
                            {"name": "total_egp_indicative",
                             "string": _("Indicative total (EGP) — today's rate only"),
                             "widget": "number", "readonly": True},
                        ]},
                    ],
                },
                {
                    "title": _("What the customer has paid"),
                    "groups": [
                        {"fields": [
                            # A real amount somebody types, not a status somebody
                            # picks: customers pay more than the deposit, and
                            # sometimes the whole car.
                            {"name": "paid_eur", "string": _("Paid so far (€)"), "widget": "number"},
                            {"name": "deposit_covered", "string": _("Deposit covered"),
                             "widget": "switch", "readonly": True},
                            {"name": "fully_paid", "string": _("Paid in full"), "widget": "switch",
                             "readonly": True},
                        ]},
                        {"fields": [
                            {"name": "remaining_eur", "string": _("Still owed (€)"),
                             "widget": "number", "readonly": True},
                            {"name": "overpaid_eur", "string": _("Overpaid (€)"), "widget": "number",
                             "readonly": True},
                            {"name": "sent_at", "string": _("Sent at"), "widget": "datetime",
                             "readonly": True},
                        ]},
                    ],
                },
                {
                    "title": _("Notes"),
                    "groups": [
                        {"fullWidth": True, "fields": [
                            {"name": "notes", "string": _("Notes"), "widget": "textarea"},
                        ]},
                    ],
                },
            ],
        },
    },
}


car_quote_search_view = {
    "key": "car_import_quote_search_view",
    "name": _("Quotation search"),
    "model": "car_import.quote",
    "menu_item": "car_import_menu_quotes",
    "view_type": "search",
    "priority": 20,
    "module": "car_import",
    "body": {
        "search": {
            "search_fields": [
                {"name": ["name"], "string": _("Reference"), "widget": "text"},
                {"name": ["partner__name"], "string": _("Customer"), "widget": "text"},
                {"name": ["vehicle__model"], "string": _("Model"), "widget": "text"},
                {"name": ["band_label"], "string": _("Band"), "widget": "text"},
            ],
            "filters": [
                {"name": "draft", "string": _("Draft"),
                 "filter": {"field": "state", "operator": "eq", "value": "draft"}},
                {"name": "sent", "string": _("Sent"),
                 "filter": {"field": "state", "operator": "eq", "value": "sent"}},
                {"name": "accepted", "string": _("Accepted"),
                 "filter": {"field": "state", "operator": "eq", "value": "accepted"}},
                {"name": "deposit_covered", "string": _("Deposit covered"),
                 "filter": {"field": "deposit_covered", "operator": "eq", "value": True}},
                {"name": "overpaid", "string": _("Overpaid"),
                 "filter": {"field": "overpaid_eur", "operator": "gt", "value": 0}},
                # The gap case. A quote that fell through every band has no
                # price, and it should be one click to find them all rather
                # than a discovery a customer makes on the phone.
                {"name": "no_price", "string": _("No price yet"),
                 "filter": {"field": "total_eur", "operator": "eq", "value": 0}},
            ],
            "group_by": [
                {"name": "state", "string": _("Status")},
                {"name": "assigned_to", "string": _("Agent")},
                {"name": "port", "string": _("Port")},
                {"name": "band", "string": _("Band")},
            ],
            "order_by": [
                {"name": "id", "string": _("Newest"), "direction": "desc"},
                {"name": "total_eur", "string": _("Largest"), "direction": "desc"},
            ],
        },
    },
}
