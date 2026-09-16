# -*- coding: utf-8 -*-
"""The calculator's bands, as a screen a manager can edit.

The owner's words when they sent the workbook were *"الاسعار دي قابلة للتعديل
على حسب حاجة السوق"*. That sentence is the whole reason this is a table with a
screen instead of five numbers in a Python file: the market moves faster than a
deploy, and the person who knows it moved is not a developer.

Dated, like every other reference table here — changing a band closes the old
row rather than rewriting history, so a quote given last month can still be
explained next month.
"""
from django.utils.translation import gettext as _

DATES = [
    {"name": "effective_from", "string": _("In force from"), "widget": "date"},
    {"name": "effective_to", "string": _("In force until"), "widget": "date"},
    {"name": "source_note", "string": _("Where this came from"), "widget": "text"},
]

car_import_pricing_band_list_view = {
    "key": "car_import_pricing_band_list_view",
    "name": "Pricing bands",
    "model": "car_import.pricingband",
    "menu_item": "car_import_menu_pricing_bands",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {"tree": {"fields": [
        {"name": "sequence", "string": _("#"), "widget": "number", "width": "60"},
        {"name": "name", "string": _("Band"), "widget": "text", "width": "200"},
        {"name": "gross_from_eur", "string": _("From (gross €)"), "widget": "number", "width": "150"},
        {"name": "gross_to_eur", "string": _("To (gross €)"), "widget": "number", "width": "150"},
        {"name": "admin_fee_type", "string": _("Admin fee is"), "widget": "select", "width": "180"},
        {"name": "admin_fee_value", "string": _("Value"), "widget": "number", "width": "120"},
        {"name": "deposit_pct", "string": _("Deposit %"), "widget": "number", "width": "120"},
        {"name": "effective_from", "string": _("From"), "widget": "date", "width": "130"},
        {"name": "effective_to", "string": _("Until"), "widget": "date", "width": "130"},
    ]}},
}

car_import_pricing_band_form_view = {
    "key": "car_import_pricing_band_form_view",
    "name": "Pricing band",
    "model": "car_import.pricingband",
    "menu_item": "car_import_menu_pricing_bands",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions_list": [], "actions": []},
        "sheet": {"sections": [
            {"title": _("Which prices this band covers"), "groups": [
                {"fields": [
                    {"name": "name", "string": _("Band"), "widget": "text", "required": True},
                    {"name": "sequence", "string": _("Order"), "widget": "number"},
                ]},
                {"fields": [
                    {"name": "gross_from_eur", "string": _("From (gross €, with VAT)"),
                     "widget": "number", "required": True},
                    {"name": "gross_to_eur", "string": _("To (gross €) — empty means no ceiling"),
                     "widget": "number"},
                ]},
            ]},
            {"title": _("What it charges"), "groups": [
                {"fields": [
                    {"name": "admin_fee_type", "string": _("Admin fee is"), "widget": "select"},
                    {"name": "admin_fee_value", "string": _("Amount, or percentage"),
                     "widget": "number"},
                ]},
                {"fields": [
                    {"name": "deposit_pct", "string": _("Deposit %"), "widget": "number"},
                ]},
            ]},
            {"title": _("Validity"), "groups": [
                {"fields": DATES},
                {"fields": [{"name": "notes", "string": _("Notes"), "widget": "textarea"}]},
            ]},
        ]},
    },
}
