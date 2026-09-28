# -*- coding: utf-8 -*-
"""The company website inside Genie: the connection, its cars, its lists,
the requests its visitors send, and the log of every call between the two.

No status pills in any header (they win the 30px row and push the buttons
off screen — see quote_views.py); states are fields and ribbons.
"""
from django.utils.translation import gettext as _


def _kind(kind):
    return {"filters": {"operator": "and", "filters": [
        {"field": "kind", "operator": "eq", "value": kind},
        {"field": "is_active", "operator": "eq", "value": True}]}}


def _pick(name, string, kind, **extra):
    field = {"name": name, "string": string, "widget": "relation", "displayField": "name_en",
             "multiSelect": False, "domain": _kind(kind)}
    field.update(extra)
    return field


# ── the connection ───────────────────────────────────────────────────────────
_CONNECTION_ACTIONS = [
    {"name": "action_test_connection", "string": _("Test the connection"), "icon": "PlugZap",
     "type": "server", "as": "button", "variant": "primary", "view_type": ["form"]},
    {"name": "action_sync_lookups", "string": _("Read the website lists"), "icon": "ListChecks",
     "type": "server", "as": "button", "variant": "secondary", "view_type": ["form"]},
    {"name": "action_import_cars", "string": _("Import the website cars"), "icon": "Download",
     "type": "server", "as": "dropdown", "view_type": ["form"], "confirm_required": True,
     "confirm_message": _("Bring every website car into Genie? Genie's copies are replaced by the website's.")},
    {"name": "action_push_pending", "string": _("Send waiting changes to the website"), "icon": "Upload",
     "type": "server", "as": "dropdown", "view_type": ["form"], "confirm_required": True},
    {"name": "action_regenerate_inbound_key", "string": _("Issue a new key for the website"), "icon": "KeyRound",
     "type": "server", "as": "dropdown", "view_type": ["form"], "confirm_required": True,
     "confirm_message": _("The website stops being able to send leads and read tracking until the "
                          "developer puts the new key in. Continue?")},
]

website_connection_list_view = {
    "key": "car_import_website_connection_list_view",
    "name": _("Website connection"),
    "model": "car_import.websiteconnection",
    "menu_item": "car_import_menu_website_connection",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {"tree": {"fields": [
        {"name": "name", "widget": "text", "string": _("Website"), "width": "220"},
        {"name": "base_url", "widget": "text", "string": _("API URL"), "width": "280"},
        {"name": "push_enabled", "widget": "switch", "string": _("Sends to the website"), "width": "160"},
        {"name": "last_ok_at", "widget": "datetime", "string": _("Last successful call"), "width": "180"},
    ]}},
}

website_connection_form_view = {
    "key": "car_import_website_connection_form_view",
    "name": _("Website connection"),
    "model": "car_import.websiteconnection",
    "menu_item": "car_import_menu_website_connection",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions_list": [], "actions": _CONNECTION_ACTIONS},
        "sheet": {
            "sections": [
                {
                    "title": _("Genie → website (publishing cars)"),
                    "groups": [
                        {"fields": [
                            {"name": "name", "string": _("Website"), "widget": "text"},
                            {"name": "base_url", "string": _("Website API URL"), "widget": "text",
                             "help": _("https://khaledautomobilegmbh.de/api")},
                            {"name": "api_email", "string": _("Website API login (email)"), "widget": "text"},
                            {"name": "api_password", "string": _("Website API password"), "widget": "password"},
                        ]},
                        {"fields": [
                            {"name": "push_enabled", "string": _("Send changes to the website"), "widget": "switch"},
                            {"name": "import_new_cars_nightly", "string": _("Bring in cars added on the website"),
                             "widget": "switch"},
                        ]},
                    ],
                },
                {
                    "title": _("Website → Genie (leads and tracking)"),
                    "groups": [
                        {"fields": [
                            {"name": "inbound_api_key", "string": _("Key the website sends to Genie"),
                             "widget": "text", "readonly": True},
                            {"name": "leads_enabled", "string": _("Accept leads from the website"), "widget": "switch",
                             "help": _("POST https://<this Genie address>/api/website/leads")},
                            {"name": "tracking_enabled", "string": _("Answer tracking requests"), "widget": "switch",
                             "help": _("GET https://<this Genie address>/api/website/tracking?chassis_number=…")},
                        ]},
                    ],
                },
                {
                    "title": _("Status"),
                    "groups": [
                        {"fields": [
                            {"name": "last_ok_at", "string": _("Last successful call"), "widget": "datetime",
                             "readonly": True},
                            {"name": "token_obtained_at", "string": _("Logged in at"), "widget": "datetime",
                             "readonly": True},
                            {"name": "lookups_synced_at", "string": _("Lists synced at"), "widget": "datetime",
                             "readonly": True},
                            {"name": "cars_imported_at", "string": _("Cars imported at"), "widget": "datetime",
                             "readonly": True},
                        ]},
                        {"fields": [
                            {"name": "last_error", "string": _("Last error"), "widget": "textarea", "readonly": True},
                        ]},
                    ],
                },
            ],
        },
    },
}


# ── the cars ─────────────────────────────────────────────────────────────────
_CAR_ACTIONS = [
    {"name": "action_send_to_website", "string": _("Send to the website"), "icon": "Upload",
     "type": "server", "as": "button", "variant": "primary", "view_type": ["form", "list"]},
    {"name": "action_show", "string": _("Show on the website"), "icon": "Eye",
     "type": "server", "as": "dropdown", "view_type": ["form", "list"]},
    {"name": "action_hide", "string": _("Hide from the website"), "icon": "EyeOff",
     "type": "server", "as": "dropdown", "view_type": ["form", "list"]},
    {"name": "action_mark_sold", "string": _("Mark sold on the website"), "icon": "BadgeCheck",
     "type": "server", "as": "dropdown", "view_type": ["form", "list"], "confirm_required": True,
     "confirm_message": _("The website cannot undo «sold». Continue?")},
    {"name": "action_link_vehicle", "string": _("Link to a Genie car record"), "icon": "Link",
     "type": "server", "as": "dropdown", "view_type": ["form", "list"]},
]

website_car_list_view = {
    "key": "car_import_website_car_list_view",
    "name": _("Website cars"),
    "model": "car_import.websitecar",
    "menu_item": "car_import_menu_website_cars",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions": _CAR_ACTIONS},
        "tree": {"fields": [
            {"name": "website_id", "widget": "number", "string": _("Website id"), "width": "100"},
            {"name": "title_en", "widget": "text", "string": _("Title"), "width": "260"},
            {"name": "serial", "widget": "text", "string": _("Chassis number"), "width": "190"},
            {"name": "year", "widget": "number", "string": _("Year"), "width": "80"},
            {"name": "price", "widget": "number", "string": _("Price"), "width": "130"},
            {"name": "currency", "widget": "relation", "displayField": "code", "string": _("Currency"), "width": "90"},
            {"name": "location", "widget": "relation", "displayField": "name_en", "string": _("Location"), "width": "110"},
            {"name": "visible", "widget": "switch", "string": _("Shown"), "width": "90"},
            {"name": "website_status", "widget": "select", "string": _("Status on the website"), "width": "170"},
            {"name": "sync_state", "widget": "select", "string": _("Website sync"), "width": "170"},
            {"name": "needs_review", "widget": "switch", "string": _("Needs review"), "width": "120"},
        ]},
    },
}

website_car_form_view = {
    "key": "car_import_website_car_form_view",
    "name": _("Website car"),
    "model": "car_import.websitecar",
    "menu_item": "car_import_menu_website_cars",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {
        "header": {"actions_list": [], "actions": _CAR_ACTIONS},
        "sheet": {
            "ribbon": {
                "field_text": "sync_state",
                "color": {
                    "success": {"field": "sync_state", "operator": "eq", "value": "synced"},
                    "warning": {"field": "sync_state", "operator": "eq", "value": "pending"},
                    "danger": {"field": "sync_state", "operator": "eq", "value": "error"},
                },
            },
            "sections": [
                {
                    "title": _("The car"),
                    "groups": [
                        {"fields": [
                            {"name": "sync_state", "string": _("Website sync"), "widget": "select", "invisible": True},
                            {"name": "title_ar", "string": _("Title (Arabic)"), "widget": "text"},
                            {"name": "title_en", "string": _("Title (English)"), "widget": "text"},
                            _pick("brand", _("Brand"), "brand", required=True),
                            {"name": "model", "string": _("Model"), "widget": "relation", "displayField": "name_en",
                             "multiSelect": False, "required": True, "domain": _kind("model"),
                             "help": _("Must belong to the brand — the website refuses anything else")},
                            _pick("category", _("Category"), "category", required=True),
                            {"name": "year", "string": _("Model year"), "widget": "number", "required": True},
                            {"name": "serial", "string": _("Chassis number"), "widget": "text", "required": True},
                        ]},
                        {"fields": [
                            _pick("location", _("Car location"), "country", required=True,
                                  help=_("Egypt: the price is in Egyptian pounds. Germany or UAE: in euros")),
                            {"name": "price", "string": _("Price"), "widget": "number", "required": True},
                            {"name": "currency", "string": _("Currency"), "widget": "relation", "displayField": "code",
                             "multiSelect": False, "readonly": True},
                            {"name": "visible", "string": _("Shown on the website"), "widget": "switch"},
                            {"name": "website_status", "string": _("Status on the website"), "widget": "select",
                             "readonly": True},
                            {"name": "vehicle", "string": _("Car in Genie"), "widget": "relation",
                             "displayField": "name", "multiSelect": False,
                             "help": _("A paid deal on this car marks it sold on the website by itself")},
                        ]},
                    ],
                },
            ],
        },
        "tabs": [
                {
                    "title": _("Specification"),
                    "sections": [{"groups": [
                        {"fields": [
                            _pick("fuel", _("Fuel"), "fuel", required=True),
                            _pick("gearbox", _("Gearbox"), "gearbox", required=True),
                            _pick("bodytype", _("Body type"), "bodytype", required=True),
                            _pick("engine", _("Engine"), "engine", required=True),
                            _pick("origin", _("Origin"), "origin"),
                        ]},
                        {"fields": [
                            {"name": "seat", "string": _("Seats"), "widget": "select"},
                            {"name": "distance", "string": _("Mileage (km)"), "widget": "number"},
                            {"name": "video_link", "string": _("Video link"), "widget": "text"},
                            {"name": "extra_options", "string": _("Extra options"), "widget": "relation",
                             "displayField": "name_en", "multiSelect": True, "domain": _kind("extra_option")},
                        ]},
                    ]}],
                },
                {
                    "title": _("Description"),
                    "sections": [{"groups": [{"fields": [
                        {"name": "description_ar", "string": _("Description (Arabic)"), "widget": "textarea"},
                        {"name": "description_en", "string": _("Description (English)"), "widget": "textarea"},
                    ]}]}],
                },
                {
                    "title": _("Photos"),
                    "sections": [{"groups": [
                        {"fields": [
                            {"name": "site_image_url", "string": _("Main photo on the website"), "widget": "text",
                             "readonly": True},
                            {"name": "main_image", "string": _("New main photo"), "widget": "files",
                             "multiSelect": False, "accept": "image/*"},
                            {"name": "gallery", "string": _("New gallery photos"), "widget": "files",
                             "maxFiles": 30, "accept": "image/*"},
                        ]},
                    ]}],
                },
                {
                    "title": _("Website"),
                    "sections": [{"groups": [
                        {"fields": [
                            {"name": "website_id", "string": _("Website id"), "widget": "number", "readonly": True},
                            {"name": "odoo_id", "string": _("Old Odoo id"), "widget": "number", "readonly": True},
                            {"name": "last_synced_at", "string": _("Last synced"), "widget": "datetime",
                             "readonly": True},
                            {"name": "last_error", "string": _("Last sending error"), "widget": "textarea",
                             "readonly": True},
                        ]},
                        {"fields": [
                            {"name": "needs_review", "string": _("Needs review"), "widget": "switch"},
                            {"name": "review_reason", "string": _("Why"), "widget": "text"},
                        ]},
                    ]}],
                },
        ],
    },
}

website_car_search_view = {
    "key": "car_import_website_car_search_view",
    "name": _("Website cars search"),
    "model": "car_import.websitecar",
    "menu_item": "car_import_menu_website_cars",
    "view_type": "search",
    "priority": 20,
    "module": "car_import",
    "body": {
        "search": {
            "search_fields": [
                {"name": ["title_en"], "string": _("Title"), "widget": "text"},
                {"name": ["title_ar"], "string": _("Title (Arabic)"), "widget": "text"},
                {"name": ["serial"], "string": _("Chassis number"), "widget": "text"},
                {"name": ["brand__name_en"], "string": _("Brand"), "widget": "text"},
                {"name": ["model__name_en"], "string": _("Model"), "widget": "text"},
            ],
            "filters": [
                {"name": "shown", "string": _("Shown on the website"),
                 "filter": {"field": "visible", "operator": "eq", "value": True}},
                {"name": "hidden", "string": _("Hidden"),
                 "filter": {"field": "visible", "operator": "eq", "value": False}},
                {"name": "egypt", "string": _("In Egypt"),
                 "filter": {"field": "location__website_id", "operator": "eq", "value": 1}},
                {"name": "germany", "string": _("In Germany"),
                 "filter": {"field": "location__website_id", "operator": "eq", "value": 2}},
                {"name": "sold", "string": _("Sold"),
                 "filter": {"field": "website_status", "operator": "eq", "value": "sold"}},
                {"name": "unsent", "string": _("Waiting to be sent"),
                 "filter": {"field": "sync_state", "operator": "in", "value": ["pending", "error", "draft"]}},
                {"name": "review", "string": _("Needs review"),
                 "filter": {"field": "needs_review", "operator": "eq", "value": True}},
            ],
            "group_by": [
                {"name": "location", "string": _("Location")},
                {"name": "brand", "string": _("Brand")},
                {"name": "website_status", "string": _("Status on the website")},
                {"name": "sync_state", "string": _("Website sync")},
            ],
            "order_by": [
                {"name": "website_id", "string": _("Newest on the website"), "direction": "desc"},
                {"name": "price", "string": _("Most expensive"), "direction": "desc"},
            ],
        },
    },
}


# ── the lists ────────────────────────────────────────────────────────────────
website_lookup_list_view = {
    "key": "car_import_website_lookup_list_view",
    "name": _("Website lists"),
    "model": "car_import.websitelookup",
    "menu_item": "car_import_menu_website_lookups",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {"tree": {"fields": [
        {"name": "kind", "widget": "select", "string": _("List"), "width": "140"},
        {"name": "website_id", "widget": "number", "string": _("Website id"), "width": "100"},
        {"name": "name_en", "widget": "text", "string": _("Name (English)"), "width": "220"},
        {"name": "name_ar", "widget": "text", "string": _("Name (Arabic)"), "width": "220"},
        {"name": "aliases", "widget": "text", "string": _("Also matches"), "width": "220"},
        {"name": "is_active", "widget": "switch", "string": _("Still on the website"), "width": "150"},
    ]}},
}

website_lookup_form_view = {
    "key": "car_import_website_lookup_form_view",
    "name": _("Website list entry"),
    "model": "car_import.websitelookup",
    "menu_item": "car_import_menu_website_lookups",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {"sheet": {"sections": [{"title": _("Entry"), "groups": [
        {"fields": [
            {"name": "kind", "string": _("List"), "widget": "select", "readonly": True},
            {"name": "website_id", "string": _("Website id"), "widget": "number", "readonly": True},
            {"name": "name_en", "string": _("Name (English)"), "widget": "text", "readonly": True},
            {"name": "name_ar", "string": _("Name (Arabic)"), "widget": "text", "readonly": True},
        ]},
        {"fields": [
            {"name": "aliases", "string": _("Also matches"), "widget": "text"},
            {"name": "brand_website_id", "string": _("Brand id (models)"), "widget": "number", "readonly": True},
            {"name": "is_active", "string": _("Still on the website"), "widget": "switch", "readonly": True},
        ]},
    ]}]}},
}

website_lookup_search_view = {
    "key": "car_import_website_lookup_search_view",
    "name": _("Website lists search"),
    "model": "car_import.websitelookup",
    "menu_item": "car_import_menu_website_lookups",
    "view_type": "search",
    "priority": 20,
    "module": "car_import",
    "body": {"search": {
        "search_fields": [
            {"name": ["name_en"], "string": _("Name"), "widget": "text"},
            {"name": ["name_ar"], "string": _("Name (Arabic)"), "widget": "text"},
        ],
        "filters": [
            {"name": kind, "string": label, "filter": {"field": "kind", "operator": "eq", "value": kind}}
            for kind, label in (("brand", _("Brands")), ("model", _("Models")), ("fuel", _("Fuels")),
                                ("gearbox", _("Gearboxes")), ("bodytype", _("Body types")),
                                ("engine", _("Engines")), ("country", _("Locations")),
                                ("extra_option", _("Extra options")))
        ],
        "group_by": [{"name": "kind", "string": _("List")}],
    }},
}


# ── what visitors sent ───────────────────────────────────────────────────────
website_submission_list_view = {
    "key": "car_import_website_submission_list_view",
    "name": _("Website requests"),
    "model": "car_import.websitesubmission",
    "menu_item": "car_import_menu_website_requests",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {"tree": {"fields": [
        {"name": "created_at", "widget": "datetime", "string": _("Received"), "width": "160"},
        {"name": "form", "widget": "select", "string": _("Form"), "width": "170"},
        {"name": "name", "widget": "text", "string": _("Name"), "width": "180"},
        {"name": "phone", "widget": "text", "string": _("Phone"), "width": "150"},
        {"name": "car_wanted", "widget": "text", "string": _("Car asked about"), "width": "220"},
        {"name": "lead", "widget": "relation", "displayField": "name", "string": _("Lead"), "width": "220"},
        {"name": "is_duplicate", "widget": "switch", "string": _("Repeat"), "width": "90"},
    ]}},
}

website_submission_form_view = {
    "key": "car_import_website_submission_form_view",
    "name": _("Website request"),
    "model": "car_import.websitesubmission",
    "menu_item": "car_import_menu_website_requests",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {"sheet": {"sections": [{"title": _("The request"), "groups": [
        {"fields": [
            {"name": "form", "string": _("Form"), "widget": "select", "readonly": True},
            {"name": "name", "string": _("Name"), "widget": "text", "readonly": True},
            {"name": "phone", "string": _("Phone"), "widget": "text", "readonly": True},
            {"name": "email", "string": _("Email"), "widget": "text", "readonly": True},
            {"name": "car_wanted", "string": _("Car asked about"), "widget": "text", "readonly": True},
            {"name": "message", "string": _("Message"), "widget": "textarea", "readonly": True},
        ]},
        {"fields": [
            {"name": "lead", "string": _("Lead"), "widget": "relation", "displayField": "name",
             "multiSelect": False, "readonly": True},
            {"name": "partner", "string": _("Customer"), "widget": "relation", "displayField": "name",
             "multiSelect": False, "readonly": True},
            {"name": "website_car", "string": _("Website car"), "widget": "relation", "displayField": "title_en",
             "multiSelect": False, "readonly": True},
            {"name": "submission_id", "string": _("Website reference"), "widget": "text", "readonly": True},
            {"name": "is_duplicate", "string": _("Repeat of an earlier request"), "widget": "switch",
             "readonly": True},
            {"name": "created_at", "string": _("Received"), "widget": "datetime", "readonly": True},
        ]},
    ]}]}},
}


# ── the log ──────────────────────────────────────────────────────────────────
website_log_list_view = {
    "key": "car_import_website_log_list_view",
    "name": _("Website API log"),
    "model": "car_import.websiteapilog",
    "menu_item": "car_import_menu_website_log",
    "view_type": "list",
    "priority": 10,
    "module": "car_import",
    "body": {"tree": {"fields": [
        {"name": "created_at", "widget": "datetime", "string": _("When"), "width": "160"},
        {"name": "direction", "widget": "select", "string": _("Direction"), "width": "150"},
        {"name": "method", "widget": "text", "string": _("Method"), "width": "80"},
        {"name": "path", "widget": "text", "string": _("Path"), "width": "240"},
        {"name": "status_code", "widget": "number", "string": _("HTTP status"), "width": "100"},
        {"name": "ok", "widget": "switch", "string": _("Succeeded"), "width": "100"},
        {"name": "duration_ms", "widget": "number", "string": _("Took (ms)"), "width": "100"},
        {"name": "error", "widget": "text", "string": _("Error"), "width": "260"},
    ]}},
}

website_log_form_view = {
    "key": "car_import_website_log_form_view",
    "name": _("Website API call"),
    "model": "car_import.websiteapilog",
    "menu_item": "car_import_menu_website_log",
    "view_type": "form",
    "priority": 10,
    "module": "car_import",
    "body": {"sheet": {"sections": [{"title": _("The call"), "groups": [
        {"fields": [
            {"name": "direction", "string": _("Direction"), "widget": "select", "readonly": True},
            {"name": "method", "string": _("Method"), "widget": "text", "readonly": True},
            {"name": "path", "string": _("Path"), "widget": "text", "readonly": True},
            {"name": "status_code", "string": _("HTTP status"), "widget": "number", "readonly": True},
            {"name": "duration_ms", "string": _("Took (ms)"), "widget": "number", "readonly": True},
            {"name": "object_ref", "string": _("Record"), "widget": "text", "readonly": True},
        ]},
        {"fields": [
            {"name": "error", "string": _("Error"), "widget": "textarea", "readonly": True},
            {"name": "request_body", "string": _("Request"), "widget": "json", "readonly": True},
            {"name": "response_body", "string": _("Response"), "widget": "json", "readonly": True},
        ]},
    ]}]}},
}

website_log_search_view = {
    "key": "car_import_website_log_search_view",
    "name": _("Website API log search"),
    "model": "car_import.websiteapilog",
    "menu_item": "car_import_menu_website_log",
    "view_type": "search",
    "priority": 20,
    "module": "car_import",
    "body": {"search": {
        "search_fields": [{"name": ["path"], "string": _("Path"), "widget": "text"}],
        "filters": [
            {"name": "failed", "string": _("Failed"), "filter": {"field": "ok", "operator": "eq", "value": False}},
            {"name": "inbound", "string": _("Website → Genie"),
             "filter": {"field": "direction", "operator": "eq", "value": "in"}},
            {"name": "outbound", "string": _("Genie → website"),
             "filter": {"field": "direction", "operator": "eq", "value": "out"}},
        ],
        "group_by": [{"name": "direction", "string": _("Direction")}, {"name": "status_code", "string": _("HTTP status")}],
    }},
}
