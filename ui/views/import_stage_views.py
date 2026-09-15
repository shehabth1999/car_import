# -*- coding: utf-8 -*-
"""Stages and the message each one sends — ops edit these, not developers."""
from django.utils.translation import gettext as _

import_stage_list_view = {
    "key": "car_import_stage_list_view",
    "name": _("Import stages"),
    "model": "car_import.importstage",
    "menu_item": "car_import_menu_stages",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {
        "tree": {
            "fields": [
                {"name": "sequence", "widget": "number", "string": _("#"), "width": "80"},
                {"name": "name", "widget": "text", "string": _("Stage name"), "width": "260"},
                {"name": "name_en", "widget": "text", "string": _("Stage (English)"), "width": "220"},
                {"name": "code", "widget": "text", "string": _("Code"), "width": "180"},
                {"name": "notify_customer", "widget": "switch", "string": _("Messages the customer"), "width": "160"},
                {"name": "requires_agent_approval", "widget": "switch", "string": _("Agent presses send"), "width": "160"},
                {"name": "send_delay_minutes", "widget": "number", "string": _("Delay (min)"), "width": "120"},
                {"name": "is_final", "widget": "switch", "string": _("Final"), "width": "100"},
            ],
        },
    },
}

import_stage_form_view = {
    "key": "car_import_stage_form_view",
    "name": _("Import stage"),
    "model": "car_import.importstage",
    "menu_item": "car_import_menu_stages",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {
        "sheet": {
            "sections": [
                {
                    "title": _("The stage"),
                    "groups": [
                        {
                            "fields": [
                                {"name": "name", "string": _("Stage name"), "widget": "text", "required": True},
                                {"name": "name_en", "string": _("Stage (English)"), "widget": "text"},
                                {"name": "code", "string": _("Code"), "widget": "text", "required": True},
                                {"name": "sequence", "string": _("Order"), "widget": "number"},
                                {"name": "color", "string": _("Colour"), "widget": "color"},
                                {"name": "fold", "string": _("Folded in the pipeline"), "widget": "switch"},
                                {"name": "is_final", "string": _("Final stage"), "widget": "switch"},
                            ],
                        },
                    ],
                },
                {
                    "title": _("The customer's message"),
                    "groups": [
                        {
                            "fields": [
                                {"name": "notify_customer", "string": _("Message the customer"), "widget": "switch"},
                                {"name": "requires_agent_approval", "string": _("An agent presses send"),
                                 "widget": "switch"},
                                {"name": "send_delay_minutes", "string": _("Delay (minutes)"), "widget": "number"},
                                {"name": "attach_media", "string": _("Attach photos and video"), "widget": "switch"},
                                {"name": "whatsapp_template", "string": _("WhatsApp template"), "widget": "relation",
                                 "displayField": "name", "multiSelect": False,
                                 "help": _("Used outside the 24-hour WhatsApp window")},
                            ],
                        },
                        {
                            "fields": [
                                {"name": "fallback_text_ar", "string": _("Message text (Arabic)"), "widget": "textarea",
                                 "help": _("{customer_name} {model} {model_year} {vin} {stage_name} {port} "
                                           "{vessel} {eta} {bl_number} {tracking_url} {deal_ref}")},
                                {"name": "fallback_text_en", "string": _("Message text (English)"), "widget": "textarea"},
                            ],
                        },
                    ],
                },
            ],
        },
    },
}
