# -*- coding: utf-8 -*-
"""The car catalogue: brands, and each brand's models.

Every car, advert, price row, website car and lead picks from these two lists,
so a spelling is fixed once — here — with "Also matches" for the other ways
people write it.
"""
from django.utils.translation import gettext as _

# ── brands ───────────────────────────────────────────────────────────────────
car_brand_list_view = {
    "key": "car_import_car_brand_list_view",
    "name": _("Car brands"),
    "model": "car_import.carbrand",
    "menu_item": "car_import_menu_car_brands",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {"tree": {"fields": [
        {"name": "sequence", "widget": "number", "string": _("Order"), "width": "80"},
        {"name": "name", "widget": "text", "string": _("Brand"), "width": "200"},
        {"name": "name_ar", "widget": "text", "string": _("Name (Arabic)"), "width": "180"},
        {"name": "aliases", "widget": "text", "string": _("Also matches"), "width": "260"},
        {"name": "website_id", "widget": "number", "string": _("Website id"), "width": "110"},
    ]}},
}

car_brand_form_view = {
    "key": "car_import_car_brand_form_view",
    "name": _("Car brand"),
    "model": "car_import.carbrand",
    "menu_item": "car_import_menu_car_brands",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {"header": {"actions_list": [], "actions": []}, "sheet": {"sections": [{"title": _("Brand"), "groups": [
        {"fields": [
            {"name": "name", "string": _("Brand"), "widget": "text", "required": True,
             "help": _("As it prints on a contract, e.g. Mercedes-Benz")},
            {"name": "name_ar", "string": _("Name (Arabic)"), "widget": "text"},
            {"name": "aliases", "string": _("Also matches"), "widget": "text",
             "help": _("Other spellings customers and adverts use, comma separated — they all find this brand")},
        ]},
        {"fields": [
            {"name": "logo", "string": _("Logo"), "widget": "files", "multiSelect": False, "accept": "image/*"},
            {"name": "website_id", "string": _("Website id"), "widget": "number",
             "help": _("Filled when the website lists are read. Empty: the website does not carry this brand, "
                       "and its cars cannot be sent there")},
            {"name": "sequence", "string": _("Order"), "widget": "number"},
        ]},
    ]}]}},
}

car_brand_search_view = {
    "key": "car_import_car_brand_search_view",
    "name": _("Car brands search"),
    "model": "car_import.carbrand",
    "menu_item": "car_import_menu_car_brands",
    "view_type": "search",
    "priority": 20,
    "module": "car_import",
    "body": {"search": {
        "search_fields": [
            {"name": ["name"], "string": _("Brand"), "widget": "text"},
            {"name": ["name_ar"], "string": _("Name (Arabic)"), "widget": "text"},
            {"name": ["aliases"], "string": _("Also matches"), "widget": "text"},
        ],
        "filters": [
            {"name": "on_website", "string": _("On the website"),
             "filter": {"field": "website_id", "operator": "is_null", "value": False}},
            {"name": "not_on_website", "string": _("Not on the website"),
             "filter": {"field": "website_id", "operator": "is_null", "value": True}},
        ],
    }},
}

# ── models ───────────────────────────────────────────────────────────────────
car_model_list_view = {
    "key": "car_import_car_model_list_view",
    "name": _("Car models"),
    "model": "car_import.carmodel",
    "menu_item": "car_import_menu_car_models",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {"tree": {"fields": [
        {"name": "brand", "widget": "relation", "displayField": "name", "string": _("Brand"), "width": "170"},
        {"name": "name", "widget": "text", "string": _("Model"), "width": "200"},
        {"name": "name_ar", "widget": "text", "string": _("Name (Arabic)"), "width": "170"},
        {"name": "aliases", "widget": "text", "string": _("Also matches"), "width": "240"},
        {"name": "website_id", "widget": "number", "string": _("Website id"), "width": "110"},
    ]}},
}

car_model_form_view = {
    "key": "car_import_car_model_form_view",
    "name": _("Car model"),
    "model": "car_import.carmodel",
    "menu_item": "car_import_menu_car_models",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {"header": {"actions_list": [], "actions": []}, "sheet": {"sections": [{"title": _("Model"), "groups": [
        {"fields": [
            {"name": "brand", "string": _("Brand"), "widget": "relation", "displayField": "name",
             "multiSelect": False, "required": True},
            {"name": "name", "string": _("Model"), "widget": "text", "required": True,
             "help": _("As the company writes it, e.g. C200 or GLA 180")},
            {"name": "name_ar", "string": _("Name (Arabic)"), "widget": "text"},
        ]},
        {"fields": [
            {"name": "aliases", "string": _("Also matches"), "widget": "text",
             "help": _("Other spellings, comma separated — e.g. C 200, C-200")},
            {"name": "website_id", "string": _("Website id"), "widget": "number",
             "help": _("Filled when the website lists are read. Empty: the website does not carry this model")},
            {"name": "display_name", "string": _("Brand and model"), "widget": "text", "readonly": True},
        ]},
    ]}]}},
}

car_model_search_view = {
    "key": "car_import_car_model_search_view",
    "name": _("Car models search"),
    "model": "car_import.carmodel",
    "menu_item": "car_import_menu_car_models",
    "view_type": "search",
    "priority": 20,
    "module": "car_import",
    "body": {"search": {
        "search_fields": [
            {"name": ["display_name"], "string": _("Brand and model"), "widget": "text"},
            {"name": ["name_ar"], "string": _("Name (Arabic)"), "widget": "text"},
            {"name": ["aliases"], "string": _("Also matches"), "widget": "text"},
        ],
        "filters": [
            {"name": "on_website", "string": _("On the website"),
             "filter": {"field": "website_id", "operator": "is_null", "value": False}},
            {"name": "not_on_website", "string": _("Not on the website"),
             "filter": {"field": "website_id", "operator": "is_null", "value": True}},
        ],
        "group_by": [{"name": "brand", "string": _("Brand")}],
    }},
}
