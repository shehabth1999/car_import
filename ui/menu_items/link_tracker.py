# -*- coding: utf-8 -*-
"""The Link Tracker menu: the client's Odoo configuration menu, entry for entry.

In their Odoo "Link Tracker" is not a link tracker. It is the top menu where an
administrator keeps every pick-list — the sources a lead comes from, the years
and colours of a car, the ports, who is on hold, who is blacklisted. Same six
groups, same entries, same order and the same English names here, so the
people who kept those lists find them where they left them.

Management only, and said once, on the root: a restriction on a menu item
covers everything under it (`MenuItem.is_accessible_by` walks up the tree).

Four entries open a table that already has a screen: Mediums and Sources
(crm → Configuration), Car Brands and Car Models (Car Import → Cars and
listings). They are the same rows, not copies. Every entry's `sequence` is
above those older screens' on purpose: where the platform needs "the menu item
of this model" — the link to a brand, to a source — it takes the lowest
sequence (`MenuItem.get_url_for_model`), and that must keep landing on the
screen its reader may open, not on this one.

The screens are in ui/views/link_tracker_views.py.
"""
from django.utils.translation import gettext as _


def _as_is(name):
    """A name the staff know in English, kept in English in Arabic too.

    Repeating the English in the catalog is not enough. The menu sync reads
    "same as the source" as "not translated" and falls back to the platform's
    merged catalog — where core's marketing module calls its own Link Tracker
    «متتبع الروابط». A name that is already one string per language is stored
    as it is.
    """
    return {"en": name, "ar": name}


menu_dict = {
    "car_import_link_tracker_menu": {
        "name": _as_is(_("Link Tracker")),
        "icon": "Link",
        "module": "car_import",
        "sequence": 16,
        "allowed_groups": ["car_import.management"],
        "children": {
            # ------------------------------------------------------------- UTMs
            "car_import_menu_lt_utms": {
                "name": _as_is(_("UTMs")),
                "icon": "Megaphone",
                "module": "car_import",
                "sequence": 10,
                "children": {
                    "car_import_menu_lt_mediums": {
                        "name": _("Mediums"),
                        "icon": "Share2",
                        "module": "car_import",
                        "model": "crm.utmmedium",
                        "view_types": "list,form",
                        "sequence": 110,
                    },
                    "car_import_menu_lt_sources": {
                        "name": _("Sources"),
                        "icon": "Globe",
                        "module": "car_import",
                        "model": "crm.utmsource",
                        "view_types": "list,form",
                        "sequence": 120,
                    },
                },
            },
            # ------------------------------------------------------------- Cars
            "car_import_menu_lt_cars": {
                "name": _("Cars"),
                "icon": "CarFront",
                "module": "car_import",
                "sequence": 20,
                "children": {
                    "car_import_menu_lt_car_brands": {
                        "name": _("Car Brands"),
                        "icon": "Tag",
                        "module": "car_import",
                        "model": "car_import.carbrand",
                        "view_types": "list,form",
                        "sequence": 110,
                    },
                    "car_import_menu_lt_car_models": {
                        "name": _("Car Models"),
                        "icon": "Layers",
                        "module": "car_import",
                        "model": "car_import.carmodel",
                        "view_types": "list,form",
                        "sequence": 120,
                    },
                    "car_import_menu_lt_car_model_years": {
                        "name": _("Car Model Year"),
                        "icon": "CalendarDays",
                        "module": "car_import",
                        "model": "car_import.carmodelyear",
                        "view_types": "list,form",
                        "sequence": 130,
                    },
                    "car_import_menu_lt_car_colours": {
                        "name": _("Car Color"),
                        "icon": "Palette",
                        "module": "car_import",
                        "model": "car_import.carcolour",
                        "view_types": "list,form",
                        "sequence": 140,
                    },
                    "car_import_menu_lt_car_trim_levels": {
                        "name": _("Car Trim Level"),
                        "icon": "SlidersHorizontal",
                        "module": "car_import",
                        "model": "car_import.cartrimlevel",
                        "view_types": "list,form",
                        "sequence": 150,
                    },
                    "car_import_menu_lt_car_buyers": {
                        "name": _("Car Buyer"),
                        "icon": "UserCheck",
                        "module": "car_import",
                        "model": "car_import.carbuyer",
                        "view_types": "list,form",
                        "sequence": 160,
                    },
                },
            },
            # --------------------------------------------------------- Delivery
            "car_import_menu_lt_delivery": {
                "name": _("Delivery"),
                "icon": "Ship",
                "module": "car_import",
                "sequence": 30,
                "children": {
                    "car_import_menu_lt_arrival_ports": {
                        "name": _("Arrival Ports"),
                        "icon": "Anchor",
                        "module": "car_import",
                        "model": "car_import.arrivalport",
                        "view_types": "list,form",
                        "sequence": 110,
                    },
                    "car_import_menu_lt_shipping_destinations": {
                        "name": _("Shipping Destination"),
                        "icon": "MapPin",
                        "module": "car_import",
                        "model": "car_import.shippingdestination",
                        "view_types": "list,form",
                        "sequence": 120,
                    },
                    "car_import_menu_lt_international_shippers": {
                        "name": _("International Shippers"),
                        "icon": "Ship",
                        "module": "car_import",
                        "model": "car_import.internationalshipper",
                        "view_types": "list,form",
                        "sequence": 130,
                    },
                    # The ports the cars are loaded at; the name is Odoo's.
                    "car_import_menu_lt_loading_ports": {
                        "name": _("International Shipping"),
                        "icon": "Container",
                        "module": "car_import",
                        "model": "car_import.loadingport",
                        "view_types": "list,form",
                        "sequence": 140,
                    },
                    "car_import_menu_lt_clearance_people": {
                        "name": _("Custom Clearance Person/Employee"),
                        "icon": "Stamp",
                        "module": "car_import",
                        "model": "car_import.customsclearanceperson",
                        "view_types": "list,form",
                        "sequence": 150,
                    },
                },
            },
            # ---------------------------------------------------- Opportunities
            "car_import_menu_lt_opportunities": {
                "name": _("Opportunities"),
                "icon": "Target",
                "module": "car_import",
                "sequence": 40,
                "children": {
                    "car_import_menu_lt_product_types": {
                        "name": _("Product Types"),
                        "icon": "Package",
                        "module": "car_import",
                        "model": "car_import.opportunityproducttype",
                        "view_types": "list,form",
                        "sequence": 110,
                    },
                },
            },
            # ----------------------------------------------------- Salespersons
            "car_import_menu_lt_salespersons": {
                "name": _("Salespersons"),
                "icon": "Users",
                "module": "car_import",
                "sequence": 50,
                "children": {
                    "car_import_menu_lt_on_hold_salespeople": {
                        "name": _("On-Hold Salespersons"),
                        "icon": "PauseCircle",
                        "module": "car_import",
                        "model": "car_import.onholdsalesperson",
                        "view_types": "list,form",
                        "sequence": 110,
                    },
                },
            },
            # -------------------------------------------------------- Blacklist
            "car_import_menu_lt_blacklist": {
                "name": _("Blacklist"),
                "icon": "Ban",
                "module": "car_import",
                "sequence": 60,
                "children": {
                    "car_import_menu_lt_customers_blacklist": {
                        "name": _("Customers Blacklist"),
                        "icon": "UserX",
                        "module": "car_import",
                        "model": "car_import.blacklistedcustomer",
                        "view_types": "list,form",
                        "sequence": 110,
                    },
                },
            },
        },
    },
}
