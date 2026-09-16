# -*- coding: utf-8 -*-
"""The car itself — one physical vehicle, not a catalogue item."""
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
                                {"name": "model_year", "string": _("Model year"), "widget": "number"},
                                {"name": "production_month", "string": _("Production month"), "widget": "text"},
                                {"name": "vin", "string": _("VIN"), "widget": "text",
                                 "help": _("17 characters — never shortened")},
                                # On a factory order this is the only identifier
                                # that exists before a VIN does, and the contract
                                # prints it. It has to live on the car so the
                                # contract, the annex and the supplier's
                                # confirmation cannot disagree about it.
                                {"name": "configuration_number", "string": _("Configuration number"),
                                 "widget": "text"},
                                {"name": "internal_reference", "string": _("Internal reference"),
                                 "widget": "text"},
                            ],
                        },
                        {
                            "fields": [
                                {"name": "cc", "string": _("Engine size (cc)"), "widget": "number",
                                 "help": _("Exact displacement from the papers — the tax band switches at 1600 and 2000")},
                                {"name": "hp", "string": _("Power (hp)"), "widget": "number"},
                                {"name": "fuel", "string": _("Fuel"), "widget": "text"},
                                {"name": "gearbox", "string": _("Gearbox"), "widget": "text"},
                                {"name": "colour_exterior", "string": _("Colour (outside)"), "widget": "text"},
                                {"name": "colour_interior", "string": _("Colour (inside)"), "widget": "text"},
                                {"name": "mileage_km", "string": _("Odometer (km)"), "widget": "number"},
                                {"name": "condition", "string": _("Condition"), "widget": "select"},
                                {"name": "accident_free", "string": _("Accident-free (فابريكة)"), "widget": "switch"},
                                {"name": "body", "string": _("Body"), "widget": "select"},
                                {"name": "upholstery", "string": _("Upholstery"), "widget": "text"},
                                {"name": "euro_norm", "string": _("EURO norm"), "widget": "text"},
                            ],
                        },
                    ],
                },
                {
                    "title": _("Origin and price"),
                    "groups": [
                        {
                            "fields": [
                                {"name": "country_built", "string": _("Built in"), "widget": "text"},
                                {"name": "built_for_eu", "string": _("Built for the EU market"), "widget": "switch"},
                                {"name": "eur1_eligible", "string": _("EUR 1 eligible"), "widget": "switch"},
                            ],
                        },
                        {
                            "fields": [
                                {"name": "listing_url", "string": _("Listing URL"), "widget": "text"},
                                {"name": "source_site", "string": _("Source"), "widget": "text"},
                                {"name": "dealer_name", "string": _("Dealer"), "widget": "text"},
                                {"name": "supplier_invoice_type", "string": _("Supplier invoice"), "widget": "select",
                                 "help": _("Gross invoices carry VAT we reclaim on export; net ones do not")},
                                {"name": "seller_is_dealer", "string": _("Sold by a dealer"), "widget": "switch"},
                                {"name": "vatable", "string": _("VAT recoverable"), "widget": "switch",
                                 "help": _("MwSt. ausweisbar — these rank first in a search")},
                                {"name": "price_gross_eur", "string": _("Listed price (EUR)"), "widget": "number"},
                                {"name": "price_net_eur", "string": _("Net of VAT (EUR)"), "widget": "number"},
                            ],
                        },
                    ],
                },
                {
                    "title": _("Where it came from"),
                    "groups": [
                        {"fields": [
                            {"name": "built_for_market", "string": _("Built for market"),
                             "widget": "text",
                             "help": _("Not the same as where it was built — EUR 1 turns on this")},
                            {"name": "export_port", "string": _("Export port"), "widget": "text"},
                        ]},
                        {"fields": [
                            # Cost data. The agents' group has no view permission
                            # on the supplier listing for the same reason.
                            {"name": "negotiated_discount_eur",
                             "string": _("Negotiated discount (EUR)"), "widget": "number"},
                        ]},
                    ],
                },
                {
                    "title": _("Options that decide the deposit tier"),
                    "groups": [
                        {
                            "fields": [
                                {"name": "has_panorama", "string": _("Panorama roof"), "widget": "switch"},
                                {"name": "has_sunroof", "string": _("Sunroof"), "widget": "switch"},
                                {"name": "has_electric_seats", "string": _("Electric seats"), "widget": "switch"},
                            ],
                        },
                        {
                            "fields": [
                                {"name": "has_electric_trunk", "string": _("Electric trunk"), "widget": "switch"},
                                {"name": "has_digital_cluster", "string": _("Digital cluster"), "widget": "switch"},
                                {"name": "has_leather_seats", "string": _("Leather seats"), "widget": "switch"},
                                {"name": "tier_override", "string": _("Tier override"), "widget": "select",
                                 "help": _("Any 3 of the 6 options make the car كاملة — set this only to disagree")},
                            ],
                        },
                    ],
                },
                {
                    # Stage 6 sends these to the customer. Until now the stage
                    # could send media and the car had nowhere to keep it, so the
                    # only copy of a walk-around video lived in a WhatsApp thread.
                    "title": _("Photos and documents"),
                    "groups": [
                        {"fields": [
                            {"name": "photos", "string": _("Photos"), "widget": "file"},
                            {"name": "walkaround_video", "string": _("Walk-around video"),
                             "widget": "file"},
                        ]},
                        {"fields": [
                            {"name": "car_card", "string": _("Car card"), "widget": "file"},
                            {"name": "vin_option_list", "string": _("VIN option list"),
                             "widget": "file"},
                            {"name": "inspection_report", "string": _("Inspection report"),
                             "widget": "textarea"},
                        ]},
                    ],
                },
                {
                    "title": _("Notes"),
                    "groups": [
                        {"fields": [{"name": "notes", "string": _("Notes"), "widget": "textarea"}]},
                    ],
                },
            ],
        },
    },
}
