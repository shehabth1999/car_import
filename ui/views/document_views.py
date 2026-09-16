# -*- coding: utf-8 -*-
"""Screens for the paperwork: the checklist per programme, and per deal."""
from django.utils.translation import gettext as _

car_import_doc_requirement_list_view = {
    "key": "car_import_doc_requirement_list_view",
    "name": "Document requirements",
    "model": "car_import.documentrequirement",
    "menu_item": "car_import_menu_doc_requirements",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {
        "tree": {
            "fields": [
                {"name": "sequence", "string": _("#"), "widget": "number", "width": "60"},
                {"name": "program", "string": _("Programme"), "widget": "relation",
                 "displayField": "name", "width": "180"},
                {"name": "code", "string": _("Code"), "widget": "text", "width": "190"},
                {"name": "name", "string": _("Document"), "widget": "text", "width": "260"},
                {"name": "mandatory", "string": _("Mandatory"), "widget": "switch", "width": "110"},
                {"name": "expires", "string": _("Expires"), "widget": "switch", "width": "100"},
                {"name": "is_sensitive", "string": _("Confidential"), "widget": "switch", "width": "120"},
            ],
        },
    },
}

car_import_doc_requirement_form_view = {
    "key": "car_import_doc_requirement_form_view",
    "name": "Document requirement",
    "model": "car_import.documentrequirement",
    "menu_item": "car_import_menu_doc_requirements",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions_list": [], "actions": []},
        "sheet": {
            "sections": [
                {
                    "title": _("The document"),
                    "groups": [
                        {"fields": [
                            {"name": "code", "string": _("Code"), "widget": "text", "required": True},
                            {"name": "name", "string": _("Name"), "widget": "text", "required": True},
                            {"name": "name_en", "string": _("Name (English)"), "widget": "text"},
                            {"name": "sequence", "string": _("Sequence"), "widget": "number"},
                        ]},
                        {"fields": [
                            {"name": "program", "string": _("Programme"), "widget": "relation",
                             "displayField": "name", "multiSelect": False},
                            {"name": "mandatory", "string": _("Mandatory"), "widget": "switch"},
                            {"name": "expires", "string": _("Has an expiry date"), "widget": "switch"},
                            {"name": "is_sensitive", "string": _("Confidential"), "widget": "switch"},
                            {"name": "ask_at_stage", "string": _("Ask for it at"), "widget": "relation",
                             "displayField": "name", "multiSelect": False},
                        ]},
                    ],
                },
                {
                    "title": _("Validity"),
                    "groups": [
                        {"fields": [
                            {"name": "effective_from", "string": _("In force from"), "widget": "date"},
                            {"name": "effective_to", "string": _("In force until"), "widget": "date"},
                            {"name": "source_note", "string": _("Where this came from"), "widget": "text"},
                        ]},
                        {"fields": [{"name": "notes", "string": _("Notes"), "widget": "textarea"}]},
                    ],
                },
            ],
        },
    },
}

car_import_deal_document_list_view = {
    "key": "car_import_deal_document_list_view",
    "name": "Deal documents",
    "model": "car_import.dealdocument",
    "menu_item": "car_import_menu_deal_documents",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {
        "tree": {
            "fields": [
                {"name": "deal", "string": _("Deal"), "widget": "relation",
                 "displayField": "name", "width": "150"},
                {"name": "name", "string": _("Document"), "widget": "text", "width": "260"},
                {"name": "state", "string": _("State"), "widget": "status", "width": "150"},
                {"name": "file", "string": _("File"), "widget": "attachment", "width": "120"},
                {"name": "received_at", "string": _("Received"), "widget": "datetime", "width": "150"},
                {"name": "verified_by", "string": _("Checked by"), "widget": "relation",
                 "displayField": "name", "width": "150"},
                {"name": "expires_on", "string": _("Expires"), "widget": "date", "width": "120"},
            ],
        },
    },
}

car_import_deal_document_form_view = {
    "key": "car_import_deal_document_form_view",
    "name": "Deal document",
    "model": "car_import.dealdocument",
    "menu_item": "car_import_menu_deal_documents",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions_list": [], "actions": []},
        "sheet": {
            "sections": [
                {
                    "title": _("The document"),
                    "groups": [
                        {"fields": [
                            {"name": "deal", "string": _("Deal"), "widget": "relation",
                             "displayField": "name", "multiSelect": False, "required": True},
                            {"name": "requirement", "string": _("Requirement"), "widget": "relation",
                             "displayField": "name", "multiSelect": False},
                            {"name": "name", "string": _("Document"), "widget": "text", "required": True},
                            {"name": "state", "string": _("State"), "widget": "select"},
                        ]},
                        {"fields": [
                            {"name": "file", "string": _("File"), "widget": "attachment"},
                            {"name": "received_at", "string": _("Received"), "widget": "datetime"},
                            {"name": "expires_on", "string": _("Expires on"), "widget": "date"},
                        ]},
                    ],
                },
                {
                    "title": _("The check"),
                    "groups": [
                        {"fields": [
                            {"name": "verified_by", "string": _("Checked by"), "widget": "relation",
                             "displayField": "name", "multiSelect": False, "readonly": True},
                            {"name": "verified_at", "string": _("Checked on"),
                             "widget": "datetime", "readonly": True},
                        ]},
                        {"fields": [
                            # Only meaningful when the state is 'rejected', and the
                            # customer is owed this sentence rather than a shrug.
                            {"name": "rejection_reason", "string": _("Why it was rejected"),
                             "widget": "text"},
                            {"name": "note", "string": _("Note"), "widget": "textarea"},
                        ]},
                    ],
                },
            ],
        },
    },
}

car_import_deal_document_search_view = {
    "key": "car_import_deal_document_search_view",
    "name": "Deal document search",
    "model": "car_import.dealdocument",
    "menu_item": "car_import_menu_deal_documents",
    "view_type": "search",
    "priority": 20,
    "module": "car_import",
    "body": {
        "search": {
            "search_fields": ["name", "deal.name"],
            "filters": [
                {"name": "outstanding", "string": _("Still missing"),
                 "filter": {"field": "state", "operator": "eq", "value": "missing"}},
                {"name": "to_check", "string": _("Waiting to be checked"),
                 "filter": {"field": "state", "operator": "eq", "value": "uploaded"}},
                {"name": "rejected", "string": _("Rejected"),
                 "filter": {"field": "state", "operator": "eq", "value": "rejected"}},
                {"name": "expired", "string": _("Expired"),
                 "filter": {"field": "state", "operator": "eq", "value": "expired"}},
            ],
            "group_by": [
                {"name": "state", "string": _("State")},
                {"name": "deal", "string": _("Deal")},
            ],
        },
    },
}

car_import_initiative_list_view = {
    "key": "car_import_initiative_list_view",
    "name": "Initiatives",
    "model": "car_import.initiative",
    "menu_item": "car_import_menu_initiatives",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {
        "tree": {
            "fields": [
                {"name": "holder", "string": _("Holder"), "widget": "relation",
                 "displayField": "name", "width": "200"},
                {"name": "initiative_type", "string": _("Type"), "widget": "select", "width": "120"},
                {"name": "status", "string": _("Status"), "widget": "status", "width": "140"},
                {"name": "approval_number", "string": _("Approval"), "widget": "text", "width": "140"},
                {"name": "tier", "string": _("Tier"), "widget": "select", "width": "110"},
                {"name": "deposit_usd", "string": _("Deposit (USD)"), "widget": "number", "width": "130"},
                {"name": "refund_due_on", "string": _("Refund due"), "widget": "date", "width": "130"},
                {"name": "transferable", "string": _("Transferable"), "widget": "switch", "width": "120"},
                {"name": "deal", "string": _("Used on"), "widget": "relation",
                 "displayField": "name", "width": "140"},
            ],
        },
    },
}

car_import_initiative_form_view = {
    "key": "car_import_initiative_form_view",
    "name": "Initiative",
    "model": "car_import.initiative",
    "menu_item": "car_import_menu_initiatives",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions_list": [], "actions": []},
        "sheet": {
            "sections": [
                {
                    "title": _("The holder"),
                    "groups": [
                        {"fields": [
                            {"name": "holder", "string": _("Holder"), "widget": "relation",
                             "displayField": "name", "multiSelect": False, "required": True},
                            {"name": "country", "string": _("Country"), "widget": "text"},
                            {"name": "initiative_type", "string": _("Type"), "widget": "select"},
                            {"name": "approval_number", "string": _("Approval number"), "widget": "text"},
                            {"name": "status", "string": _("Status"), "widget": "select"},
                        ]},
                        {"fields": [
                            {"name": "deal", "string": _("Used on deal"), "widget": "relation",
                             "displayField": "name", "multiSelect": False},
                            # One modification, ever. The form says so rather than
                            # letting somebody find out at the ministry.
                            {"name": "modifications_used", "string": _("Modifications used (max 1)"),
                             "widget": "number"},
                        ]},
                    ],
                },
                {
                    "title": _("The deposit"),
                    "groups": [
                        {"fields": [
                            {"name": "tier", "string": _("Tier"), "widget": "select"},
                            {"name": "deposit_usd", "string": _("Deposit (USD)"), "widget": "number"},
                            {"name": "deposit_paid_on", "string": _("Paid on"), "widget": "date"},
                        ]},
                        {"fields": [
                            # Computed five years out; read-only so nobody "corrects" it.
                            {"name": "refund_due_on", "string": _("Refund due on"),
                             "widget": "date", "readonly": True},
                            {"name": "refunded_on", "string": _("Refunded on"), "widget": "date"},
                        ]},
                    ],
                },
                {
                    "title": _("Selling the right"),
                    "groups": [
                        {"fields": [
                            {"name": "transferable", "string": _("May be transferred"), "widget": "switch"},
                            {"name": "asking_price_egp", "string": _("Asking price (EGP)"),
                             "widget": "number"},
                            {"name": "participation_split", "string": _("Participation split"),
                             "widget": "text"},
                        ]},
                        {"fields": [
                            {"name": "buyer", "string": _("Buyer"), "widget": "relation",
                             "displayField": "name", "multiSelect": False},
                            {"name": "notes", "string": _("Notes"), "widget": "textarea"},
                        ]},
                    ],
                },
            ],
        },
    },
}

car_import_initiative_search_view = {
    "key": "car_import_initiative_search_view",
    "name": "Initiative search",
    "model": "car_import.initiative",
    "menu_item": "car_import_menu_initiatives",
    "view_type": "search",
    "priority": 20,
    "module": "car_import",
    "body": {
        "search": {
            "search_fields": ["approval_number", "holder.name", "country"],
            "filters": [
                {"name": "for_sale", "string": _("Offered for sale"),
                 "filter": {"field": "status", "operator": "eq", "value": "for_sale"}},
                {"name": "unused", "string": _("Not used yet"),
                 "filter": {"field": "deal", "operator": "is_null", "value": True}},
                {"name": "refund_due", "string": _("Refund due"),
                 "filter": {"field": "refunded_on", "operator": "is_null", "value": True}},
            ],
            "group_by": [
                {"name": "status", "string": _("Status")},
                {"name": "initiative_type", "string": _("Type")},
                {"name": "tier", "string": _("Tier")},
            ],
        },
    },
}
