# -*- coding: utf-8 -*-
"""The quotation screens — the calculator, as something a salesman can use.

The top of the form is the client's spreadsheet: the advertised price and the
five switches. Everything the engine answers lives in tabs and in a footer
that stays on screen — total, deposit, balance, still owed — and every input
carries an `onChange`, so the figures move as the salesman types instead of
after a press of *Recalculate*. Nothing typed into a result column is ever
saved: those fields are `editable=False`, and the save re-runs the engine.

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

_RO_NUMBER = {"widget": "number", "readonly": True}


def _ro(name, string, help_text=None):
    field = {"name": name, "string": string, **_RO_NUMBER}
    if help_text:
        field["help"] = help_text
    return field


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
                {"name": "car_label", "widget": "text", "string": _("Car (as quoted)"), "width": "200"},
                {"name": "issued_by_ai", "widget": "checkbox", "string": _("By the assistant"), "width": "130"},
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
                             "displayField": "name", "multiSelect": False, "onChange": True,
                             "help": _("Picking a customer pulls in their open deal, its car and its agent")},
                            {"name": "deal", "string": _("Deal"), "widget": "relation",
                             "displayField": "name", "multiSelect": False,
                             "help": _("When the customer accepts, this deal's agreed amount and payment marks follow the quotation")},
                        ]},
                        {"fields": [
                            {"name": "vehicle", "string": _("Car"), "widget": "relation",
                             "displayField": "name", "multiSelect": False,
                             "help": _("Optional on a multi-car offer — the chosen candidate's car is copied here")},
                            {"name": "car_label", "string": _("Car (as quoted)"), "widget": "text",
                             "help": _("The car in words — what the offer prints when no car record exists yet, which is every quotation the assistant makes from an advert")},
                            {"name": "listing", "string": _("Advert it was priced from"), "widget": "relation",
                             "displayField": "ad_id", "multiSelect": False},
                            {"name": "issued_by_ai", "string": _("Made by the assistant"), "widget": "switch",
                             "readonly": True},
                            {"name": "assigned_to", "string": _("Sales agent"), "widget": "relation",
                             "displayField": "name", "multiSelect": False,
                             "help": _("Defaults to whoever writes it. An agent only sees their own quotations")},
                            {"name": "quote_date", "string": _("Date"), "widget": "date"},
                            {"name": "valid_until", "string": _("Valid until"), "widget": "date",
                             "help": _("The German seller can sell the car meanwhile — a short validity is honest")},
                        ]},
                    ],
                },
                {
                    "title": _("What the salesman enters"),
                    "groups": [
                        {"fields": [
                            {"name": "currency", "string": _("Currency"), "widget": "relation", "displayField": "code", "multiSelect": False,
                             "help": _("Euros — the German advert's currency. Every figure on this quotation is in it")},
                            {"name": "gross_price_eur", "string": _("Price with VAT (€)"),
                             "widget": "number", "required": True, "onChange": True,
                             "help": _("The number on the German advert. Everything below follows from it — and recalculates as you type")},
                            {"name": "vat_rate_pct", "string": _("VAT %"), "widget": "number", "onChange": True,
                             "help": _("German VAT, 19%. Only changes if the seller's invoice says otherwise")},
                            {"name": "with_eur1", "string": _("EUR 1 certificate"), "widget": "switch",
                             "onChange": True,
                             "help": _("Proof of EU origin — cuts the customs rate. The car must have been built for the EU market")},
                            {"name": "shipping_type", "string": _("Shipping"), "widget": "select", "onChange": True,
                             "help": _("Standard RORO is included; VIP RORO and container are surcharges")},
                        ]},
                        {"fields": [
                            {"name": "port", "string": _("Port of arrival"), "widget": "select", "onChange": True},
                            {"name": "collect_from_showroom", "string": _("Collected from the showroom"),
                             "widget": "switch", "onChange": True,
                             "help": _("Door delivery is included in the port fee. A customer who collects from the showroom gets the amount on the arrival tab taken OFF what is due on arrival")},
                            {"name": "admin_fee_discount_eur",
                             "string": _("Discount on the admin fee (€)"), "widget": "number", "onChange": True,
                             "help": _("Any discount on the company's fee needs management — the save raises the request and waits")},
                            {"name": "fx_rate_egp", "string": _("EGP per EUR (indicative only)"),
                             "widget": "number", "onChange": True,
                             "help": _("Only for the indicative EGP total. The company promises no rate")},
                        ]},
                    ],
                },
            ],
            # Below every tab: the four numbers a salesman reads out loud.
            "footer": {
                "fields": [
                    {"name": "total_eur", "string": _("Total €"), "widget": "number", "highlight": True},
                    {"separator": "thin"},
                    {"name": "deposit_eur", "string": _("Deposit €"), "widget": "number"},
                    {"separator": "thin"},
                    {"name": "balance_eur", "string": _("Balance €"), "widget": "number"},
                    {"separator": "thin"},
                    {"name": "remaining_eur", "string": _("Still owed €"), "widget": "number"},
                ],
                "position": "end",
            },
        },
        "tabs": [
            {
                "title": _("The price, as the customer sees it"),
                "sections": [
                    {
                        "title": "",
                        "groups": [
                            {"title": _("In euros"), "fields": [
                                {"name": "band_label", "string": _("Band used"), "widget": "text",
                                 "readonly": True,
                                 "help": _("Which pricing band the gross price fell into — it fixes the admin fee and the deposit %")},
                                _ro("net_eur", _("Net price (€)"), _("Gross without German VAT")),
                                _ro("vat_reclaimable_eur", _("VAT reclaimed (€)"),
                                    _("Reclaimed on export when the seller's invoice shows VAT")),
                                _ro("shipping_eur", _("Shipping (€)")),
                                _ro("admin_fee_before_discount_eur", _("Admin fee (€)"), _("The band's fee, before any discount")),
                                _ro("admin_fee_eur", _("Admin fee after discount (€)")),
                                _ro("eur1_eur", _("EUR 1 (€)")),
                                _ro("shipping_extra_eur", _("Shipping option (€)")),
                            ]},
                            {"title": _("What the customer pays"), "fields": [
                                _ro("total_eur", _("Total selling price (€)")),
                                _ro("deposit_pct", _("Deposit %"), _("Set by the band, never typed")),
                                _ro("deposit_eur", _("Deposit (€)")),
                                _ro("balance_eur", _("Balance (€)"), _("Total minus deposit — due before the car ships")),
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
                        # Kept apart, and never added to the euro total. These are
                        # collected in Egypt, on arrival, in pounds. Summing them
                        # with the euros would turn a quote into a promise about an
                        # exchange rate nobody made.
                        "title": _("Collected in Egypt, on arrival (EGP)"),
                        "groups": [
                            {"fields": [
                                _ro("port_fee_egp", _("Port fees (EGP)")),
                                _ro("showroom_fee_egp", _("Showroom collection discount (EGP)"),
                                    _("A minus: it comes off the port fee. The port fee line itself does not change")),
                            ]},
                            {"fields": [
                                _ro("egp_due_on_arrival", _("Due on arrival (EGP)")),
                                _ro("total_egp_indicative", _("Indicative total (EGP) — today's rate only"),
                                    _("Euro total × the rate you typed. Indicative, and the document says so")),
                            ]},
                        ],
                    },
                ],
            },
            {
                # The plan's shape, and the client's own habit: an agent answers
                # "do you have a C200?" with five links at five prices. Each row
                # carries its own whole stack, because a cheaper car can land in
                # a band with a BIGGER deposit percentage — which is exactly the
                # comparison the customer is making.
                "title": _("Candidate cars"),
                "sections": [{
                    "title": _("Tick the one the customer chose — its figures become the quotation's"),
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
                             {"name": "options.admin_fee_discount_eur", "widget": "number",
                              "string": _("Fee discount €")},
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
                }],
            },
            {
                "title": _("What the customer has paid"),
                "sections": [{
                    "title": "",
                    "groups": [
                        {"fields": [
                            # A real amount somebody types, not a status somebody
                            # picks: customers pay more than the deposit, and
                            # sometimes the whole car.
                            {"name": "paid_eur", "string": _("Paid so far (€)"), "widget": "number",
                             "onChange": True,
                             "help": _("The real amount received, as the accountant confirmed it. The deal's payment mark follows this once the quotation is accepted")},
                            {"name": "deposit_covered", "string": _("Deposit covered"),
                             "widget": "switch", "readonly": True},
                            {"name": "fully_paid", "string": _("Paid in full"), "widget": "switch",
                             "readonly": True},
                        ]},
                        {"fields": [
                            _ro("remaining_eur", _("Still owed (€)")),
                            _ro("overpaid_eur", _("Overpaid (€)"),
                                _("The customer sent more than the total — do not ask for money already paid")),
                            {"name": "sent_at", "string": _("Sent at"), "widget": "datetime",
                             "readonly": True},
                        ]},
                    ],
                }],
                "footer": {
                    "fields": [
                        {"name": "paid_eur", "string": _("Paid €"), "widget": "number"},
                        {"separator": "thin"},
                        {"name": "remaining_eur", "string": _("Still owed €"), "widget": "number",
                         "highlight": True},
                    ],
                    "position": "end",
                },
            },
            {
                "title": _("The offer, line by line"),
                "sections": [{
                    "title": _("Exactly what the customer was shown — regenerated on every save"),
                    "groups": [{"fullWidth": True, "fields": [
                        {"name": "lines", "string": "", "widget": "list",
                         "required": False, "minRows": 0, "maxRows": 40,
                         "createable": False, "deleteable": False, "selectable": False,
                         "editable": False,
                         "listConfig": {"fields": [
                             {"name": "lines.sequence", "widget": "number", "string": _("#")},
                             {"name": "lines.label", "widget": "text", "string": _("Description")},
                             {"name": "lines.amount", "widget": "number", "string": _("Amount")},
                             {"name": "lines.currency", "widget": "relation", "displayField": "code",
                              "string": _("Currency")},
                         ]},
                         },
                    ]}],
                }],
            },
            {
                "title": _("Notes"),
                "sections": [{
                    "title": "",
                    "groups": [{"fullWidth": True, "fields": [
                        {"name": "notes", "string": _("Notes"), "widget": "textarea", "rows": 5,
                         "help": _("Internal. Nothing here reaches the offer document")},
                    ]}],
                }],
            },
        ],
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
