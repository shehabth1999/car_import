# -*- coding: utf-8 -*-
"""The contract screens.

The form is arranged the way somebody fills a contract in front of a customer:
the deal on top, then tabs — who they are as their ID spells it, which car,
what they are paying and when, the document itself. Most of it arrives
prefilled the moment the deal is picked (`onChange`), because the name on a
national ID and the name in a WhatsApp profile are regularly not the same
string, and the contract has to match the ID. The money adds itself up in the
footer and complains while you type, not six weeks later.
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
        "name": "action_send_contract",
        "string": _("Send to the customer"),
        "icon": "Send",
        "type": "server",
        "as": "button",
        "variant": "secondary",
        "view_type": ["form"],
        "confirm_required": True,
    },
    {
        "name": "action_print_annex2",
        "string": _("Annex 2 — specification"),
        "icon": "ClipboardList",
        "type": "server",
        "as": "dropdown",
        "view_type": ["form"],
    },
    {
        "name": "action_void",
        "string": _("Void"),
        "icon": "Ban",
        "type": "server",
        "as": "dropdown",
        "variant": "danger",
        "view_type": ["form", "list"],
        "confirm_required": True,
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
                             "displayField": "name", "required": True, "multiSelect": False,
                             "onChange": True,
                             "help": _("Picking the deal fills the customer, the car, the accepted quotation's money, the issuer and the template")},
                            {"name": "quote", "string": _("Quotation"), "widget": "relation",
                             "displayField": "name", "multiSelect": False,
                             "help": _("The accepted offer the money came from. Only an offer — the deal's own contract figures win")},
                        ]},
                        {"fields": [
                            {"name": "template", "string": _("Template"), "widget": "relation",
                             "displayField": "name", "multiSelect": False,
                             "help": _("The lawyer's .docx for this programme. Generation refuses when a required blank has no value")},
                            {"name": "contract_date", "string": _("Contract date"),
                             "widget": "date",
                             "help": _("Printed as day / month / year on page one, and decides which signatory was authorised")},
                            {"name": "issuer", "string": _("Issued by"), "widget": "relation",
                             "displayField": "name", "multiSelect": False},
                            {"name": "signatory", "string": _("Signed for the company by"),
                             "widget": "relation", "displayField": "name", "multiSelect": False,
                             "help": _("Whoever is authorised on the contract date. Their name and ID replace the literal ones in the template")},
                        ]},
                    ],
                },
            ],
            "footer": {
                "fields": [
                    {"name": "total_eur", "string": _("Total €"), "widget": "number", "highlight": True},
                    {"separator": "thin"},
                    {"name": "down_payment_eur", "string": _("At signing €"), "widget": "number"},
                    {"separator": "thin"},
                    {"name": "bank_transfer_eur", "string": _("Transfer €"), "widget": "number"},
                    {"separator": "thin"},
                    {"name": "cash_on_bl_eur", "string": _("On B/L €"), "widget": "number"},
                ],
                "position": "end",
            },
        },
        "tabs": [
            {
                "title": _("The customer"),
                "sections": [{
                    "title": _("Exactly as their ID reads"),
                    "groups": [
                        {"fields": [
                            {"name": "customer_name", "string": _("Name as on the ID"),
                             "widget": "text", "required": True,
                             "help": _("Not the WhatsApp name. The contract is void against a name that is not on the ID")},
                            {"name": "customer_national_id", "string": _("National ID number"),
                             "widget": "text", "required": True,
                             "help": _("14 digits. Filed against the deal's paperwork too")},
                            {"name": "shipping_name", "string": _("Ships in the name of"),
                             "widget": "text",
                             "help": _("Usually the customer. On a provided initiative it is the initiative holder — the customs papers carry this name")},
                        ]},
                        {"fields": [
                            {"name": "customer_address", "string": _("Address"), "widget": "text",
                             "help": _("As on the ID — clause 10 sends formal notices there")},
                            {"name": "customer_email", "string": _("Email"), "widget": "email",
                             "help": _("Formal correspondence goes here as well as by registered post")},
                        ]},
                    ],
                }],
            },
            {
                "title": _("The car"),
                "sections": [{
                    "title": _("As the annex prints it"),
                    "groups": [
                        {"fields": [
                            {"name": "car_model", "string": _("Model"), "widget": "text",
                             "required": True},
                            {"name": "car_trim", "string": _("Trim"), "widget": "text"},
                        ]},
                        {"fields": [
                            {"name": "car_model_year", "string": _("Model year"), "widget": "text",
                             "help": _("Replaces the literal year the lawyer typed in the template")},
                            {"name": "car_configuration", "string": _("Configuration number"),
                             "widget": "text",
                             "help": _("The manufacturer's build code — Annex 2 settles disputes about options against it")},
                        ]},
                    ],
                }],
            },
            {
                "title": _("The money"),
                "sections": [
                    {
                        "title": _("Article 4 — the price and how it is paid"),
                        "groups": [
                            {"fields": [
                                {"name": "currency", "string": _("Currency"), "widget": "relation", "displayField": "code", "multiSelect": False},
                                {"name": "total_eur", "string": _("Total contract value (€)"),
                                 "widget": "number", "required": True, "onChange": True,
                                 "help": _("The three payments below must add up to this — the form says so as you type, and the save refuses otherwise")},
                                {"name": "deposit_pct", "string": _("Deposit %"), "widget": "number",
                                 "help": _("From the quotation's band")},
                            ]},
                            {"fields": [
                                {"name": "down_payment_eur", "string": _("Received at signing (€)"),
                                 "widget": "number", "onChange": True},
                                {"name": "bank_transfer_eur", "string": _("Bank transfer (€)"),
                                 "widget": "number", "onChange": True},
                                {"name": "cash_on_bl_eur", "string": _("Cash on bill of lading (€)"),
                                 "widget": "number", "onChange": True,
                                 "help": _("Due when the bill of lading is issued — before the ship sails")},
                            ]},
                        ],
                    },
                    {
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
                ],
            },
            {
                "title": _("The document"),
                "sections": [{
                    "title": "",
                    "groups": [
                        {"title": _("Generated"), "fields": [
                            {"name": "document", "string": _("Generated contract"),
                             "widget": "file", "readonly": True,
                             "help": _("Kept as generated, never rebuilt from today's data — it is what the customer holds")},
                            {"name": "generated_at", "string": _("Generated at"),
                             "widget": "datetime", "readonly": True},
                            {"name": "generated_by", "string": _("Generated by"),
                             "widget": "relation", "displayField": "name", "readonly": True,
                             "multiSelect": False},
                            {"name": "sent_at", "string": _("Sent at"), "widget": "datetime",
                             "readonly": True},
                        ]},
                        {"title": _("Signed"), "fields": [
                            {"name": "signed_on", "string": _("Signed on"), "widget": "date"},
                            {"name": "signed_document", "string": _("Signed copy"),
                             "widget": "file",
                             "help": _("The copy that came back with a signature. A generated file proves what we offered; only this proves what they agreed to")},
                            {"name": "void_reason", "string": _("Why it was voided"),
                             "widget": "text",
                             "invisible": {"field": "state", "operator": "ne", "value": "cancelled"}},
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
                    {"name": "program", "string": _("Programme"), "widget": "select",
                     "help": _("Which deals it is offered to. 'Any programme' is the fallback")},
                ]},
                {"fields": [
                    {"name": "docx", "string": _("Template file"), "widget": "file",
                     "help": _("The lawyer's Word file, with its blanks turned into named fields by import_contract_templates")},
                    {"name": "is_fillable", "string": _("Can be filled"), "widget": "switch",
                     "help": _("Off for the documents the lawyer has not delivered in a fillable form yet")},
                    {"name": "source_filename", "string": _("Original filename"), "widget": "text",
                     "readonly": True},
                ]},
            ]},
            {"title": _("Fields this template asks for"), "groups": [
                {"fullWidth": True, "fields": [
                    {"name": "tokens", "string": _("Fields"), "widget": "text",
                     "readonly": True},
                    {"name": "notes", "string": _("Notes"), "widget": "textarea"},
                ]},
            ]},
        ]},
    },
}


car_contract_issuer_list_view = {
    "key": "car_import_contract_issuer_list_view",
    "name": _("Contract issuers"),
    "model": "car_import.contractissuer",
    "menu_item": "car_import_menu_contract_issuers",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {"tree": {"fields": [
        {"name": "code", "widget": "text", "string": _("Code"), "width": "110"},
        {"name": "name", "widget": "text", "string": _("Company"), "width": "320"},
        {"name": "commercial_register", "widget": "text", "string": _("Register"), "width": "140"},
        {"name": "tax_card", "widget": "text", "string": _("Tax card"), "width": "150"},
        {"name": "legal_rep_name", "widget": "text", "string": _("Legal representative"),
         "width": "230"},
        {"name": "is_default", "widget": "switch", "string": _("Default"), "width": "110"},
    ]}},
}


car_contract_issuer_form_view = {
    "key": "car_import_contract_issuer_form_view",
    "name": _("Contract issuer"),
    "model": "car_import.contractissuer",
    "menu_item": "car_import_menu_contract_issuers",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions_list": [], "actions": []},
        "sheet": {"sections": [
            {"title": _("As the contract prints it"), "groups": [
                {"fields": [
                    {"name": "code", "string": _("Code"), "widget": "text", "required": True},
                    {"name": "name", "string": _("Company name"), "widget": "text",
                     "required": True},
                    {"name": "name_en", "string": _("Company name (English)"), "widget": "text"},
                    {"name": "represents", "string": _("Marketing agent for"), "widget": "text",
                     "help": _("K&T contracts as marketing agent for the German company — the clause names it")},
                ]},
                {"fields": [
                    {"name": "commercial_register", "string": _("Commercial register"),
                     "widget": "text"},
                    {"name": "chamber", "string": _("Chamber of commerce"), "widget": "text"},
                    {"name": "tax_card", "string": _("Tax card"), "widget": "text"},
                    {"name": "is_default", "string": _("Use by default"), "widget": "switch"},
                ]},
            ]},
            {"title": _("Who represents it"), "groups": [
                {"fields": [
                    {"name": "legal_rep_name", "string": _("Legal representative"),
                     "widget": "text"},
                    {"name": "legal_rep_national_id", "string": _("Their national ID"),
                     "widget": "text"},
                ]},
                {"fields": [
                    {"name": "email", "string": _("Notice email (clause 10)"), "widget": "email"},
                    {"name": "address", "string": _("Address"), "widget": "text"},
                ]},
            ]},
            {
                "title": _("Authorised signatories"),
                "groups": [{"fullWidth": True, "fields": [
                    {"name": "signatories", "string": "", "widget": "list",
                     "required": False, "minRows": 0, "maxRows": 20,
                     "createable": True, "deleteable": True, "selectable": False,
                     "editable": True,
                     "help": _("Dated on purpose: 'who could sign in March?' gets asked once, by a lawyer, about a disputed contract"),
                     "listConfig": {"fields": [
                         {"name": "signatories.name", "widget": "text", "string": _("Name"),
                          "required": True},
                         {"name": "signatories.national_id", "widget": "text",
                          "string": _("National ID")},
                         {"name": "signatories.title", "widget": "text", "string": _("Capacity")},
                         {"name": "signatories.authorised_from", "widget": "date",
                          "string": _("From")},
                         {"name": "signatories.authorised_to", "widget": "date",
                          "string": _("Until")},
                         {"name": "signatories.is_default", "widget": "switch",
                          "string": _("Signs by default")},
                     ]}},
                ]}],
            },
        ]},
    },
}
