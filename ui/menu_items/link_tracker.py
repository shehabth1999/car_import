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

#: The module this tree is filed under — deliberately NOT car_import.
#:
#: The side menu marks a top-level entry as open when its module equals the
#: `module=` of the page's address, and shows the sub-menu of the FIRST entry
#: with that module (project/web/src/themes/Rubick/SideMenu/side-menu.ts). So a
#: module can own one top-level menu, no more: filed under car_import, every
#: Link Tracker page lit up Car Import as well and showed Car Import's own
#: sub-menu.
#:
#: A module of its own is the honest answer, but an extension repository
#: carries exactly one module. Until the side menu matches by menu instead of
#: by module, this tree borrows the identity of an installed module that has
#: no menu and no screen of its own, so nothing else ever answers to its name.
#: The price: a sync limited to that module (`sync_menu_items --app …`) would
#: not find these entries in its files and would delete them — the full sync
#: every deploy runs puts them back.
MENU_MODULE = "aistudio_whatsapp"


def _name(en, ar=None):
    """A name fixed in both languages.

    Names are looked up in the catalog of the entry's MODULE, and this tree's
    module is a borrowed one (see MENU_MODULE) whose catalog has none of them —
    the fallback is the platform's merged catalog, where core's marketing
    module calls its own Link Tracker «متتبع الروابط» and "Delivery" is
    somebody else's word. A name that is already one string per language is
    stored as it is. "Link Tracker" and "UTMs" stay English in Arabic too:
    they are names the staff know.
    """
    return {"en": en, "ar": ar or en}


def _entry(en, ar, icon, model, sequence):
    return {
        "name": _name(en, ar),
        "icon": icon,
        "module": MENU_MODULE,
        "model": model,
        "view_types": "list,form",
        "sequence": sequence,
    }


def _group(en, ar, icon, sequence, children):
    return {
        "name": _name(en, ar),
        "icon": icon,
        "module": MENU_MODULE,
        "sequence": sequence,
        "children": children,
    }


menu_dict = {
    "car_import_link_tracker_menu": {
        "name": _name("Link Tracker"),
        "icon": "Link",
        "module": MENU_MODULE,
        "sequence": 16,
        "allowed_groups": ["car_import.management"],
        "children": {
            "car_import_menu_lt_utms": _group("UTMs", None, "Megaphone", 10, {
                "car_import_menu_lt_mediums": _entry(
                    "Mediums", "الوسايط", "Share2", "crm.utmmedium", 110),
                "car_import_menu_lt_sources": _entry(
                    "Sources", "المصادر", "Globe", "crm.utmsource", 120),
            }),
            "car_import_menu_lt_cars": _group("Cars", "العربيات", "CarFront", 20, {
                "car_import_menu_lt_car_brands": _entry(
                    "Car Brands", "ماركات العربيات", "Tag", "car_import.carbrand", 110),
                "car_import_menu_lt_car_models": _entry(
                    "Car Models", "موديلات العربيات", "Layers", "car_import.carmodel", 120),
                "car_import_menu_lt_car_model_years": _entry(
                    "Car Model Year", "سنة موديل العربية", "CalendarDays", "car_import.carmodelyear", 130),
                "car_import_menu_lt_car_colours": _entry(
                    "Car Color", "لون العربية", "Palette", "car_import.carcolour", 140),
                "car_import_menu_lt_car_trim_levels": _entry(
                    "Car Trim Level", "فئة العربية", "SlidersHorizontal", "car_import.cartrimlevel", 150),
                "car_import_menu_lt_car_buyers": _entry(
                    "Car Buyer", "مشتري العربية", "UserCheck", "car_import.carbuyer", 160),
            }),
            "car_import_menu_lt_delivery": _group("Delivery", "الشحن", "Ship", 30, {
                "car_import_menu_lt_arrival_ports": _entry(
                    "Arrival Ports", "مواني الوصول", "Anchor", "car_import.arrivalport", 110),
                "car_import_menu_lt_shipping_destinations": _entry(
                    "Shipping Destination", "وجهة الشحن", "MapPin", "car_import.shippingdestination", 120),
                "car_import_menu_lt_international_shippers": _entry(
                    "International Shippers", "شركات الشحن الدولي", "Ship", "car_import.internationalshipper", 130),
                # The ports the cars are loaded at; the name is Odoo's.
                "car_import_menu_lt_loading_ports": _entry(
                    "International Shipping", "الشحن الدولي", "Container", "car_import.loadingport", 140),
                "car_import_menu_lt_clearance_people": _entry(
                    "Custom Clearance Person/Employee", "شخص/موظف التخليص الجمركي", "Stamp",
                    "car_import.customsclearanceperson", 150),
            }),
            "car_import_menu_lt_opportunities": _group("Opportunities", "الفرص", "Target", 40, {
                "car_import_menu_lt_product_types": _entry(
                    "Product Types", "أنواع الطلب", "Package", "car_import.opportunityproducttype", 110),
            }),
            "car_import_menu_lt_salespersons": _group("Salespersons", "البياعين", "Users", 50, {
                "car_import_menu_lt_on_hold_salespeople": _entry(
                    "On-Hold Salespersons", "البياعين المعلّقين", "PauseCircle", "car_import.onholdsalesperson", 110),
            }),
            "car_import_menu_lt_blacklist": _group("Blacklist", "القايمة السودا", "Ban", 60, {
                "car_import_menu_lt_customers_blacklist": _entry(
                    "Customers Blacklist", "القايمة السودا للعملاء", "UserX", "car_import.blacklistedcustomer", 110),
            }),
        },
    },
}
