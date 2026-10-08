# -*- coding: utf-8 -*-
"""The screens of the Link Tracker menu: a list and a form for each of its entries —
Odoo's sixteen, and three the client asked for on 2026-10-07.

Plain on purpose. In the client's Odoo these are short lists an administrator
edits now and then, and that is what they are here; the column titles are
Odoo's own field labels, so nobody has to learn them twice.

Twelve entries are the new lists (models/picklists.py). The other four —
Mediums, Sources, Car Brands, Car Models — show tables that already have a
screen somewhere else, and get views of their own here only because a view
belongs to one menu item. Those four sit at priority 30, behind the original
screens' views: wherever the platform asks for "the list" or "the form" of a
model without naming a menu (a relation picker, a link to a record), the
lowest priority wins, and that has to stay the original. They are also shorter
than the originals — what a manager types; a brand's logo, its website number
and its place in the order are still on the full screen under Car Import.
"""
from django.utils.translation import gettext as _

#: Behind the views of the screens these tables already had (10, and 1 in crm).
SECOND_SCREEN = 30


def _list(key, name, model, menu_item, fields, priority=10):
    return {
        "key": key, "name": name, "model": model, "menu_item": menu_item,
        "view_type": "list", "priority": priority, "module": "car_import",
        "body": {"tree": {"fields": fields}},
    }


def _form(key, name, model, menu_item, groups, priority=10):
    return {
        "key": key, "name": name, "model": model, "menu_item": menu_item,
        "view_type": "form", "priority": priority, "module": "car_import",
        "body": {"header": {"actions_list": [], "actions": []},
                 "sheet": {"sections": [{"title": name, "groups": groups}]}},
    }


def _names(slug, model, menu_item, menu_name, record_name, label):
    """The list and the form of a list that is only a name."""
    return (
        _list(f"car_import_lt_{slug}_list_view", menu_name, model, menu_item,
              [{"name": "name", "widget": "text", "string": label, "width": "320"}]),
        _form(f"car_import_lt_{slug}_form_view", record_name, model, menu_item,
              [{"fields": [{"name": "name", "string": label, "widget": "text", "required": True}]}]),
    )


# ── UTMs ─────────────────────────────────────────────────────────────────────
# crm's own tables. Odoo also kept a medium on each source; crm.UtmSource has
# no such field, so there is none to show.
car_import_lt_medium_list_view = _list(
    "car_import_lt_medium_list_view", _("Mediums"), "crm.utmmedium", "car_import_menu_lt_mediums",
    [
        {"name": "name", "widget": "text", "string": _("Medium Name"), "width": "260"},
        {"name": "description", "widget": "text", "string": _("Description"), "width": "420"},
    ], priority=SECOND_SCREEN)

car_import_lt_medium_form_view = _form(
    "car_import_lt_medium_form_view", _("UTM Medium"), "crm.utmmedium", "car_import_menu_lt_mediums",
    [{"fields": [
        {"name": "name", "string": _("Medium Name"), "widget": "text", "required": True},
        {"name": "description", "string": _("Description"), "widget": "textarea", "rows": 2},
    ]}], priority=SECOND_SCREEN)

car_import_lt_source_list_view = _list(
    "car_import_lt_source_list_view", _("Sources"), "crm.utmsource", "car_import_menu_lt_sources",
    [
        {"name": "name", "widget": "text", "string": _("Source Name"), "width": "260"},
        {"name": "description", "widget": "text", "string": _("Description"), "width": "420"},
    ], priority=SECOND_SCREEN)

car_import_lt_source_form_view = _form(
    "car_import_lt_source_form_view", _("UTM Source"), "crm.utmsource", "car_import_menu_lt_sources",
    [{"fields": [
        {"name": "name", "string": _("Source Name"), "widget": "text", "required": True},
        {"name": "description", "string": _("Description"), "widget": "textarea", "rows": 2},
    ]}], priority=SECOND_SCREEN)

# ── Cars ─────────────────────────────────────────────────────────────────────
# The catalogue itself (models/catalogue.py): the same rows as Car Import →
# Cars and listings → Car brands / Car models, not a second list.
car_import_lt_car_brand_list_view = _list(
    "car_import_lt_car_brand_list_view", _("Car Brands"), "car_import.carbrand", "car_import_menu_lt_car_brands",
    [
        {"name": "name", "widget": "text", "string": _("Brand"), "width": "220"},
        {"name": "name_ar", "widget": "text", "string": _("Name (Arabic)"), "width": "200"},
        {"name": "aliases", "widget": "text", "string": _("Also matches"), "width": "320"},
    ], priority=SECOND_SCREEN)

car_import_lt_car_brand_form_view = _form(
    "car_import_lt_car_brand_form_view", _("Car brand"), "car_import.carbrand", "car_import_menu_lt_car_brands",
    [{"fields": [
        {"name": "name", "string": _("Brand"), "widget": "text", "required": True,
         "help": _("As it prints on a contract, e.g. Mercedes-Benz")},
        {"name": "name_ar", "string": _("Name (Arabic)"), "widget": "text"},
        {"name": "aliases", "string": _("Also matches"), "widget": "text",
         "help": _("Other spellings customers and adverts use, comma separated — they all find this brand")},
    ]}], priority=SECOND_SCREEN)

car_import_lt_car_model_list_view = _list(
    "car_import_lt_car_model_list_view", _("Car Models"), "car_import.carmodel", "car_import_menu_lt_car_models",
    [
        {"name": "brand", "widget": "relation", "displayField": "name", "string": _("Brand"), "width": "180"},
        {"name": "name", "widget": "text", "string": _("Model"), "width": "220"},
        {"name": "name_ar", "widget": "text", "string": _("Name (Arabic)"), "width": "200"},
        {"name": "aliases", "widget": "text", "string": _("Also matches"), "width": "280"},
    ], priority=SECOND_SCREEN)

car_import_lt_car_model_form_view = _form(
    "car_import_lt_car_model_form_view", _("Car model"), "car_import.carmodel", "car_import_menu_lt_car_models",
    [{"fields": [
        {"name": "brand", "string": _("Brand"), "widget": "relation", "displayField": "name",
         "multiSelect": False, "required": True},
        {"name": "name", "string": _("Model"), "widget": "text", "required": True,
         "help": _("As the company writes it, e.g. C200 or GLA 180")},
        {"name": "name_ar", "string": _("Name (Arabic)"), "widget": "text"},
        {"name": "aliases", "string": _("Also matches"), "widget": "text",
         "help": _("Other spellings, comma separated — e.g. C 200, C-200")},
    ]}], priority=SECOND_SCREEN)

# Not an Odoo entry: the client's request of 2026-10-07 — the brands built in
# the EU, which EUR 1 rests on. Each row points at a catalogue brand.
car_import_lt_eu_made_brand_list_view = _list(
    "car_import_lt_eu_made_brand_list_view", _("EU-Made Brands"), "car_import.eumadebrand",
    "car_import_menu_lt_eu_made_brands",
    [
        {"name": "brand", "widget": "relation", "displayField": "name", "string": _("Brand"), "width": "260"},
        {"name": "note", "widget": "text", "string": _("Note"), "width": "360"},
    ])

car_import_lt_eu_made_brand_form_view = _form(
    "car_import_lt_eu_made_brand_form_view", _("EU-made brand"), "car_import.eumadebrand",
    "car_import_menu_lt_eu_made_brands",
    [{"fields": [
        {"name": "brand", "string": _("Brand"), "widget": "relation", "displayField": "name",
         "multiSelect": False, "required": True,
         "help": _("A brand whose cars are built inside the European Union. Once this list has brands, the assistant and the team are warned when a car of any other brand is priced for EUR 1")},  # noqa: E501
        {"name": "note", "string": _("Note"), "widget": "text"},
    ]}])

car_import_lt_eu_made_brand_search_view = {
    "key": "car_import_lt_eu_made_brand_search_view",
    "name": _("EU-Made Brands"),
    "model": "car_import.eumadebrand",
    "menu_item": "car_import_menu_lt_eu_made_brands",
    "view_type": "search",
    "priority": 20,
    "module": "car_import",
    "body": {"search": {"search_fields": [
        {"name": ["brand__name", "brand__name_ar"], "string": _("Brand"), "widget": "text"},
    ]}},
}

car_import_lt_car_model_year_list_view, car_import_lt_car_model_year_form_view = _names(
    "car_model_year", "car_import.carmodelyear", "car_import_menu_lt_car_model_years",
    _("Car Model Year"), _("Car model year"), _("Model year"))

car_import_lt_car_colour_list_view, car_import_lt_car_colour_form_view = _names(
    "car_colour", "car_import.carcolour", "car_import_menu_lt_car_colours",
    _("Car Color"), _("Car colour"), _("Colour"))

car_import_lt_car_trim_level_list_view = _list(
    "car_import_lt_car_trim_level_list_view", _("Car Trim Level"), "car_import.cartrimlevel",
    "car_import_menu_lt_car_trim_levels",
    [{"name": "name", "widget": "text", "string": _("Trim Level"), "width": "320"}])

car_import_lt_car_trim_level_form_view = _form(
    "car_import_lt_car_trim_level_form_view", _("Car trim level"), "car_import.cartrimlevel",
    "car_import_menu_lt_car_trim_levels",
    [
        {"fields": [{"name": "name", "string": _("Trim Level"), "widget": "text", "required": True}]},
        {"fullWidth": True, "fields": [
            {"name": "options_features", "string": _("Options/Features"), "widget": "editor"},
        ]},
    ])

car_import_lt_car_buyer_list_view = _list(
    "car_import_lt_car_buyer_list_view", _("Car Buyer"), "car_import.carbuyer", "car_import_menu_lt_car_buyers",
    [
        {"name": "name", "widget": "text", "string": _("Owner Name"), "width": "240"},
        {"name": "company_name", "widget": "text", "string": _("Company name"), "width": "260"},
        {"name": "address", "widget": "text", "string": _("Address"), "width": "340"},
    ])

car_import_lt_car_buyer_form_view = _form(
    "car_import_lt_car_buyer_form_view", _("Car buyer"), "car_import.carbuyer", "car_import_menu_lt_car_buyers",
    [{"fields": [
        {"name": "name", "string": _("Owner Name"), "widget": "text", "required": True},
        {"name": "company_name", "string": _("Company name"), "widget": "text"},
        {"name": "address", "string": _("Address"), "widget": "text"},
    ]}])

# ── Delivery ─────────────────────────────────────────────────────────────────
car_import_lt_arrival_port_list_view, car_import_lt_arrival_port_form_view = _names(
    "arrival_port", "car_import.arrivalport", "car_import_menu_lt_arrival_ports",
    _("Arrival Ports"), _("Arrival port"), _("Arrival Port Name"))

car_import_lt_shipping_destination_list_view, car_import_lt_shipping_destination_form_view = _names(
    "shipping_destination", "car_import.shippingdestination", "car_import_menu_lt_shipping_destinations",
    _("Shipping Destination"), _("Shipping destination"), _("Destination"))

car_import_lt_international_shipper_list_view, car_import_lt_international_shipper_form_view = _names(
    "international_shipper", "car_import.internationalshipper", "car_import_menu_lt_international_shippers",
    _("International Shippers"), _("International shipper"), _("Shipper Name"))

# Odoo's "International Shipping" is the list of ports the cars are loaded at.
car_import_lt_loading_port_list_view, car_import_lt_loading_port_form_view = _names(
    "loading_port", "car_import.loadingport", "car_import_menu_lt_loading_ports",
    _("International Shipping"), _("Loading port"), _("Shipping Name"))

car_import_lt_clearance_person_list_view, car_import_lt_clearance_person_form_view = _names(
    "clearance_person", "car_import.customsclearanceperson", "car_import_menu_lt_clearance_people",
    _("Custom Clearance Person/Employee"), _("Customs clearance person"), _("Person/Employee"))

# ── Opportunities ────────────────────────────────────────────────────────────
car_import_lt_product_type_list_view, car_import_lt_product_type_form_view = _names(
    "product_type", "car_import.opportunityproducttype", "car_import_menu_lt_product_types",
    _("Product Types"), _("Product type"), _("Product Type Name"))

# ── Salespersons ─────────────────────────────────────────────────────────────
# The one list here that does something: whoever is on it gets no new lead from
# the assignment job (services/lead_assignment.py). The help text is the only
# place a manager reads that.
car_import_lt_on_hold_salesperson_list_view = _list(
    "car_import_lt_on_hold_salesperson_list_view", _("On-Hold Salespersons"), "car_import.onholdsalesperson",
    "car_import_menu_lt_on_hold_salespeople",
    [
        {"name": "user", "widget": "relation", "displayField": "name", "string": _("Salesperson"), "width": "320"},
        {"name": "hidden", "widget": "switch", "string": _("Hidden"), "width": "120"},
    ])

car_import_lt_on_hold_salesperson_form_view = _form(
    "car_import_lt_on_hold_salesperson_form_view", _("On-hold salesperson"), "car_import.onholdsalesperson",
    "car_import_menu_lt_on_hold_salespeople",
    [{"fields": [
        {"name": "user", "string": _("Salesperson"), "widget": "relation", "displayField": "name",
         "multiSelect": False, "required": True,
         "help": _("While a salesperson is on this list, the automatic lead assignment gives them no new leads. The leads they already have stay with them.")},
        {"name": "hidden", "string": _("Hidden"), "widget": "switch",
         "help": _("Kept as it was in Odoo. It has no effect here.")},
    ]}])

# This list has no `name` to search on, which is what a list searches by default.
car_import_lt_on_hold_salesperson_search_view = {
    "key": "car_import_lt_on_hold_salesperson_search_view",
    "name": _("On-Hold Salespersons"),
    "model": "car_import.onholdsalesperson",
    "menu_item": "car_import_menu_lt_on_hold_salespeople",
    "view_type": "search",
    "priority": 20,
    "module": "car_import",
    "body": {"search": {"search_fields": [
        {"name": ["user__name", "user__email"], "string": _("Salesperson"), "widget": "text"},
    ]}},
}

# ── Customs and initiatives ──────────────────────────────────────────────────
# The client, 2026-10-07: «مكان مخصص لقيمة الجمارك والمبادرات». The same two
# tables the assistant prices from (CustomsValuation, DepositTier) — until
# now read-only lists under Settings — here with a form, so management adds a
# model or corrects a figure where it keeps its other lists. A figure saved
# here is the one the next quotation uses.
_DATED = [
    {"name": "effective_from", "string": _("In force from"), "widget": "date"},
    {"name": "effective_to", "string": _("In force until"), "widget": "date",
     "help": _("Set it when the government changes the figure, and add the new figure as a new row")},
    {"name": "source_note", "string": _("Where this came from"), "widget": "text"},
]

car_import_lt_customs_value_list_view = _list(
    "car_import_lt_customs_value_list_view", _("Customs Values"), "car_import.customsvaluation",
    "car_import_menu_lt_customs_values",
    [
        {"name": "car_model", "string": _("Model"), "widget": "relation", "displayField": "display_name",
         "width": "240"},
        {"name": "model_year", "string": _("Year"), "widget": "number", "width": "90"},
        {"name": "value_eur", "string": _("Customs (EUR)"), "widget": "number", "width": "150"},
        {"name": "effective_from", "string": _("In force from"), "widget": "date", "width": "130"},
        {"name": "effective_to", "string": _("In force until"), "widget": "date", "width": "130"},
    ], priority=SECOND_SCREEN)

car_import_lt_customs_value_form_view = _form(
    "car_import_lt_customs_value_form_view", _("Customs value"), "car_import.customsvaluation",
    "car_import_menu_lt_customs_values",
    [
        {"fields": [
            {"name": "car_model", "string": _("Model"), "widget": "relation", "displayField": "display_name",
             "multiSelect": False, "required": True},
            {"name": "model_year", "string": _("Model year"), "widget": "number", "required": True,
             "help": _("A car one model year newer than the newest row takes this year's figure")},
            {"name": "value_eur", "string": _("Customs (EUR)"), "widget": "number", "required": True,
             "help": _("What a new car of this model pays in customs on a personal import, in euros")},
        ]},
        {"fields": _DATED},
    ], priority=SECOND_SCREEN)

car_import_lt_initiative_value_list_view = _list(
    "car_import_lt_initiative_value_list_view", _("Initiative Values"), "car_import.deposittier",
    "car_import_menu_lt_initiative_values",
    [
        {"name": "car_model", "string": _("Model"), "widget": "relation", "displayField": "display_name",
         "width": "240"},
        {"name": "model_year", "string": _("Year"), "widget": "number", "width": "90"},
        {"name": "tier", "string": _("Tier"), "widget": "select", "width": "120"},
        {"name": "region", "string": _("Residence"), "widget": "select", "width": "150"},
        {"name": "deposit_usd", "string": _("Initiative value (USD)"), "widget": "number", "width": "170"},
    ], priority=SECOND_SCREEN)

car_import_lt_initiative_value_form_view = _form(
    "car_import_lt_initiative_value_form_view", _("Initiative value"), "car_import.deposittier",
    "car_import_menu_lt_initiative_values",
    [
        {"fields": [
            {"name": "car_model", "string": _("Model"), "widget": "relation", "displayField": "display_name",
             "multiSelect": False, "required": True},
            {"name": "model_year", "string": _("Model year"), "widget": "number", "required": True},
            {"name": "tier", "string": _("Tier"), "widget": "select", "required": True},
            {"name": "region", "string": _("Residence"), "widget": "select", "required": True,
             "help": _("Inside Europe = lives in an EU country. UK and Turkey count as outside")},
            {"name": "deposit_usd", "string": _("Initiative value (USD)"), "widget": "number", "required": True,
             "help": _("The dollar deposit the initiative needs for this car")},
        ]},
        {"fields": _DATED},
    ], priority=SECOND_SCREEN)


def _model_search(slug, model, menu_item, name):
    """These two tables have no `name`, which is what a list searches by default."""
    return {
        "key": f"car_import_lt_{slug}_search_view", "name": name, "model": model, "menu_item": menu_item,
        "view_type": "search", "priority": 20, "module": "car_import",
        "body": {"search": {"search_fields": [
            {"name": ["car_model__display_name", "car_model__name_ar"], "string": _("Model"), "widget": "text"},
        ]}},
    }


car_import_lt_customs_value_search_view = _model_search(
    "customs_value", "car_import.customsvaluation", "car_import_menu_lt_customs_values", _("Customs Values"))
car_import_lt_initiative_value_search_view = _model_search(
    "initiative_value", "car_import.deposittier", "car_import_menu_lt_initiative_values", _("Initiative Values"))

# ── Blacklist ────────────────────────────────────────────────────────────────
car_import_lt_blacklisted_customer_list_view = _list(
    "car_import_lt_blacklisted_customer_list_view", _("Customers Blacklist"), "car_import.blacklistedcustomer",
    "car_import_menu_lt_customers_blacklist",
    [
        {"name": "name", "widget": "text", "string": _("Customer Name"), "width": "300"},
        {"name": "phone", "widget": "text", "string": _("Phone"), "width": "200"},
    ])

car_import_lt_blacklisted_customer_form_view = _form(
    "car_import_lt_blacklisted_customer_form_view", _("Blacklisted customer"), "car_import.blacklistedcustomer",
    "car_import_menu_lt_customers_blacklist",
    [{"fields": [
        {"name": "name", "string": _("Customer Name"), "widget": "text", "required": True},
        {"name": "phone", "string": _("Phone"), "widget": "text"},
    ]}])
