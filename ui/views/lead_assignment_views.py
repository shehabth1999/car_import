# -*- coding: utf-8 -*-
"""Lead assignment groups, as a screen management owns.

The same table the client filled in Odoo — a name, the lead tags, the
salespeople, a daily limit — because the people who will set it up have set it
up before. Who gets which tag is a commercial decision that changes when
somebody joins, leaves or goes on holiday; it does not belong in code.

The help texts carry the whole rule, since this screen is the only place a
manager will ever read it: a lead goes to the next salesperson in turn, nobody
gets more than the daily limit in a day, and anyone on approved time off is
skipped by the job (services/lead_assignment.py) without being taken off the
list.
"""
from django.utils.translation import gettext as _

car_import_lead_assignment_group_list_view = {
    "key": "car_import_lead_assignment_group_list_view",
    "name": _("Lead assignment groups"),
    "model": "car_import.leadassignmentgroup",
    "menu_item": "car_import_menu_lead_assignment",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {"tree": {"fields": [
        {"name": "name", "widget": "text", "string": _("Name"), "width": "220"},
        {"name": "tags", "widget": "relation", "displayField": "name", "multiSelect": True,
         "string": _("Lead tags"), "width": "280"},
        {"name": "salespeople", "widget": "relation", "displayField": "name", "multiSelect": True,
         "string": _("Salespeople"), "width": "320"},
        {"name": "daily_limit", "widget": "number", "string": _("Daily limit"), "width": "120"},
        {"name": "active", "widget": "switch", "string": _("Active"), "width": "100"},
    ]}},
}


car_import_lead_assignment_group_form_view = {
    "key": "car_import_lead_assignment_group_form_view",
    "name": _("Lead assignment group"),
    "model": "car_import.leadassignmentgroup",
    "menu_item": "car_import_menu_lead_assignment",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions_list": [], "actions": []},
        "sheet": {"sections": [
            {"title": _("Which leads"), "groups": [
                {"fields": [
                    {"name": "name", "string": _("Name"), "widget": "text", "required": True},
                    {"name": "active", "string": _("Active"), "widget": "switch", "defaultValue": True,
                     "help": _("Switch off to stop handing out leads through this group.")},
                ]},
                {"fields": [
                    # Empty is a rule, not an oversight: the catch-all group,
                    # tried after every group that has tags.
                    {"name": "tags", "string": _("Lead tags"), "widget": "relation", "displayField": "name",
                     "multiSelect": True,
                     "help": _("A lead that carries any of these tags belongs to this group. Leave empty to make this a catch-all group: it is tried last and takes the leads no tagged group matched.")},
                ]},
            ]},
            {"title": _("Who gets them"), "groups": [
                {"fields": [
                    {"name": "salespeople", "string": _("Salespeople"), "widget": "relation",
                     "displayField": "name", "multiSelect": True,
                     "help": _("Leads go to these people one at a time, in turn. Anyone on approved time off, or already at the daily limit, is skipped automatically; when nobody is free the lead waits.")},
                ]},
                {"fields": [
                    {"name": "daily_limit", "string": _("Daily limit"), "widget": "number", "min": 0,
                     "defaultValue": 100,
                     "help": _("The most leads one salesperson receives from this group in a day. 0 means no limit.")},
                    # The job's own counter (editable=False on the model): shown
                    # so a manager can see the turn moving, never typed.
                    {"name": "last_assigned_index", "string": _("Last turn"), "widget": "number",
                     "readonly": True,
                     "help": _("Set by the system. It remembers who received the last lead, so the next one goes to the person after them.")},
                ]},
            ]},
        ]},
    },
}
