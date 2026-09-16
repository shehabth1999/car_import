# -*- coding: utf-8 -*-
"""The car-import actions in the chat header — one dropdown, four entries.

They act on the customer of the open conversation, so every one is
`type: "server"`: the action runs first, reads the customer off the
conversation, and opens the right form or wizard already filled in. A
`type: "menu"` button opens static schema that cannot know who is on screen.

Handlers: `extensions.py :: ConversationExtension`. Gating is per action by
group; the deal and the quote are sales, the stage is operations too.
"""
from django.utils.translation import gettext as _

_SALES = ["car_import.sales_agent", "car_import.sales_manager", "car_import.management"]
_OPS = ["car_import.sales_agent", "car_import.sales_manager", "car_import.operations",
        "car_import.management"]


def _entry(name, string, icon, groups, variant="secondary", confirm=False):
    return {
        "operation": "append",
        "target": "actions",
        "content": {
            "name": name,
            "string": string,
            "icon": icon,
            "type": "server",
            "as": "dropdown",
            "view_type": ["form"],
            "variant": variant,
            "confirm_required": confirm,
            "allowed_groups": groups,
        },
    }


menu_dict = {
    "car_import_chat_actions": {
        "_inherit": "chat_main_menu_omnichannel",
        "inheritance_operations": [
            _entry("action_open_or_create_deal", _("Car deal"), "Car", _OPS, "primary"),
            _entry("action_new_quote", _("New quotation"), "Calculator", _SALES),
            _entry("action_qualify_customer", _("Qualify customer"), "ClipboardCheck", _SALES),
            _entry("action_set_stage_from_chat", _("Set stage…"), "ListOrdered", _OPS),
        ],
    },
}
