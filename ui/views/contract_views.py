# -*- coding: utf-8 -*-
"""The contract screens.

The form is arranged the way somebody fills a contract in front of a customer:
who they are as their ID spells it, which car, what they are paying and when.
Most of it arrives prefilled from the deal and the accepted quotation — the
fields exist so a person can correct them, because the name on a national ID
and the name in a WhatsApp profile are regularly not the same string, and the
contract has to match the ID.
"""
from django.utils.translation import gettext as _

_CONTRACT_ACTIONS = [
    {
        "name": "action_generate_contract",
        "string": _("Generate the contract"),
        "icon": "FileText",
        "type": "server",
        "as": "button",
        "variant": "primary",
        "view_type": ["form", "list"],
    },
    {
        "name": "action_mark_signed",
        "string": _("Customer signed"),
        "icon": "PenLine",
        "type": "server",
        "as": "dropdown",
        "view_type": ["form", "list"],
    },
]


car_contract_list_view = {
    "key": "car_import_contract_list_view",
    "name": _("Contracts"),
    "model": "car_import.contract",
    "menu_item": "car_import_menu_contracts",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions": _CONTRACT_ACTIONS},
        "tree": {"fields": [
            {"name": "deal", "widget": "relation", "displayField": "name",
             "string": _("Deal"), "width": "170"},
            {"name": "customer_name", "widget": "text", "string": _("Customer"), "width": "200"},
            {"name": "car_model", "widget": "text", "string": _("Car"), "width": "190"},
            {"name": "contract_date", "widget": "date", "string": _("Date"), "width": "130"},
            {"name": "total_eur", "widget": "number", "string": _("Total €"), "width": "130"},
            {"name": "down_payment_eur", "widget": "number", "string": _("At signing €"),
             "width": "140"},
            {"name": "state", "widget": "status", "string": _("Status"), "width": "130"},
            {"name": "document", "widget": "file", "string": _("Document"), "width": "180"},
        ]},
    },
}


car_contract_form_view = {
    "key": "car_import_contract_form_view",
    "name": _("Contract"),
    "model": "car_import.contract",
    "menu_item": "car_import_menu_contracts",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions_list": [], "actions": _CONTRACT_ACTIONS},
        "sheet": {
            "ribbon": {
                "field_text": "state",
                "color": {
                    "success": {"field": "state", "operator": "eq", "value": "signed"},
                    "danger": {"field": "state", "operator": "eq", "value": "cancelled"},
                },
                "invisible": {"field": "state", "operator": "eq", "value": "draft"},
            },
            "sections": [
                {
                    "title": _("The deal"),
                    "groups": [
                        {"fields": [
                            {"name": "state", "string": _("Status"), "widget": "select",
                             "invisible": True},
                            {"name": "deal", "string": _("Deal"), "widget": "relation",
                             "displayField": "name", "required": True, "multiSelect": False},
                            {"name": "quote", "string": _("Quotation"), "widget": "relation",
                             "displayField": "name", "multiSelect": False},
                        ]},
                        {"fields": [
                            {"name": "template", "string": _("Template"), "widget": "relation",
                             "displayField": "name", "multiSelect": False},
                            {"name": "contract_date", "string": _("Contract date"),
                             "widget": "date"},
                        ]},
                    ],
                },
                {
                    # As the ID spells it. The contract has to match the document
                    # the customer will present at customs, not the name they use
                    # on WhatsApp — and those differ more often than not.
                    "title": _("The customer, exactly as their ID reads"),
                    "groups": [
                        {"fields": [
                            {"name": "customer_name", "string": _("Name as on the ID"),
                             "widget": "text", "required": True},
                            {"name": "customer_national_id", "string": _("National ID number"),
                             "widget": "text", "required": True},
                            {"name": "shipping_name", "string": _("Ships in the name of"),
                             "widget": "text"},
                        ]},
                        {"fields": [
                            {"name": "customer_address", "string": _("Address"), "widget": "text"},
                            {"name": "customer_email", "string": _("Email"), "widget": "text"},
                        ]},
                    ],
                },
                {
                    "title": _("The car"),
                    "groups": [
                        {"fields": [
                            {"name": "car_model", "string": _("Model"), "widget": "text",
                             "required": True},
                            {"name": "car_trim", "string": _("Trim"), "widget": "text"},
                        ]},
                        {"fields": [
                            {"name": "car_model_year", "string": _("Model year"), "widget": "text"},
                            {"name": "car_configuration", "string": _("Configuration number"),
                             "widget": "text"},
                        ]},
                    ],
                },
                {
                    "title": _("The money"),
                    "groups": [
                        {"fields": [
                            {"name": "total_eur", "string": _("Total contract value (€)"),
                             "widget": "number", "required": True},
                            {"name": "deposit_pct", "string": _("Deposit %"), "widget": "number"},
                        ]},
                        {"fields": [
                            {"name": "down_payment_eur", "string": _("Received at signing (€)"),
                             "widget": "number"},
                            {"name": "bank_transfer_eur", "string": _("Bank transfer (€)"),
                             "widget": "number"},
                            {"name": "cash_on_bl_eur", "string": _("Cash on bill of lading (€)"),
                             "widget": "number"},
                        ]},
                    ],
                },
                {
                    # Annex 1. Three dates and three amounts, and clause 6 gives
                    # the company a 7% monthly late charge against them — so a
                    # wrong date here is not a typo, it is money.
                    "title": _("Annex 1 — the payment schedule"),
                    "groups": [
                        {"fields": [
                            {"name": "instalment_1_date", "string": _("Payment 1 — date"),
                             "widget": "date"},
                            {"name": "instalment_2_date", "string": _("Payment 2 — date"),
                             "widget": "date"},
                            {"name": "instalment_3_date", "string": _("Payment 3 — date"),
                             "widget": "date"},
                        ]},
                        {"fields": [
                            {"name": "instalment_1_amount", "string": _("Payment 1 — amount"),
                             "widget": "number"},
                            {"name": "instalment_2_amount", "string": _("Payment 2 — amount"),
                             "widget": "number"},
                            {"name": "instalment_3_amount", "string": _("Payment 3 — amount"),
                             "widget": "number"},
                        ]},
                    ],
                },
                {
                    "title": _("The document"),
                    "groups": [
                        {"fields": [
                            {"name": "document", "string": _("Generated contract"),
                             "widget": "file", "readonly": True},
                            {"name": "generated_at", "string": _("Generated at"),
                             "widget": "datetime", "readonly": True},
                        ]},
                        {"fields": [
                            {"name": "generated_by", "string": _("Generated by"),
                             "widget": "relation", "displayField": "name", "readonly": True,
                             "multiSelect": False},
                            {"name": "signed_on", "string": _("Signed on"), "widget": "date"},
                        ]},
                    ],
                },
                {
                    "title": _("Notes"),
                    "groups": [{"fullWidth": True, "fields": [
                        {"name": "notes", "string": _("Notes"), "widget": "textarea"},
                    ]}],
                },
            ],
        },
    },
}


car_contract_template_list_view = {
    "key": "car_import_contract_template_list_view",
    "name": _("Contract templates"),
    "model": "car_import.contracttemplate",
    "menu_item": "car_import_menu_contract_templates",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {"tree": {"fields": [
        {"name": "code", "widget": "text", "string": _("Code"), "width": "180"},
        {"name": "name", "widget": "text", "string": _("Name"), "width": "260"},
        {"name": "program", "widget": "select", "string": _("Programme"), "width": "160"},
        {"name": "is_fillable", "widget": "switch", "string": _("Can be filled"), "width": "140"},
        {"name": "docx", "widget": "file", "string": _("File"), "width": "200"},
        {"name": "source_filename", "widget": "text", "string": _("From"), "width": "240"},
    ]}},
}


car_contract_template_form_view = {
    "key": "car_import_contract_template_form_view",
    "name": _("Contract template"),
    "model": "car_import.contracttemplate",
    "menu_item": "car_import_menu_contract_templates",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions_list": [], "actions": []},
        "sheet": {"sections": [
            {"title": _("The template"), "groups": [
                {"fields": [
                    {"name": "code", "string": _("Code"), "widget": "text", "required": True},
                    {"name": "name", "string": _("Name"), "widget": "text", "required": True},
                    {"name": "program", "string": _("Programme"), "widget": "select"},
                ]},
                {"fields": [
                    {"name": "docx", "string": _("Template file"), "widget": "file"},
                    {"name": "is_fillable", "string": _("Can be filled"), "widget": "switch"},
                    {"name": "source_filename", "string": _("Original filename"), "widget": "text",
                     "readonly": True},
                ]},
            ]},
            {"title": _("Fields this template asks for"), "groups": [
                {"fullWidth": True, "fields": [
                    # Read-only: the list comes from the file itself, and editing
                    # it here would describe a template that does not exist.
                    {"name": "tokens", "string": _("Fields"), "widget": "text",
                     "readonly": True},
                    {"name": "notes", "string": _("Notes"), "widget": "textarea"},
                ]},
            ]},
        ]},
    },
}
