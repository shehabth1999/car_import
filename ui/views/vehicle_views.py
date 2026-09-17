# -*- coding: utf-8 -*-
"""The car itself — one physical vehicle, not a catalogue item.

Identity on top; the rest in tabs, because a car has forty fields and the
Germany team fills the first eight while the sales agent reads the last ten.
"""
from django.utils.translation import gettext as _

vehicle_list_view = {
    "key": "car_import_vehicle_list_view",
    "name": _("Cars"),
    "model": "car_import.vehicle",
    "menu_item": "car_import_menu_vehicles",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {
        "tree": {
            "fields": [
                {"name": "make", "widget": "text", "string": _("Make"), "width": "120"},
                {"name": "model", "widget": "text", "string": _("Model"), "width": "160"},
                {"name": "trim", "widget": "text", "string": _("Trim"), "width": "150"},
                {"name": "model_year", "widget": "number", "string": _("Year"), "width": "90"},
                {"name": "cc", "widget": "number", "string": _("cc"), "width": "90"},
                {"name": "vin", "widget": "text", "string": _("VIN"), "width": "190"},
                {"name": "mileage_km", "widget": "number", "string": _("km"), "width": "100"},
                {"name": "vatable", "widget": "switch", "string": _("VAT recoverable"), "width": "140"},
                {"name": "price_gross_eur", "widget": "number", "string": _("Listed (EUR)"), "width": "130"},
            ],
        },
    },
}

vehicle_form_view = {
    "key": "car_import_vehicle_form_view",
    "name": _("Car"),
    "model": "car_import.vehicle",
    "menu_item": "car_import_menu_vehicles",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {
        "sheet": {
            "sections": [
                {
                    "title": _("The car"),
                    "groups": [
                        {
                            "fields": [
                                {"name": "make", "string": _("Make"), "widget": "text", "required": True},
                                {"name": "model", "string": _("Model"), "widget": "text", "required": True},
                                {"name": "trim", "string": _("Trim"), "widget": "text"},
                                {"name": "model_year", "string": _("Model year"), "widget": "number",
                                 "help": _("The model year, not the registration year — the initiative rules read this one")},
                                {"name": "production_month", "string": _("Production month"), "widget": "text",
                                 "help": _("The manufacturer's two-year warranty counts from here")},
                            ],
                        },
                        {
                            "fields": [
                                {"name": "vin", "string": _("VIN"), "widget": "text",
                                 "help": _("17 characters — never shortened. The customs file and the VIN option list hang off it")},
                                {"name": "configuration_number", "string": _("Configuration number"),
                                 "widget": "text",
                                 "help": _("The manufacturer's build code. Annex 2 of the contract settles option disputes against it")},
                                {"name": "internal_reference", "string": _("Internal reference"),
                                 "widget": "text"},
                                {"name": "condition", "string": _("Condition"), "widget": "select"},
                                {"name": "accident_free", "string": _("Accident-free (فابريكة)"), "widget": "switch",
                                 "help": _("Original paint, no repairs. What the company promises the customer — the inspection report backs it")},
                            ],
                        },
                    ],
                },
            ],
            "footer": {
                "fields": [
                    {"name": "price_gross_eur", "string": _("Listed €"), "widget": "number", "highlight": True},
                    {"separator": "thin"},
                    {"name": "price_net_eur", "string": _("Net €"), "widget": "number"},
                    {"separator": "thin"},
                    {"name": "negotiated_discount_eur", "string": _("Discount €"), "widget": "number"},
                ],
                "position": "end",
            },
        },
        "tabs": [
            {
                "title": _("Specification"),
                "sections": [{
                    "title": "",
                    "groups": [
                        {"title": _("Engine and gearbox"), "fields": [
                            {"name": "cc", "string": _("Engine size (cc)"), "widget": "number",
                             "help": _("Exact displacement from the papers — the tax band switches at 1600 and 2000")},
                            {"name": "hp", "string": _("Power (hp)"), "widget": "number"},
                            {"name": "fuel", "string": _("Fuel"), "widget": "text"},
                            {"name": "gearbox", "string": _("Gearbox"), "widget": "text"},
                            {"name": "euro_norm", "string": _("EURO norm"), "widget": "text",
                             "help": _("Euro 6 / 6d — printed on the registration document")},
                            {"name": "mileage_km", "string": _("Odometer (km)"), "widget": "number",
                             "help": _("A used car above the customer's expectation is offered an alternative first")},
                        ]},
                        {"title": _("Body and colours"), "fields": [
                            {"name": "body", "string": _("Body"), "widget": "select"},
                            {"name": "colour_exterior", "string": _("Colour (outside)"), "widget": "text"},
                            {"name": "colour_interior", "string": _("Colour (inside)"), "widget": "text"},
                            {"name": "upholstery", "string": _("Upholstery"), "widget": "text"},
                        ]},
                    ],
                }],
            },
            {
                "title": _("Origin and price"),
                "sections": [{
                    "title": "",
                    "groups": [
                        {"title": _("Where it was built, and for whom"), "fields": [
                            {"name": "country_built", "string": _("Built in"), "widget": "text",
                             "help": _("Outside the EU needs management's approval — the save raises the request")},
                            {"name": "built_for_market", "string": _("Built for market"),
                             "widget": "text",
                             "help": _("Not the same as where it was built — EUR 1 turns on this")},
                            {"name": "built_for_eu", "string": _("Built for the EU market"), "widget": "switch"},
                            {"name": "eur1_eligible", "string": _("EUR 1 eligible"), "widget": "switch",
                             "help": _("Proof of EU origin — a lower customs rate for the customer")},
                            {"name": "export_port", "string": _("Export port"), "widget": "text"},
                        ]},
                        {"title": _("The German side"), "fields": [
                            {"name": "listing_url", "string": _("Listing URL"), "widget": "url"},
                            {"name": "source_site", "string": _("Source"), "widget": "text"},
                            {"name": "dealer_name", "string": _("Dealer"), "widget": "text"},
                            {"name": "seller_is_dealer", "string": _("Sold by a dealer"), "widget": "switch",
                             "help": _("A private seller cannot issue a VAT invoice — nothing to reclaim")},
                            {"name": "supplier_invoice_type", "string": _("Supplier invoice"), "widget": "select",
                             "help": _("Gross invoices carry VAT we reclaim on export; net ones do not")},
                            {"name": "vatable", "string": _("VAT recoverable"), "widget": "switch",
                             "onChange": True,
                             "help": _("MwSt. ausweisbar — these rank first in a search, and the net price recomputes")},
                            {"name": "price_gross_eur", "string": _("Listed price (EUR)"), "widget": "number",
                             "onChange": True,
                             "help": _("The advert's number. Cost data — sales agents never see this screen")},
                            {"name": "price_net_eur", "string": _("Net of VAT (EUR)"), "widget": "number",
                             "help": _("Gross ÷ 1.19 when VAT is recoverable; equal to gross otherwise")},
                            {"name": "negotiated_discount_eur",
                             "string": _("Negotiated discount (EUR)"), "widget": "number",
                             "help": _("What the Germany team got off the advert. Above 500 € it needs management")},
                        ]},
                    ],
                }],
            },
            {
                "title": _("Options and tier"),
                "sections": [{
                    "title": _("Any three of the six make the car كاملة — the deposit tier follows"),
                    "groups": [
                        {"fields": [
                            {"name": "has_panorama", "string": _("Panorama roof"), "widget": "switch"},
                            {"name": "has_sunroof", "string": _("Sunroof"), "widget": "switch"},
                            {"name": "has_electric_seats", "string": _("Electric seats"), "widget": "switch"},
                        ]},
                        {"fields": [
                            {"name": "has_electric_trunk", "string": _("Electric trunk"), "widget": "switch"},
                            {"name": "has_digital_cluster", "string": _("Digital cluster"), "widget": "switch"},
                            {"name": "has_leather_seats", "string": _("Leather seats"), "widget": "switch"},
                            {"name": "tier_override", "string": _("Tier override"), "widget": "select",
                             "help": _("Set this only to disagree with the count")},
                        ]},
                    ],
                }],
            },
            {
                "title": _("Photos and documents"),
                "sections": [{
                    "title": "",
                    "groups": [
                        {"title": _("What the customer is shown"), "fields": [
                            {"name": "photos", "string": _("Photos"), "widget": "files", "maxFiles": 40,
                             "help": _("From the Berlin showroom — the stage 'arrived at the showroom' sends these")},
                            {"name": "walkaround_video", "string": _("Walk-around video"),
                             "widget": "file"},
                        ]},
                        {"title": _("What the paperwork needs"), "fields": [
                            {"name": "car_card", "string": _("Car card"), "widget": "file"},
                            {"name": "vin_option_list", "string": _("VIN option list"),
                             "widget": "file",
                             "help": _("The manufacturer's list of everything built into this VIN")},
                            {"name": "inspection_report", "string": _("Inspection report"),
                             "widget": "textarea", "rows": 4,
                             "help": _("Before shipping. A car that fails is replaced with the same specification")},
                        ]},
                    ],
                }],
            },
            {
                "title": _("Notes"),
                "sections": [{
                    "title": "",
                    "groups": [{"fullWidth": True, "fields": [
                        {"name": "notes", "string": _("Notes"), "widget": "textarea", "rows": 5},
                    ]}],
                }],
            },
        ],
    },
}
