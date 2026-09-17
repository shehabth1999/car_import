# -*- coding: utf-8 -*-
"""The operating switches, as a screen management can open.

`ConfigParameter` is the platform's key/value table and it ships with no
screen of its own — a switch nobody can find is not a switch. These views
show only this module's rows (`car_import.*`, filtered by the menu item),
with the key locked and the value editable. Flipping one takes effect on the
next message or the next AI turn; nothing is deployed or restarted.
"""
from django.utils.translation import gettext as _

car_import_switch_list_view = {
    "key": "car_import_switch_list_view",
    "name": _("Operating switches"),
    "model": "base.configparameter",
    "menu_item": "car_import_menu_switches",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {"tree": {"fields": [
        {"name": "key", "widget": "text", "string": _("Switch"), "width": "300"},
        {"name": "value", "widget": "text", "string": _("Value"), "width": "120"},
        {"name": "description", "widget": "text", "string": _("What it does"), "width": "600"},
        {"name": "updated_at", "widget": "datetime", "string": _("Changed"), "width": "160"},
    ]}},
}

car_import_switch_form_view = {
    "key": "car_import_switch_form_view",
    "name": _("Operating switch"),
    "model": "base.configparameter",
    "menu_item": "car_import_menu_switches",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions_list": [], "actions": []},
        "sheet": {"sections": [{"title": "", "groups": [
            {"fields": [
                {"name": "key", "string": _("Switch"), "widget": "text", "readonly": True,
                 "help": _("The name the code reads. Never changes")},
                {"name": "value", "string": _("Value"), "widget": "text", "required": True,
                 "help": _("0 = off, 1 = on for the yes/no switches; a number for the hours. Takes effect immediately")},
            ]},
            {"fullWidth": True, "fields": [
                {"name": "description", "string": _("What it does"), "widget": "textarea", "rows": 3,
                 "readonly": True},
            ]},
        ]}]},
    },
}
