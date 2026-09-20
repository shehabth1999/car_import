# -*- coding: utf-8 -*-
"""
The deal screens.

Every button here is one we declared: nothing is inherited from a sales order,
so there is no invoice, payment-link, coupon or lock action to hide.

The form is one short sheet and four tabs. It used to be five sections stacked
down one very tall page, which meant the ETA was two screens below the
customer's name and a person scrolling for the bill of lading passed the
financing rate on the way. Now: who and what on top, then *stage and
shipping*, *payment and plan*, *contract*, *delivery* as tabs, and the money
in a footer that follows you.
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
        "name": "action_set_stage",
        "string": _("Set stage…"),
        "icon": "ListRestart",
        "type": "menu",
        "as": "button",
        "variant": "secondary",
        "view_type": ["form", "list"],
        "menu_type": "modal",
        "view_key": "car_import_set_stage_form_view",
        "on_success": {"type": "refresh"},
    },
    {
        "name": "action_build_document_checklist",
        "string": _("Build document checklist"),
        "icon": "ClipboardList",
        "type": "server",
        "as": "dropdown",
        "view_type": ["form", "list"],
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

# What hangs off a deal, as counters that open the related list — instead of
# inline tables that would have to be posted back with every save.
_SMART_ACTIONS = [
    {"string": _("Quotations"), "icon": "Calculator", "model": "car_import.quote",
     "menu_item_key": "car_import_menu_quotes", "relation_field": "deal", "color": "primary",
     "context": {"default_fields": {"deal": "active_id"}}},
    {"string": _("Payments to confirm"), "icon": "BadgeCheck", "model": "car_import.paymentreceipt",
     "menu_item_key": "car_import_menu_receipts", "relation_field": "deal", "color": "warning",
     "domain": {"filters": {"operator": "and", "filters": [
         {"field": "state", "operator": "eq", "value": "pending"}]}}},
    {"string": _("Proforma invoices"), "icon": "Receipt", "model": "car_import.proformainvoice",
     "menu_item_key": "car_import_menu_proformas", "relation_field": "deal"},
    {"string": _("Contracts"), "icon": "FileText", "model": "car_import.contract",
     "menu_item_key": "car_import_menu_contracts", "relation_field": "deal",
     "context": {"default_fields": {"deal": "active_id"}}},
    {"string": _("Paperwork missing"), "icon": "FileWarning", "model": "car_import.dealdocument",
     "menu_item_key": "car_import_menu_deal_documents", "relation_field": "deal", "color": "warning",
     "domain": {"filters": {"operator": "and", "filters": [
         {"field": "state", "operator": "in", "value": ["missing", "rejected", "expired"]}]}}},
    {"string": _("Messages sent"), "icon": "Send", "model": "car_import.stagechangelog",
     "menu_item_key": "car_import_menu_stage_log", "relation_field": "deal", "color": "info"},
]

_NOT_INITIATIVE = {"field": "program", "operator": "ne", "value": "initiative"}
_IS_CASH = {"field": "financing_type", "operator": "eq", "value": "cash"}
_NOT_BANK = {"field": "financing_type", "operator": "ne", "value": "bank"}


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
                {"name": "import_stage", "widget": "relation", "displayField": "name", "string": _("Stage"), "width": "180"},
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
            # Without this the board is a flat wall of cards: the renderer only
            # draws stage columns when the view names the field to group on.
            "group_by": {
                "name": "import_stage",
                "tag": "field",
            },
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
        # No status pills in the header, deliberately. The header lays its
        # stage pills and the action buttons out on ONE 30px row with overflow
        # hidden: with fourteen Arabic stage names the buttons are pushed off
        # the screen and cease to exist. The stage is a field, moved with the
        # buttons; the kanban is where the pipeline is meant to be read.
        "header": {
            "actions_list": _SMART_ACTIONS,
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
                                # Declared (hidden) so the ribbon can read it — the ribbon
                                # renders from persisted data, not from the header alone.
                                {"name": "state", "string": _("Status"), "widget": "select", "invisible": True},
                                {"name": "name", "string": _("Reference"), "widget": "text", "readonly": True,
                                 "help": _("Given automatically on save — KA/year/number")},
                                {"name": "partner", "string": _("Customer"), "widget": "relation",
                                 "displayField": "name", "required": True, "multiSelect": False,
                                 "onChange": True,
                                 "help": _("Picking a customer pulls in their latest lead and the programme it says")},
                                {"name": "lead", "string": _("Lead"), "widget": "relation",
                                 "displayField": "name", "multiSelect": False,
                                 "help": _("The CRM lead this deal grew out of — it carries the ad and campaign the customer came from")},
                                {"name": "attribution_summary", "string": _("Came from"),
                                 "widget": "text", "readonly": True,
                                 "help": _("Read from the lead: paid or organic, campaign, first click")},
                                {"name": "assigned_to", "string": _("Sales agent"), "widget": "relation",
                                 "displayField": "name", "multiSelect": False,
                                 "help": _("Defaults to whoever opens the deal. An agent only sees the deals assigned to them")},
                                {"name": "hold_reason", "string": _("Reason for hold"), "widget": "text",
                                 "invisible": {"field": "state", "operator": "ne", "value": "on_hold"}},
                                {"name": "cancel_reason", "string": _("Reason for cancelling"), "widget": "text",
                                 "invisible": {"field": "state", "operator": "ne", "value": "cancelled"},
                                 "help": _("Cancelling after a deposit needs management's approval — this reason goes on the request")},
                            ],
                        },
                        {
                            "fields": [
                                {"name": "vehicle", "string": _("Car"), "widget": "relation",
                                 "displayField": "name", "multiSelect": False,
                                 "help": _("The physical car. Leave empty until one is chosen — the quotation's candidates come first")},
                                {"name": "program", "string": _("Programme"), "widget": "select",
                                 "help": _("Which of the six revenue lines this is. Commercial import asks management before the deal exists")},
                                {"name": "initiative", "string": _("Initiative"), "widget": "relation",
                                 "displayField": "name", "multiSelect": False, "invisible": _NOT_INITIATIVE,
                                 "help": _("The initiative the car ships under. Its holder's name goes on the contract's shipping clause")},
                                {"name": "customer_is_initiative_holder",
                                 "string": _("The customer holds the initiative"), "widget": "switch",
                                 "invisible": _NOT_INITIATIVE,
                                 "help": _("Customs clears in the customer's own name, so the company has no lien — instalments are refused")},
                                {"name": "accepted_quote", "string": _("Accepted quotation"),
                                 "widget": "relation", "displayField": "name",
                                 "multiSelect": False, "readonly": True,
                                 "help": _("Set by 'Customer accepted' on the quotation. Its money drives the payment marks below")},
                                {"name": "branch", "string": _("Branch"), "widget": "relation",
                                 "displayField": "name", "multiSelect": False},
                            ],
                        },
                    ],
                },
            ],
            # Sheet-level: below every tab, so the money is visible whichever
            # tab is open.
            "footer": {
                "fields": [
                    {"name": "amount_agreed", "string": _("Agreed €"), "widget": "number"},
                    {"separator": "thin"},
                    {"name": "amount_paid_marked", "string": _("Paid €"), "widget": "number"},
                    {"separator": "thin"},
                    {"name": "amount_due_marked", "string": _("Still due €"), "widget": "number",
                     "highlight": True},
                ],
                "position": "end",
            },
        },
        "tabs": [
            {
                "title": _("Stage and shipping"),
                "sections": [
                    {
                        "title": "",
                        "groups": [
                            {
                                "title": _("Where it is"),
                                "fields": [
                                    # Read-only: a stage moves through the buttons or the
                                    # kanban, so the gates in the stage machine always run.
                                    {"name": "import_stage", "string": _("Current stage"), "widget": "relation",
                                     "displayField": "name", "readonly": True, "multiSelect": False,
                                     "help": _("Moved with the buttons above, never typed — each move can message the customer")},
                                    {"name": "stage_entered_at", "string": _("In this stage since"),
                                     "widget": "datetime", "readonly": True},
                                    {"name": "previous_stage", "string": _("Previous stage"), "widget": "relation",
                                     "displayField": "name", "readonly": True, "multiSelect": False},
                                    {"name": "stage_is_blocked", "string": _("Blocked"), "widget": "switch",
                                     "help": _("A gate is refusing the next stage — the reason says which")},
                                    {"name": "blocked_reason", "string": _("Why it is blocked"), "widget": "text",
                                     "invisible": {"field": "stage_is_blocked", "operator": "eq", "value": False}},
                                    {"name": "notifications_suppressed", "string": _("Hold customer messages"),
                                     "widget": "switch",
                                     "help": _("On during migration or corrections, so a stage move tells nobody. Untick once the customer knows the system writes to them")},
                                    {"name": "public_status", "string": _("Customer-facing status"), "widget": "text",
                                     "help": _("The line the customer reads on the tracking page and in the AI's answer")},
                                ],
                            },
                            {
                                "title": _("Papers and the ship"),
                                "fields": [
                                    {"name": "acid_number", "string": _("ACID number"), "widget": "text",
                                     "help": _("Egypt's advance cargo ID — the longest wait in the whole journey, and not in our hands")},
                                    {"name": "import_approval_number", "string": _("Import approval"), "widget": "text"},
                                    {"name": "carrier", "string": _("Carrier"), "widget": "text"},
                                    {"name": "vessel", "string": _("Vessel"), "widget": "text"},
                                    {"name": "booking_ref", "string": _("Booking"), "widget": "text"},
                                    {"name": "sail_date", "string": _("Sailed on"), "widget": "date"},
                                    {"name": "bl_number", "string": _("Bill of lading"), "widget": "text",
                                     "help": _("The cash-on-B/L instalment in the contract falls due when this exists")},
                                    {"name": "bl_date", "string": _("B/L date"), "widget": "date"},
                                    {"name": "eta", "string": _("ETA"), "widget": "date",
                                     "help": _("What the customer is told. Change it and say so — the AI quotes this date")},
                                    {"name": "arrival_port", "string": _("Port"), "widget": "text"},
                                    {"name": "arrival_date", "string": _("Arrived on"), "widget": "date"},
                                    {"name": "notification_date", "string": _("Notification (إخطار) date"), "widget": "date"},
                                    {"name": "release_date", "string": _("Customs released on"), "widget": "date"},
                                    {"name": "tracking_url", "string": _("Tracking link"), "widget": "url"},
                                ],
                            },
                        ],
                    },
                ],
            },
            {
                "title": _("Payment and plan"),
                "sections": [
                    {
                        "title": "",
                        "groups": [
                            {
                                "title": _("The marks — not accounting"),
                                "fields": [
                                    {"name": "payment_state", "string": _("Payment"), "widget": "select", "readonly": True,
                                     "help": _("Follows the accepted quotation's 'paid so far', or the two Mark buttons. Never typed")},
                                    {"name": "amount_agreed", "string": _("Agreed amount"), "widget": "number",
                                     "onChange": True,
                                     "help": _("Copied from the accepted quotation's total; the due amount recomputes as you type")},
                                    {"name": "amount_paid_marked", "string": _("Marked as paid"), "widget": "number",
                                     "onChange": True,
                                     "help": _("What the accountant confirmed received. A mark, not a ledger entry")},
                                    {"name": "amount_due_marked", "string": _("Marked as due"), "widget": "number",
                                     "readonly": True, "help": _("Agreed minus paid")},
                                    {"name": "currency", "string": _("Currency"), "widget": "relation", "displayField": "code", "multiSelect": False,
                                     "help": _("EUR for imports; EGP for showroom cars")},
                                    {"name": "payment_marked_by", "string": _("Marked by"), "widget": "relation",
                                     "displayField": "name", "readonly": True, "multiSelect": False},
                                    {"name": "payment_marked_at", "string": _("Marked at"), "widget": "datetime",
                                     "readonly": True},
                                    {"name": "payment_note", "string": _("Note"), "widget": "text"},
                                ],
                            },
                            {
                                "title": _("The plan the customer agreed"),
                                "fields": [
                                    {"name": "financing_type", "string": _("Payment plan"), "widget": "select",
                                     "onChange": True,
                                     "help": _("Company instalments need management's approval and are refused to an initiative holder")},
                                    {"name": "financing_down_payment_pct", "string": _("Down payment %"), "widget": "number",
                                     "invisible": _IS_CASH},
                                    {"name": "financing_term_months", "string": _("Term (months)"), "widget": "number",
                                     "invisible": _IS_CASH},
                                    {"name": "financing_rate_pct", "string": _("Rate % a year (flat)"), "widget": "number",
                                     "invisible": _IS_CASH,
                                     "help": _("Flat, on the financed part — the company's published rate")},
                                    {"name": "financing_bank", "string": _("Bank"), "widget": "text",
                                     "invisible": _NOT_BANK},
                                    {"name": "cheques_received", "string": _("All cheques received"), "widget": "switch",
                                     "invisible": _IS_CASH,
                                     "help": _("The stage 'contract signed and money transferred' is gated on this for instalment deals")},
                                    {"name": "financing_note", "string": _("Financing note"), "widget": "text"},
                                ],
                            },
                        ],
                    },
                ],
            },
            {
                "title": _("Contract"),
                "sections": [
                    {
                        "title": "",
                        "groups": [
                            {
                                "title": _("As printed on the contract"),
                                "fields": [
                                    {"name": "contract_date", "string": _("Contract date"), "widget": "date"},
                                    {"name": "contract_total_eur", "string": _("Contract total (EUR)"), "widget": "number",
                                     "help": _("What the accountant agreed. Wins over the quotation when the contract is generated")},
                                    {"name": "contract_down_payment_eur", "string": _("Received at signing (EUR)"),
                                     "widget": "number"},
                                    {"name": "contract_bank_transfer_eur", "string": _("Bank transfer (EUR)"),
                                     "widget": "number"},
                                    {"name": "contract_cash_on_bl_eur", "string": _("Cash on bill of lading (EUR)"),
                                     "widget": "number",
                                     "help": _("The three payments must add up to the total — the contract refuses otherwise")},
                                ],
                            },
                            {
                                "title": _("Consent"),
                                "fields": [
                                    {"name": "media_consent", "string": _("Consent for photos and video"),
                                     "widget": "switch",
                                     "help": _("The customer agreed in the contract that their car may appear in content")},
                                ],
                            },
                        ],
                    },
                ],
            },
            {
                "title": _("Delivery and after-sales"),
                "sections": [
                    {
                        "title": "",
                        "groups": [
                            {
                                "title": _("Handover"),
                                "fields": [
                                    {"name": "delivery_date", "string": _("Delivered on"), "widget": "date"},
                                    {"name": "delivery_receipt", "string": _("Delivery receipt"), "widget": "files",
                                     "multiSelect": False, "accept": "image/*,application/pdf",
                                     "help": _("The signed محضر استلام. The final stage is gated on it")},
                                ],
                            },
                            {
                                "title": _("After the keys"),
                                "fields": [
                                    {"name": "licensing_state", "string": _("Licensing"), "widget": "text",
                                     "help": _("Not included in the price — a licensing agent is available by power of attorney")},
                                    {"name": "protection_state", "string": _("Protection film"), "widget": "text"},
                                    {"name": "warranty_activated", "string": _("Warranty activated"), "widget": "switch",
                                     "help": _("The manufacturer's two years from production. The company itself gives none")},
                                    {"name": "public_token", "string": _("Tracking token"), "widget": "text",
                                     "readonly": True,
                                     "help": _("The key on the customer's tracking link — never share it in a group")},
                                ],
                            },
                        ],
                    },
                ],
            },
        ],
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
