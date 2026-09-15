# -*- coding: utf-8 -*-
"""Proof that the customer was actually told."""
from django.utils.translation import gettext as _

stage_change_log_list_view = {
    "key": "car_import_stage_log_list_view",
    "name": _("Stage messages"),
    "model": "car_import.stagechangelog",
    "menu_item": "car_import_menu_stage_log",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {
        "tree": {
            "fields": [
                {"name": "changed_at", "widget": "datetime", "string": _("When"), "width": "170"},
                {"name": "deal", "widget": "relation", "displayField": "name", "string": _("Deal"), "width": "160"},
                {"name": "from_stage", "widget": "relation", "displayField": "name", "string": _("From"), "width": "170"},
                {"name": "to_stage", "widget": "relation", "displayField": "name", "string": _("To"), "width": "170"},
                {"name": "notification_state", "widget": "status", "string": _("Message"), "width": "150"},
                {"name": "channel_used", "widget": "text", "string": _("Channel"), "width": "130"},
                {"name": "changed_by", "widget": "relation", "displayField": "name", "string": _("Moved by"), "width": "160"},
                {"name": "error", "widget": "text", "string": _("Error"), "width": "260"},
            ],
        },
    },
}

stage_change_log_search_view = {
    "key": "car_import_stage_log_search_view",
    "name": _("Stage message search"),
    "model": "car_import.stagechangelog",
    "menu_item": "car_import_menu_stage_log",
    "view_type": "search",
    "priority": 20,
    "module": "car_import",
    "body": {
        "search": {
            "search_fields": [
                {"name": ["deal__name"], "string": _("Deal"), "widget": "text"},
                {"name": ["message_text"], "string": _("Message"), "widget": "text"},
            ],
            "filters": [
                {"name": "failed", "string": _("Failed"),
                 "filter": {"field": "notification_state", "operator": "eq", "value": "failed"}},
                {"name": "awaiting", "string": _("Waiting for an agent"),
                 "filter": {"field": "notification_state", "operator": "eq", "value": "awaiting_approval"}},
                {"name": "sent", "string": _("Sent"),
                 "filter": {"field": "notification_state", "operator": "eq", "value": "sent"}},
            ],
            "group_by": [
                {"name": "notification_state", "string": _("Message state")},
                {"name": "to_stage", "string": _("Stage")},
            ],
            "order_by": [
                {"name": "changed_at", "string": _("Newest"), "direction": "desc"},
            ],
        },
    },
}
