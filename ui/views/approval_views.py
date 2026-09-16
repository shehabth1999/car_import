# -*- coding: utf-8 -*-
"""The approval rules, and the requests they produce.

Two screens because they answer two different questions. Management edits the
rules the way they edit a fee — the thresholds are commercial policy, not
configuration a developer owns. Everyone else lives on the request list, which
is a queue: what is waiting, for whom, and how long it has been waiting.
"""
from django.utils.translation import gettext as _

_REQUEST_ACTIONS = [
    {
        "name": "action_approve",
        "string": _("Approve"),
        "icon": "Check",
        "type": "server",
        "as": "button",
        "variant": "primary",
        "view_type": ["form", "list"],
    },
    {
        "name": "action_refuse",
        "string": _("Refuse"),
        "icon": "X",
        "type": "server",
        "as": "button",
        "variant": "danger",
        "view_type": ["form", "list"],
        "confirm_required": True,
    },
]


car_approval_policy_list_view = {
    "key": "car_import_approval_policy_list_view",
    "name": _("Approval rules"),
    "model": "car_import.approvalpolicy",
    "menu_item": "car_import_menu_approval_policies",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {"tree": {"fields": [
        {"name": "subject", "widget": "select", "string": _("Subject"), "width": "230"},
        {"name": "name", "widget": "text", "string": _("Rule"), "width": "280"},
        {"name": "threshold_amount", "widget": "number", "string": _("Above"), "width": "130"},
        {"name": "currency", "widget": "text", "string": _("Currency"), "width": "100"},
        {"name": "approver_group", "widget": "text", "string": _("Approved by"), "width": "200"},
        {"name": "is_active", "widget": "switch", "string": _("In force"), "width": "110"},
        {"name": "effective_from", "widget": "date", "string": _("From"), "width": "130"},
    ]}},
}


car_approval_policy_form_view = {
    "key": "car_import_approval_policy_form_view",
    "name": _("Approval rule"),
    "model": "car_import.approvalpolicy",
    "menu_item": "car_import_menu_approval_policies",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions_list": [], "actions": []},
        "sheet": {"sections": [
            {"title": _("The rule"), "groups": [
                {"fields": [
                    {"name": "subject", "string": _("Subject"), "widget": "select",
                     "required": True},
                    {"name": "name", "string": _("Rule"), "widget": "text"},
                    {"name": "is_active", "string": _("In force"), "widget": "switch"},
                ]},
                {"fields": [
                    # Empty means "always". The client worded most of these that
                    # way — ANY discount on the fees, ANY non-standard schedule —
                    # and a zero here would mean the same thing while reading
                    # like somebody forgot to fill it in.
                    {"name": "threshold_amount", "string": _("Needs approval above"),
                     "widget": "number"},
                    {"name": "currency", "string": _("Currency"), "widget": "text"},
                    {"name": "approver_group", "string": _("Approved by (group)"),
                     "widget": "text"},
                ]},
            ]},
            {"title": _("Validity"), "groups": [
                {"fields": [
                    {"name": "effective_from", "string": _("In force from"), "widget": "date"},
                    {"name": "effective_to", "string": _("In force until"), "widget": "date"},
                ]},
                {"fields": [
                    {"name": "source_note", "string": _("Where this came from"), "widget": "text"},
                    {"name": "notes", "string": _("Notes"), "widget": "textarea"},
                ]},
            ]},
        ]},
    },
}


car_approval_request_list_view = {
    "key": "car_import_approval_request_list_view",
    "name": _("Approval requests"),
    "model": "car_import.approvalrequest",
    "menu_item": "car_import_menu_approval_requests",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions": _REQUEST_ACTIONS},
        "tree": {"fields": [
            {"name": "subject", "widget": "select", "string": _("Subject"), "width": "220"},
            {"name": "partner", "widget": "relation", "displayField": "name",
             "string": _("Customer"), "width": "190"},
            {"name": "deal", "widget": "relation", "displayField": "name",
             "string": _("Deal"), "width": "150"},
            {"name": "amount", "widget": "number", "string": _("Amount"), "width": "130"},
            {"name": "currency", "widget": "text", "string": _("Cur."), "width": "80"},
            {"name": "reason", "widget": "text", "string": _("Why"), "width": "260"},
            {"name": "requested_by", "widget": "relation", "displayField": "name",
             "string": _("Asked by"), "width": "150"},
            {"name": "state", "widget": "status", "string": _("Status"), "width": "120"},
            {"name": "created_at", "widget": "datetime", "string": _("Asked at"), "width": "160"},
        ]},
    },
}


car_approval_request_form_view = {
    "key": "car_import_approval_request_form_view",
    "name": _("Approval request"),
    "model": "car_import.approvalrequest",
    "menu_item": "car_import_menu_approval_requests",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions_list": [], "actions": _REQUEST_ACTIONS},
        "sheet": {
            "ribbon": {
                "field_text": "state",
                "color": {
                    "success": {"field": "state", "operator": "eq", "value": "approved"},
                    "danger": {"field": "state", "operator": "eq", "value": "refused"},
                },
                "invisible": {"field": "state", "operator": "eq", "value": "pending"},
            },
            "sections": [
                {"title": _("What is being asked"), "groups": [
                    {"fields": [
                        {"name": "state", "string": _("Status"), "widget": "select",
                         "invisible": True},
                        {"name": "subject", "string": _("Subject"), "widget": "select",
                         "readonly": True},
                        {"name": "policy", "string": _("Rule"), "widget": "relation",
                         "displayField": "name", "readonly": True, "multiSelect": False},
                        {"name": "amount", "string": _("Amount"), "widget": "number",
                         "readonly": True},
                        {"name": "currency", "string": _("Currency"), "widget": "text",
                         "readonly": True},
                    ]},
                    {"fields": [
                        {"name": "partner", "string": _("Customer"), "widget": "relation",
                         "displayField": "name", "readonly": True, "multiSelect": False},
                        {"name": "deal", "string": _("Deal"), "widget": "relation",
                         "displayField": "name", "readonly": True, "multiSelect": False},
                        {"name": "quote", "string": _("Quotation"), "widget": "relation",
                         "displayField": "name", "readonly": True, "multiSelect": False},
                        {"name": "requested_by", "string": _("Asked by"), "widget": "relation",
                         "displayField": "name", "readonly": True, "multiSelect": False},
                    ]},
                ]},
                {"title": _("Why"), "groups": [
                    {"fullWidth": True, "fields": [
                        {"name": "reason", "string": _("Reason"), "widget": "textarea",
                         "readonly": True},
                    ]},
                ]},
                {"title": _("The decision"), "groups": [
                    {"fields": [
                        {"name": "decided_by", "string": _("Decided by"), "widget": "relation",
                         "displayField": "name", "readonly": True, "multiSelect": False},
                        {"name": "decided_at", "string": _("Decided at"), "widget": "datetime",
                         "readonly": True},
                    ]},
                    {"fields": [
                        {"name": "decision_note", "string": _("Note"), "widget": "text"},
                    ]},
                ]},
            ],
        },
    },
}


car_approval_request_search_view = {
    "key": "car_import_approval_request_search_view",
    "name": _("Approval search"),
    "model": "car_import.approvalrequest",
    "menu_item": "car_import_menu_approval_requests",
    "view_type": "search",
    "priority": 20,
    "module": "car_import",
    "body": {"search": {
        "search_fields": [
            {"name": ["reason"], "string": _("Why"), "widget": "text"},
            {"name": ["partner__name"], "string": _("Customer"), "widget": "text"},
            {"name": ["deal__name"], "string": _("Deal"), "widget": "text"},
        ],
        "filters": [
            {"name": "pending", "string": _("Waiting"),
             "filter": {"field": "state", "operator": "eq", "value": "pending"}},
            {"name": "approved", "string": _("Approved"),
             "filter": {"field": "state", "operator": "eq", "value": "approved"}},
            {"name": "refused", "string": _("Refused"),
             "filter": {"field": "state", "operator": "eq", "value": "refused"}},
        ],
        "group_by": [
            {"name": "subject", "string": _("Subject")},
            {"name": "state", "string": _("Status")},
            {"name": "requested_by", "string": _("Asked by")},
        ],
        "order_by": [{"name": "id", "string": _("Newest"), "direction": "desc"}],
    }},
}


# The modal behind "Set stage…" on the deal.
car_import_set_stage_form_view = {
    "key": "car_import_set_stage_form_view",
    "name": "Set stage",
    "priority": 1,
    "module": "car_import",
    "model": "car_import.setstage",
    "view_type": "form",
    "body": {"sheet": {"sections": [
        {"title": "", "groups": [
            {"fields": [
                {"name": "import_stage", "string": _("Stage"), "widget": "relation",
                 "displayField": "name", "required": True, "multiSelect": False},
            ]},
            {"fields": [
                {"name": "reason", "string": _("Why"), "widget": "text", "required": True},
                {"name": "notify_customer", "string": _("Tell the customer too"),
                 "widget": "switch"},
            ]},
        ]},
    ]}},
}
