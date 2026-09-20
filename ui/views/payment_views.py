# -*- coding: utf-8 -*-
"""The accountant's screen, and the proforma invoices behind it.

The receipt form is built around one decision. The assistant has already read
the screenshot and filled the row in; what is left for a person is to look at
the picture, look at the bank statement, and press **Accept — money received**.
So there is one button. Rejecting is real but rare, and lives in the actions
menu where nobody presses it by reflex; after a decision there are no buttons
at all.

No status pills in either header — the pills win the 30px row and push the
button off the screen (see `quote_views.py`). The state is a ribbon.
"""
from django.utils.translation import gettext as _

_PENDING_ONLY = {"field": "state", "operator": "ne", "value": "pending"}

_RECEIPT_ACTIONS = [
    {
        "name": "action_accept",
        "string": _("Accept — money received"),
        "icon": "BadgeCheck",
        "type": "server",
        "as": "button",
        "variant": "primary",
        "view_type": ["form", "list"],
        "invisible": _PENDING_ONLY,
        "confirm_required": True,
        "confirm_message": _("Confirm that this amount reached the company's account? The customer is "
                             "told, the deal is credited, and the contract is issued and sent."),
    },
    {
        "name": "action_reject",
        "string": _("Reject this receipt"),
        "icon": "Ban",
        "type": "server",
        "as": "dropdown",
        "view_type": ["form", "list"],
        "invisible": _PENDING_ONLY,
        "confirm_required": True,
    },
]

receipt_list_view = {
    "key": "car_import_receipt_list_view",
    "name": _("Payment receipts"),
    "model": "car_import.paymentreceipt",
    "menu_item": "car_import_menu_receipts",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions": _RECEIPT_ACTIONS},
        "tree": {
            "fields": [
                {"name": "name", "widget": "text", "string": _("Reference"), "width": "120"},
                {"name": "state", "widget": "status", "string": _("Status"), "width": "190"},
                {"name": "partner", "widget": "relation", "displayField": "name",
                 "string": _("Customer"), "width": "190"},
                {"name": "amount", "widget": "number", "string": _("On the screenshot"), "width": "140"},
                {"name": "currency", "widget": "relation", "displayField": "code",
                 "string": _("Currency"), "width": "90"},
                {"name": "amount_credited", "widget": "number", "string": _("To credit €"), "width": "130"},
                {"name": "transfer_date", "widget": "date", "string": _("Transfer date"), "width": "120"},
                {"name": "proforma", "widget": "relation", "displayField": "name",
                 "string": _("Proforma invoice"), "width": "140"},
                {"name": "ai_confidence", "widget": "select", "string": _("How clear it was"), "width": "140"},
                {"name": "reviewed_by", "widget": "relation", "displayField": "name",
                 "string": _("Confirmed by"), "width": "150"},
            ],
        },
    },
}

receipt_form_view = {
    "key": "car_import_receipt_form_view",
    "name": _("Payment receipt"),
    "model": "car_import.paymentreceipt",
    "menu_item": "car_import_menu_receipts",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions_list": [], "actions": _RECEIPT_ACTIONS},
        "sheet": {
            "ribbon": {
                "field_text": "state",
                "color": {
                    "success": {"field": "state", "operator": "eq", "value": "accepted"},
                    "danger": {"field": "state", "operator": "eq", "value": "rejected"},
                    "warning": {"field": "state", "operator": "eq", "value": "pending"},
                },
            },
            "sections": [
                {
                    "title": _("The transfer"),
                    "groups": [
                        {"fields": [
                            {"name": "state", "string": _("Status"), "widget": "select", "invisible": True},
                            {"name": "name", "string": _("Reference"), "widget": "text", "readonly": True},
                            {"name": "partner", "string": _("Customer"), "widget": "relation",
                             "displayField": "name", "multiSelect": False, "required": True},
                            {"name": "screenshot", "string": _("Transfer screenshot"), "widget": "files",
                             "multiSelect": False, "accept": "image/*,application/pdf",
                             "help": _("The picture the customer sent. Compare it with the bank statement, not with this form")},
                            {"name": "ai_remarks", "string": _("What to check"), "widget": "textarea",
                             "readonly": True,
                             "help": _("Written by the assistant: anything that did not match the invoice, the customer or the calendar")},
                        ]},
                        {"fields": [
                            {"name": "amount", "string": _("Amount on the screenshot"), "widget": "number",
                             "help": _("As the assistant read it. Correct it if the picture says otherwise")},
                            {"name": "currency", "string": _("Its currency"), "widget": "relation",
                             "displayField": "code", "multiSelect": False},
                            {"name": "transfer_date", "string": _("Transfer date"), "widget": "date"},
                            {"name": "sender_name", "string": _("Sent by"), "widget": "text"},
                            {"name": "bank_name", "string": _("Bank"), "widget": "text"},
                            {"name": "bank_reference", "string": _("Transfer reference"), "widget": "text",
                             "help": _("The same reference on two receipts usually means the same transfer sent twice")},
                            {"name": "ai_confidence", "string": _("How clear it was"), "widget": "select",
                             "readonly": True},
                        ]},
                    ],
                },
                {
                    "title": _("What it pays for"),
                    "groups": [
                        {"fields": [
                            {"name": "proforma", "string": _("Proforma invoice"), "widget": "relation",
                             "displayField": "name", "multiSelect": False},
                            {"name": "quote", "string": _("Quotation"), "widget": "relation",
                             "displayField": "name", "multiSelect": False,
                             "help": _("Accepting adds the credited amount to this quotation's paid total, and the deal follows it")},
                            {"name": "deal", "string": _("Deal"), "widget": "relation",
                             "displayField": "name", "multiSelect": False},
                        ]},
                        {"fields": [
                            {"name": "reviewed_by", "string": _("Confirmed by"), "widget": "relation",
                             "displayField": "name", "multiSelect": False, "readonly": True},
                            {"name": "reviewed_at", "string": _("Confirmed at"), "widget": "datetime",
                             "readonly": True},
                            {"name": "contract_outcome", "string": _("What happened to the contract"),
                             "widget": "text", "readonly": True},
                            {"name": "reject_reason", "string": _("Why it was rejected"), "widget": "text",
                             "help": _("Fill this before rejecting — the agent reads it in the chat")},
                            {"name": "notes", "string": _("Notes"), "widget": "textarea"},
                        ]},
                    ],
                },
            ],
            "footer": {
                "fields": [
                    {"name": "amount_credited", "string": _("Amount to credit (EUR)"), "widget": "number",
                     "help": _("The number that reaches the deal when you accept. Filled for a euro "
                               "transfer; type the euro value yourself for any other currency"),
                     "highlight": True},
                ],
                "position": "end",
            },
        },
    },
}

receipt_search_view = {
    "key": "car_import_receipt_search_view",
    "name": _("Payment receipts search"),
    "model": "car_import.paymentreceipt",
    "menu_item": "car_import_menu_receipts",
    "view_type": "search",
    "priority": 20,
    "module": "car_import",
    "body": {
        "search": {
            "search_fields": [
                {"name": ["name"], "string": _("Reference"), "widget": "text"},
                {"name": ["partner__name"], "string": _("Customer"), "widget": "text"},
                {"name": ["bank_reference"], "string": _("Transfer reference"), "widget": "text"},
                {"name": ["sender_name"], "string": _("Sent by"), "widget": "text"},
            ],
            "filters": [
                {"name": "pending", "string": _("Waiting for the accountant"),
                 "filter": {"field": "state", "operator": "eq", "value": "pending"}},
                {"name": "accepted", "string": _("Accepted"),
                 "filter": {"field": "state", "operator": "eq", "value": "accepted"}},
                {"name": "rejected", "string": _("Rejected"),
                 "filter": {"field": "state", "operator": "eq", "value": "rejected"}},
                {"name": "by_ai", "string": _("Read by the assistant"),
                 "filter": {"field": "source", "operator": "eq", "value": "ai"}},
            ],
            "group_by": [
                {"name": "state", "string": _("Status")},
                {"name": "partner", "string": _("Customer")},
            ],
            "order_by": [
                {"name": "id", "string": _("Newest"), "direction": "desc"},
            ],
        },
    },
}


# ── proforma invoices ────────────────────────────────────────────────────────
_PROFORMA_ACTIONS = [
    {
        "name": "action_open_document",
        "string": _("Open the invoice"),
        "icon": "FileText",
        "type": "server",
        "as": "button",
        "variant": "primary",
        "view_type": ["form"],
    },
    {
        "name": "action_resend",
        "string": _("Send it to the customer again"),
        "icon": "MessageCircle",
        "type": "server",
        "as": "dropdown",
        "view_type": ["form", "list"],
        "confirm_required": True,
    },
    {
        "name": "action_cancel",
        "string": _("Cancel this invoice"),
        "icon": "Ban",
        "type": "server",
        "as": "dropdown",
        "view_type": ["form", "list"],
        "confirm_required": True,
        "invisible": {"field": "state", "operator": "in", "value": ["cancelled", "paid"]},
    },
]

proforma_list_view = {
    "key": "car_import_proforma_list_view",
    "name": _("Proforma invoices"),
    "model": "car_import.proformainvoice",
    "menu_item": "car_import_menu_proformas",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions": _PROFORMA_ACTIONS},
        "tree": {
            "fields": [
                {"name": "name", "widget": "text", "string": _("Reference"), "width": "120"},
                {"name": "invoice_date", "widget": "date", "string": _("Date"), "width": "120"},
                {"name": "partner", "widget": "relation", "displayField": "name",
                 "string": _("Customer"), "width": "190"},
                {"name": "car_label", "widget": "text", "string": _("Car"), "width": "220"},
                {"name": "total_amount", "widget": "number", "string": _("Total €"), "width": "130"},
                {"name": "amount_due", "widget": "number", "string": _("Due now €"), "width": "130"},
                {"name": "paid_amount", "widget": "number", "string": _("Confirmed €"), "width": "130"},
                {"name": "state", "widget": "status", "string": _("Status"), "width": "130"},
                {"name": "issued_by_ai", "widget": "checkbox", "string": _("By the assistant"), "width": "130"},
            ],
        },
    },
}

proforma_form_view = {
    "key": "car_import_proforma_form_view",
    "name": _("Proforma invoice"),
    "model": "car_import.proformainvoice",
    "menu_item": "car_import_menu_proformas",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions_list": [], "actions": _PROFORMA_ACTIONS},
        "sheet": {
            "ribbon": {
                "field_text": "state",
                "color": {
                    "success": {"field": "state", "operator": "eq", "value": "paid"},
                    "warning": {"field": "state", "operator": "eq", "value": "partly_paid"},
                    "danger": {"field": "state", "operator": "eq", "value": "cancelled"},
                },
            },
            "sections": [
                {
                    "title": _("The invoice"),
                    "groups": [
                        {"fields": [
                            {"name": "state", "string": _("Status"), "widget": "select", "invisible": True},
                            {"name": "name", "string": _("Reference"), "widget": "text", "readonly": True},
                            {"name": "partner", "string": _("Customer"), "widget": "relation",
                             "displayField": "name", "multiSelect": False, "required": True},
                            {"name": "quote", "string": _("Quotation"), "widget": "relation",
                             "displayField": "name", "multiSelect": False},
                            {"name": "deal", "string": _("Deal"), "widget": "relation",
                             "displayField": "name", "multiSelect": False},
                            {"name": "car_label", "string": _("Car"), "widget": "text"},
                        ]},
                        {"fields": [
                            {"name": "invoice_date", "string": _("Date"), "widget": "date"},
                            {"name": "valid_until", "string": _("Valid until"), "widget": "date",
                             "help": _("Short on purpose: the German seller can sell the car meanwhile")},
                            {"name": "currency", "string": _("Currency"), "widget": "relation",
                             "displayField": "code", "multiSelect": False},
                            {"name": "deposit_pct", "string": _("Deposit %"), "widget": "number"},
                            {"name": "issued_by_ai", "string": _("Issued by the assistant"), "widget": "switch",
                             "readonly": True},
                            {"name": "sent_at", "string": _("Sent at"), "widget": "datetime", "readonly": True},
                        ]},
                    ],
                },
                {
                    "title": _("Where the customer was told to pay"),
                    "groups": [
                        {"fields": [
                            {"name": "bank_details_text", "string": _("Bank details as sent"),
                             "widget": "textarea",
                             "help": _("Frozen when the invoice was issued. Changing the company's account later does not rewrite this")},
                            {"name": "notes", "string": _("Notes"), "widget": "textarea"},
                        ]},
                    ],
                },
            ],
            "footer": {
                "fields": [
                    {"name": "total_amount", "string": _("Total selling price"), "widget": "number"},
                    {"name": "amount_due", "string": _("Due now"), "widget": "number",
                     "help": _("The deposit this invoice asks for")},
                    {"name": "paid_amount", "string": _("Confirmed so far"), "widget": "number",
                     "readonly": True,
                     "help": _("The sum of the receipts the accountant accepted against this invoice")},
                ],
                "position": "end",
            },
        },
    },
}
