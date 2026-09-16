# -*- coding: utf-8 -*-
"""Screens for call recordings, including the review list that matters most."""
from django.utils.translation import gettext as _

car_import_call_list_view = {
    "key": "car_import_call_list_view",
    "name": "Call recordings",
    "model": "car_import.callrecording",
    "menu_item": "car_import_menu_calls",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {
        "tree": {
            "fields": [
                {"name": "recorded_at", "string": _("When"), "widget": "datetime", "width": "160"},
                {"name": "partner", "string": _("Customer"), "widget": "relation",
                 "displayField": "name", "width": "190"},
                {"name": "customer_phone", "string": _("Number"), "widget": "text", "width": "140"},
                {"name": "agent", "string": _("Agent"), "widget": "relation",
                 "displayField": "name", "width": "150"},
                {"name": "deal", "string": _("Deal"), "widget": "relation",
                 "displayField": "name", "width": "140"},
                # The two columns somebody has to act on.
                {"name": "match_state", "string": _("Match"), "widget": "status", "width": "150"},
                {"name": "process_state", "string": _("Processing"), "widget": "status", "width": "140"},
                {"name": "duration_seconds", "string": _("Length (s)"), "widget": "number", "width": "110"},
                {"name": "is_simulated", "string": _("Simulated"), "widget": "switch", "width": "110"},
            ],
        },
    },
}

car_import_call_form_view = {
    "key": "car_import_call_form_view",
    "name": "Call recording",
    "model": "car_import.callrecording",
    "menu_item": "car_import_menu_calls",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions_list": [], "actions": []},
        "sheet": {
            "ribbon": {
                "field_text": "match_state",
                "color": {"warning": {"field": "match_state", "operator": "in",
                                      "value": ["unmatched", "ambiguous"]}},
                "invisible": {"field": "match_state", "operator": "in",
                              "value": ["matched", "manual"]},
            },
            "sections": [
                {
                    "title": _("The call"),
                    "groups": [
                        {"fields": [
                            {"name": "match_state", "string": _("Match"), "widget": "select",
                             "invisible": True},
                            {"name": "recorded_at", "string": _("When"), "widget": "datetime"},
                            {"name": "duration_seconds", "string": _("Length (s)"), "widget": "number"},
                            {"name": "direction", "string": _("Direction"), "widget": "select"},
                            {"name": "customer_phone", "string": _("Customer number"), "widget": "text"},
                            {"name": "audio", "string": _("Recording"), "widget": "attachment"},
                        ]},
                        {"fields": [
                            {"name": "agent", "string": _("Agent"), "widget": "relation",
                             "displayField": "name", "multiSelect": False},
                            {"name": "agent_folder", "string": _("Folder"), "widget": "text",
                             "readonly": True},
                            {"name": "file_name", "string": _("File"), "widget": "text",
                             "readonly": True},
                            {"name": "is_simulated", "string": _("Simulated"), "widget": "switch",
                             "readonly": True},
                        ]},
                    ],
                },
                {
                    "title": _("Who it was with"),
                    "groups": [
                        {"fields": [
                            {"name": "partner", "string": _("Customer"), "widget": "relation",
                             "displayField": "name", "multiSelect": False},
                            {"name": "deal", "string": _("Deal"), "widget": "relation",
                             "displayField": "name", "multiSelect": False},
                            {"name": "lead", "string": _("Lead"), "widget": "relation",
                             "displayField": "name", "multiSelect": False},
                        ]},
                        {"fields": [
                            # Why it could not be matched, in words, so whoever
                            # fixes it does not have to guess what went wrong.
                            {"name": "match_note", "string": _("Why it needs review"),
                             "widget": "text", "readonly": True},
                            {"name": "candidates", "string": _("Possible customers"),
                             "widget": "json", "readonly": True},
                        ]},
                    ],
                },
                {
                    "title": _("What was said"),
                    "groups": [
                        {"fields": [
                            {"name": "summary", "string": _("Summary"), "widget": "textarea"},
                            {"name": "action_items", "string": _("Action items"), "widget": "json"},
                        ]},
                        {"fields": [
                            {"name": "transcript", "string": _("Transcript"), "widget": "textarea"},
                            {"name": "process_state", "string": _("Processing"), "widget": "select"},
                            {"name": "error", "string": _("Error"), "widget": "text", "readonly": True},
                        ]},
                    ],
                },
                {
                    "title": _("Consent"),
                    "groups": [
                        {"fields": [
                            {"name": "consent_recorded", "string": _("Consent on file"),
                             "widget": "switch"},
                            # Internal by default: sending a summary to the
                            # customer is a separate, deliberate act.
                            {"name": "sent_to_customer", "string": _("Sent to the customer"),
                             "widget": "switch"},
                        ]},
                    ],
                },
            ],
        },
    },
}

car_import_call_search_view = {
    "key": "car_import_call_search_view",
    "name": "Call recording search",
    "model": "car_import.callrecording",
    "menu_item": "car_import_menu_calls",
    "view_type": "search",
    "priority": 20,
    "module": "car_import",
    "body": {
        "search": {
            "search_fields": ["customer_phone", "file_name", "partner.name", "summary"],
            "filters": [
                {"name": "needs_review", "string": _("Needs review"),
                 "filter": {"field": "match_state", "operator": "in",
                            "value": ["unmatched", "ambiguous"]}},
                {"name": "matched", "string": _("Matched"),
                 "filter": {"field": "match_state", "operator": "eq", "value": "matched"}},
                {"name": "summarised", "string": _("Summarised"),
                 "filter": {"field": "process_state", "operator": "eq", "value": "summarised"}},
                {"name": "real_only", "string": _("Real recordings only"),
                 "filter": {"field": "is_simulated", "operator": "eq", "value": False}},
            ],
            "group_by": [
                {"name": "match_state", "string": _("Match")},
                {"name": "agent", "string": _("Agent")},
                {"name": "process_state", "string": _("Processing")},
            ],
        },
    },
}
