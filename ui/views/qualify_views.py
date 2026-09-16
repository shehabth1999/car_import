# -*- coding: utf-8 -*-
"""The qualification wizard form, opened from the chat header."""
from django.utils.translation import gettext as _

car_import_qualify_form_view = {
    "key": "car_import_qualify_form_view",
    "name": "Qualify customer",
    "model": "car_import.qualifycustomer",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {
        # sheet → sections → groups → fields: a group straight under the sheet
        # is accepted by the sync and drawn as nothing.
        "sheet": {"sections": [{"title": "", "groups": [
                {"title": _("Customer"), "fields": [
                    {"name": "partner", "string": _("Customer"), "widget": "relation",
                     "displayField": "name", "readonly": True, "required": True},
                ]},
                {"title": _("What they want"), "fields": [
                    {"name": "program", "string": _("Programme"), "widget": "select"},
                    {"name": "initiative_type", "string": _("Initiative type"), "widget": "select",
                     "invisible": {"field": "program", "operator": "ne", "value": "initiative"}},
                    {"name": "model_wanted", "string": _("Model wanted"), "widget": "text"},
                    {"name": "model_year_wanted", "string": _("Model year wanted"), "widget": "number"},
                    {"name": "trim_wanted", "string": _("Trim wanted"), "widget": "text"},
                    {"name": "colour_wanted", "string": _("Colour wanted"), "widget": "text"},
                    {"name": "condition_wanted", "string": _("Zero or used"), "widget": "select"},
                ]},
                {"title": _("Money and place"), "fields": [
                    {"name": "budget_eur", "string": _("Budget (€)"), "widget": "number"},
                    {"name": "funds_ready_on", "string": _("Funds ready on"), "widget": "date"},
                    {"name": "residence_country", "string": _("Country of residence"), "widget": "text"},
                    {"name": "is_expat", "string": _("Egyptian abroad"), "widget": "switch"},
                    {"name": "note", "string": _("Note"), "widget": "text"},
                ]},
            ]}],
        },
    },
}
