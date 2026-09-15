# -*- coding: utf-8 -*-
"""
The deal screens.

Every button here is one we declared: nothing is inherited from a sales order,
so there is no invoice, payment-link, coupon or lock action to hide.
"""
from django.utils.translation import gettext as _

_STAGE_ACTIONS = [
    {
        "name": "action_move_next_stage",
        "string": _("Move to next stage"),
        "icon": "ArrowRight",
        "type": "server",
        "as": "button",
        "variant": "primary",
        "view_type": ["form", "list"],
        "confirm_required": False,
    },
    {
        "name": "action_send_stage_update",
        "string": _("Send update to customer"),
        "icon": "Send",
        "type": "server",
        "as": "button",
        "variant": "secondary",
        "view_type": ["form"],
    },
    {
        "name": "action_mark_deposit_received",
        "string": _("Mark deposit received"),
        "icon": "BadgeCheck",
        "type": "server",
        "as": "dropdown",
        "view_type": ["form", "list"],
    },
    {
        "name": "action_mark_fully_paid",
        "string": _("Mark fully paid"),
        "icon": "CheckCheck",
        "type": "server",
        "as": "dropdown",
        "view_type": ["form", "list"],
    },
    {
        "name": "action_toggle_ai",
        "string": _("AI on / off for this customer"),
        "icon": "Bot",
        "type": "server",
        "as": "dropdown",
        "view_type": ["form"],
    },
    {
        "name": "action_hold",
        "string": _("Put on hold"),
        "icon": "PauseCircle",
        "type": "server",
        "as": "dropdown",
        "view_type": ["form"],
        "invisible": {"field": "state", "operator": "ne", "value": "open"},
    },
    {
        "name": "action_resume",
        "string": _("Reopen"),
        "icon": "PlayCircle",
        "type": "server",
        "as": "dropdown",
        "view_type": ["form"],
        "invisible": {"field": "state", "operator": "ne", "value": "on_hold"},
    },
    {
        "name": "action_cancel",
        "string": _("Cancel deal"),
        "icon": "XCircle",
        "type": "server",
        "as": "dropdown",
        "variant": "danger",
        "view_type": ["form"],
        "confirm_required": True,
    },
]


car_deal_list_view = {
    "key": "car_import_deal_list_view",
    "name": _("Car deals"),
    "model": "car_import.cardeal",
    "menu_item": "car_import_menu_deals",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions": _STAGE_ACTIONS},
        "tree": {
            "fields": [
                {"name": "name", "widget": "text", "string": _("Reference"), "width": "140"},
                {"name": "partner", "widget": "relation", "displayField": "name", "string": _("Customer"), "width": "200"},
                {"name": "vehicle", "widget": "relation", "displayField": "name", "string": _("Car"), "width": "220"},
                {"name": "import_stage", "widget": "relation", "displayField": "name_ar", "string": _("Stage"), "width": "180"},
                {"name": "state", "widget": "status", "string": _("Status"), "width": "120"},
                {"name": "payment_state", "widget": "status", "string": _("Payment"), "width": "140"},
                {"name": "financing_type", "widget": "select", "string": _("Plan"), "width": "140"},
                {"name": "assigned_to", "widget": "relation", "displayField": "name", "string": _("Agent"), "width": "160"},
                {"name": "eta", "widget": "date", "string": _("ETA"), "width": "120"},
                {"name": "arrival_port", "widget": "text", "string": _("Port"), "width": "120"},
            ],
        },
    },
}


car_deal_kanban_view = {
    "key": "car_import_deal_kanban_view",
    "name": _("Deal pipeline"),
    "model": "car_import.cardeal",
    "menu_item": "car_import_menu_deals",
    "view_type": "kanban",
    "priority": 5,
    "module": "car_import",
    "body": {
        "kanban": {
            "id": "car-import-deals",
            "name": _("Deal pipeline"),
            "description": _("Every open car, by shipping stage"),
            "card": {
                "header": {
                    "profile": {
                        "title": {"name": "partner", "tag": "field", "widget": "relation",
                                  "displayField": "name", "string": _("Customer")},
                        "subtitle": {"name": "vehicle", "tag": "field", "widget": "relation",
                                     "displayField": "name", "string": _("Car")},
                    },
                    "fields": [
                        {"name": "name", "string": _("Reference"), "widget": "text"},
                    ],
                },
                "body": {
                    "fields": [
                        {"name": "payment_state", "string": _("Payment"), "widget": "status"},
                        {"name": "assigned_to", "string": _("Agent"), "widget": "relation", "displayField": "name"},
                        {"name": "eta", "string": _("ETA"), "widget": "date"},
                        {"name": "stage_entered_at", "string": _("In stage since"), "widget": "date"},
                    ],
                },
            },
        },
    },
}


car_deal_form_view = {
    "key": "car_import_deal_form_view",
    "name": _("Car deal"),
    "model": "car_import.cardeal",
    "menu_item": "car_import_menu_deals",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {
            "status": {
                "name": "import_stage",
                "widget": "status",
                "string": _("Stage"),
                "readonly": True,  # stages move through the buttons, never by clicking
            },
            "actions_list": [],
            "actions": _STAGE_ACTIONS,
        },
        "sheet": {
            "ribbon": {
                "field_text": "state",
                "color": {
                    "success": {"field": "state", "operator": "eq", "value": "done"},
                    "danger": {"field": "state", "operator": "eq", "value": "cancelled"},
                    "warning": {"field": "state", "operator": "eq", "value": "on_hold"},
                },
                "invisible": {"field": "state", "operator": "eq", "value": "open"},
            },
            "sections": [
                {
                    "title": _("Customer and car"),
                    "groups": [
                        {
                            "fields": [
                                {"name": "name", "string": _("Reference"), "widget": "text", "readonly": True},
                                {"name": "partner", "string": _("Customer"), "widget": "relation",
                                 "displayField": "name", "required": True, "multiSelect": False},
                                {"name": "lead", "string": _("Lead"), "widget": "relation",
                                 "displayField": "name", "multiSelect": False},
                                {"name": "assigned_to", "string": _("Sales agent"), "widget": "relation",
                                 "displayField": "name", "multiSelect": False},
                            ],
                        },
                        {
                            "fields": [
                                {"name": "vehicle", "string": _("Car"), "widget": "relation",
                                 "displayField": "name", "multiSelect": False},
                                {"name": "program", "string": _("Programme"), "widget": "select"},
                                {"name": "customer_is_initiative_holder",
                                 "string": _("The customer holds the initiative"), "widget": "switch"},
                                {"name": "branch", "string": _("Branch"), "widget": "relation",
                                 "displayField": "name", "multiSelect": False},
                            ],
                        },
                    ],
                },
                {
                    "title": _("Stage and shipping"),
                    "groups": [
                        {
                            "fields": [
                                {"name": "stage_entered_at", "string": _("In this stage since"),
                                 "widget": "datetime", "readonly": True},
                                {"name": "previous_stage", "string": _("Previous stage"), "widget": "relation",
                                 "displayField": "name_ar", "readonly": True, "multiSelect": False},
                                {"name": "stage_is_blocked", "string": _("Blocked"), "widget": "switch"},
                                {"name": "blocked_reason", "string": _("Why it is blocked"), "widget": "text"},
                                {"name": "notifications_suppressed", "string": _("Hold customer messages"),
                                 "widget": "switch"},
                            ],
                        },
                        {
                            "fields": [
                                {"name": "acid_number", "string": _("ACID number"), "widget": "text"},
                                {"name": "import_approval_number", "string": _("Import approval"), "widget": "text"},
                                {"name": "carrier", "string": _("Carrier"), "widget": "text"},
                                {"name": "vessel", "string": _("Vessel"), "widget": "text"},
                                {"name": "sail_date", "string": _("Sailed on"), "widget": "date"},
                                {"name": "bl_number", "string": _("Bill of lading"), "widget": "text"},
                                {"name": "eta", "string": _("ETA"), "widget": "date"},
                                {"name": "arrival_port", "string": _("Port"), "widget": "text"},
                                {"name": "arrival_date", "string": _("Arrived on"), "widget": "date"},
                                {"name": "release_date", "string": _("Customs released on"), "widget": "date"},
                                {"name": "tracking_url", "string": _("Tracking link"), "widget": "text"},
                            ],
                        },
                    ],
                },
                {
                    "title": _("Payment and plan"),
                    "groups": [
                        {
                            "fields": [
                                {"name": "payment_state", "string": _("Payment"), "widget": "select", "readonly": True},
                                {"name": "amount_agreed", "string": _("Agreed amount"), "widget": "number"},
                                {"name": "amount_paid_marked", "string": _("Marked as paid"), "widget": "number"},
                                {"name": "amount_due_marked", "string": _("Marked as due"), "widget": "number"},
                                {"name": "currency_note", "string": _("Currency"), "widget": "text"},
                                {"name": "payment_marked_by", "string": _("Marked by"), "widget": "relation",
                                 "displayField": "name", "readonly": True, "multiSelect": False},
                                {"name": "payment_marked_at", "string": _("Marked at"), "widget": "datetime",
                                 "readonly": True},
                                {"name": "payment_note", "string": _("Note"), "widget": "text"},
                            ],
                        },
                        {
                            "fields": [
                                {"name": "financing_type", "string": _("Payment plan"), "widget": "select"},
                                {"name": "financing_down_payment_pct", "string": _("Down payment %"), "widget": "number"},
                                {"name": "financing_term_months", "string": _("Term (months)"), "widget": "number"},
                                {"name": "financing_rate_pct", "string": _("Rate % a year (flat)"), "widget": "number"},
                                {"name": "financing_bank", "string": _("Bank"), "widget": "text"},
                                {"name": "cheques_received", "string": _("All cheques received"), "widget": "switch"},
                                {"name": "financing_note", "string": _("Financing note"), "widget": "text"},
                            ],
                        },
                    ],
                },
                {
                    "title": _("Contract"),
                    "groups": [
                        {
                            "fields": [
                                {"name": "contract_date", "string": _("Contract date"), "widget": "date"},
                                {"name": "contract_total_eur", "string": _("Contract total (EUR)"), "widget": "number"},
                                {"name": "contract_down_payment_eur", "string": _("Received at signing (EUR)"),
                                 "widget": "number"},
                                {"name": "contract_bank_transfer_eur", "string": _("Bank transfer (EUR)"),
                                 "widget": "number"},
                                {"name": "contract_cash_on_bl_eur", "string": _("Cash on bill of lading (EUR)"),
                                 "widget": "number"},
                                {"name": "media_consent", "string": _("Consent for photos and video"),
                                 "widget": "switch"},
                            ],
                        },
                    ],
                },
                {
                    "title": _("Delivery"),
                    "groups": [
                        {
                            "fields": [
                                {"name": "delivery_date", "string": _("Delivered on"), "widget": "date"},
                                {"name": "delivery_receipt", "string": _("Delivery receipt"), "widget": "files",
                                 "multiSelect": False, "accept": "image/*,application/pdf"},
                                {"name": "licensing_state", "string": _("Licensing"), "widget": "text"},
                                {"name": "protection_state", "string": _("Protection film"), "widget": "text"},
                                {"name": "warranty_activated", "string": _("Warranty activated"), "widget": "switch"},
                            ],
                        },
                    ],
                },
            ],
        },
    },
}


car_deal_search_view = {
    "key": "car_import_deal_search_view",
    "name": _("Deal search"),
    "model": "car_import.cardeal",
    "menu_item": "car_import_menu_deals",
    "view_type": "search",
    "priority": 20,
    "module": "car_import",
    "body": {
        "search": {
            "search_fields": [
                {"name": ["name"], "string": _("Reference"), "widget": "text"},
                {"name": ["partner__name"], "string": _("Customer"), "widget": "text"},
                {"name": ["vehicle__vin"], "string": _("VIN"), "widget": "text"},
                {"name": ["vehicle__model"], "string": _("Model"), "widget": "text"},
                {"name": ["bl_number"], "string": _("Bill of lading"), "widget": "text"},
                {"name": ["acid_number"], "string": _("ACID"), "widget": "text"},
            ],
            "filters": [
                {"name": "open", "string": _("Open"),
                 "filter": {"field": "state", "operator": "eq", "value": "open"}},
                {"name": "on_hold", "string": _("On hold"),
                 "filter": {"field": "state", "operator": "eq", "value": "on_hold"}},
                {"name": "unpaid", "string": _("Not paid"),
                 "filter": {"field": "payment_state", "operator": "eq", "value": "not_paid"}},
                {"name": "instalments", "string": _("On instalments"),
                 "filter": {"field": "financing_type", "operator": "eq", "value": "direct_instalments"}},
                {"name": "blocked", "string": _("Blocked"),
                 "filter": {"field": "stage_is_blocked", "operator": "eq", "value": True}},
                {"name": "messages_held", "string": _("Messages held"),
                 "filter": {"field": "notifications_suppressed", "operator": "eq", "value": True}},
            ],
            "group_by": [
                {"name": "import_stage", "string": _("Stage")},
                {"name": "assigned_to", "string": _("Agent")},
                {"name": "program", "string": _("Programme")},
                {"name": "payment_state", "string": _("Payment")},
                {"name": "arrival_port", "string": _("Port")},
            ],
            "order_by": [
                {"name": "eta", "string": _("ETA"), "direction": "asc"},
                {"name": "id", "string": _("Newest"), "direction": "desc"},
            ],
        },
    },
}
