# -*- coding: utf-8 -*-
"""Configuration screens — the point of moving the figures out of the code.

Deliberately plain list+form screens. The value is not the layout, it is that
a manager can change a fee, close a programme or publish a new exchange rate
without a developer, a deploy, or a conversation with us.
"""
from django.utils.translation import gettext as _


def _list(key, name, model, menu_item, fields):
    return {
        "key": key, "name": name, "model": model, "menu_item": menu_item,
        "view_type": "list", "priority": 10, "module": "car_import",
        "body": {"tree": {"fields": fields}},
    }


def _form(key, name, model, menu_item, sections):
    return {
        "key": key, "name": name, "model": model, "menu_item": menu_item,
        "view_type": "form", "priority": 10, "module": "car_import",
        "body": {"header": {"actions_list": [], "actions": []},
                 "sheet": {"sections": sections}},
    }


DATES = [
    {"name": "effective_from", "string": _("In force from"), "widget": "date"},
    {"name": "effective_to", "string": _("In force until"), "widget": "date"},
    {"name": "source_note", "string": _("Where this came from"), "widget": "text"},
]

# ── programmes ─────────────────────────────────────────────────────────────
car_import_program_list_view = _list(
    "car_import_program_list_view", "Import programmes", "car_import.importprogram",
    "car_import_menu_programs",
    [
        {"name": "sequence", "string": _("#"), "widget": "number", "width": "60"},
        {"name": "code", "string": _("Code"), "widget": "text", "width": "130"},
        {"name": "name", "string": _("Name"), "widget": "text", "width": "220"},
        {"name": "is_blocked", "string": _("Suspended"), "widget": "switch", "width": "110"},
        {"name": "requires_zero_km", "string": _("Zero km"), "widget": "switch", "width": "100"},
        {"name": "min_model_year", "string": _("Oldest year"), "widget": "number", "width": "110"},
        {"name": "max_cc", "string": _("Max cc"), "widget": "number", "width": "100"},
        {"name": "instalments_allowed", "string": _("Instalments"), "widget": "switch", "width": "110"},
    ])

car_import_program_form_view = _form(
    "car_import_program_form_view", "Import programme", "car_import.importprogram",
    "car_import_menu_programs",
    [
        {"title": _("The route"), "groups": [
            {"fields": [
                {"name": "code", "string": _("Code"), "widget": "text", "required": True},
                {"name": "name", "string": _("Name"), "widget": "text", "required": True},
                {"name": "name_en", "string": _("Name (English)"), "widget": "text"},
                {"name": "sequence", "string": _("Sequence"), "widget": "number"},
            ]},
            {"fields": [
                {"name": "is_blocked", "string": _("Suspended"), "widget": "switch"},
                {"name": "blocked_reason", "string": _("Why suspended"), "widget": "text"},
                {"name": "requires_management_approval", "string": _("Needs management approval"),
                 "widget": "switch"},
            ]},
        ]},
        {"title": _("What it allows"), "groups": [
            {"fields": [
                {"name": "requires_zero_km", "string": _("Must be brand new"), "widget": "switch"},
                {"name": "requires_current_model_year", "string": _("Must be this year's model"),
                 "widget": "switch"},
                {"name": "min_model_year", "string": _("Oldest model year"), "widget": "number"},
            ]},
            {"fields": [
                {"name": "max_cc", "string": _("Engine limit (cc)"), "widget": "number"},
                {"name": "instalments_allowed", "string": _("Instalments possible"), "widget": "switch"},
            ]},
        ]},
        {"title": _("Validity"), "groups": [{"fields": DATES},
                                            {"fields": [{"name": "notes", "string": _("Notes"),
                                                         "widget": "textarea"}]}]},
    ])

# ── fees ───────────────────────────────────────────────────────────────────
car_import_fee_list_view = _list(
    "car_import_fee_list_view", "Fee schedule", "car_import.feeschedule",
    "car_import_menu_fees",
    [
        {"name": "code", "string": _("Code"), "widget": "text", "width": "170"},
        {"name": "name", "string": _("Name"), "widget": "text", "width": "240"},
        {"name": "amount", "string": _("Amount"), "widget": "number", "width": "120"},
        {"name": "amount_to", "string": _("Up to"), "widget": "number", "width": "110"},
        {"name": "currency", "string": _("Currency"), "widget": "relation", "displayField": "code", "width": "90"},
        {"name": "applies_to", "string": _("Applies"), "widget": "select", "width": "140"},
        {"name": "quotable_to_customer", "string": _("May be quoted"), "widget": "switch", "width": "130"},
        {"name": "effective_from", "string": _("From"), "widget": "date", "width": "120"},
    ])

car_import_fee_form_view = _form(
    "car_import_fee_form_view", "Fee", "car_import.feeschedule", "car_import_menu_fees",
    [
        {"title": _("The charge"), "groups": [
            {"fields": [
                {"name": "code", "string": _("Code"), "widget": "text", "required": True},
                {"name": "name", "string": _("Name"), "widget": "text", "required": True},
                {"name": "amount", "string": _("Amount"), "widget": "number"},
                {"name": "amount_to", "string": _("Up to (for a range)"), "widget": "number"},
                {"name": "currency", "string": _("Currency"), "widget": "relation", "displayField": "code", "multiSelect": False},
            ]},
            {"fields": [
                {"name": "applies_to", "string": _("Applies"), "widget": "select"},
                # The licence cost itself is the client's own "never quote" rule.
                {"name": "quotable_to_customer", "string": _("May be quoted to a customer"),
                 "widget": "switch"},
                {"name": "notes", "string": _("Notes"), "widget": "textarea"},
            ]},
        ]},
        {"title": _("Validity"), "groups": [{"fields": DATES}]},
    ])

# ── financing ──────────────────────────────────────────────────────────────
car_import_financing_list_view = _list(
    "car_import_financing_list_view", "Financing plans", "car_import.financingplan",
    "car_import_menu_financing",
    [
        {"name": "code", "string": _("Code"), "widget": "text", "width": "170"},
        {"name": "name", "string": _("Name"), "widget": "text", "width": "220"},
        {"name": "available", "string": _("On offer"), "widget": "switch", "width": "110"},
        {"name": "down_payment_pct", "string": _("Down payment %"), "widget": "number", "width": "140"},
        {"name": "rate_pct_flat", "string": _("Rate % / year"), "widget": "number", "width": "130"},
        {"name": "cheques_required", "string": _("Cheques"), "widget": "switch", "width": "100"},
    ])

car_import_financing_form_view = _form(
    "car_import_financing_form_view", "Financing plan", "car_import.financingplan",
    "car_import_menu_financing",
    [
        {"title": _("The plan"), "groups": [
            {"fields": [
                {"name": "code", "string": _("Code"), "widget": "text", "required": True},
                {"name": "name", "string": _("Name"), "widget": "text", "required": True},
                {"name": "available", "string": _("On offer"), "widget": "switch"},
                {"name": "down_payment_pct", "string": _("Down payment %"), "widget": "number"},
                {"name": "rate_pct_flat", "string": _("Flat rate % per year"), "widget": "number"},
            ]},
            {"fields": [
                {"name": "cheques_required", "string": _("Cheques required"), "widget": "switch"},
                {"name": "first_instalment_note", "string": _("First instalment"), "widget": "text"},
                {"name": "covers", "string": _("What it covers"), "widget": "text"},
                {"name": "not_available_when", "string": _("Not available when"), "widget": "text"},
            ]},
        ]},
        {"title": _("Who computes the amount"), "groups": [
            {"fields": [
                # Reads as a sentence on purpose: it is the rule the assistant
                # quotes back when a customer asks "كام القسط؟".
                {"name": "amount_policy", "string": _("Policy"), "widget": "text"},
                {"name": "notes", "string": _("Notes"), "widget": "textarea"},
            ]},
            {"fields": DATES},
        ]},
    ])

# ── deposits, customs, price ranges — loaded, not typed ────────────────────
car_import_deposit_list_view = _list(
    "car_import_deposit_list_view", "Deposit values", "car_import.deposittier",
    "car_import_menu_deposits",
    [
        {"name": "make", "string": _("Make"), "widget": "text", "width": "140"},
        {"name": "model", "string": _("Model"), "widget": "text", "width": "140"},
        {"name": "model_year", "string": _("Year"), "widget": "number", "width": "90"},
        {"name": "tier", "string": _("Tier"), "widget": "select", "width": "120"},
        {"name": "region", "string": _("Region"), "widget": "select", "width": "150"},
        {"name": "deposit_usd", "string": _("Deposit (USD)"), "widget": "number", "width": "140"},
        {"name": "source_note", "string": _("Source"), "widget": "text", "width": "220"},
    ])

car_import_customs_list_view = _list(
    "car_import_customs_list_view", "Customs values", "car_import.customsvaluation",
    "car_import_menu_customs",
    [
        {"name": "make", "string": _("Make"), "widget": "text", "width": "140"},
        {"name": "model", "string": _("Model"), "widget": "text", "width": "140"},
        {"name": "model_year", "string": _("Year"), "widget": "number", "width": "90"},
        {"name": "value_eur", "string": _("Value (EUR)"), "widget": "number", "width": "140"},
        # Open question V1 lives in this column — visible, not hidden in a doc.
        {"name": "basis", "string": _("This number is"), "widget": "select", "width": "220"},
    ])

car_import_price_range_list_view = _list(
    "car_import_price_range_list_view", "Model price ranges", "car_import.modelpricerange",
    "car_import_menu_price_ranges",
    [
        {"name": "make", "string": _("Make"), "widget": "text", "width": "140"},
        {"name": "model", "string": _("Model"), "widget": "text", "width": "140"},
        {"name": "model_year", "string": _("Year"), "widget": "number", "width": "90"},
        {"name": "price_from_eur", "string": _("From (EUR)"), "widget": "number", "width": "130"},
        {"name": "price_to_eur", "string": _("To (EUR)"), "widget": "number", "width": "130"},
        {"name": "cc_rounded", "string": _("cc"), "widget": "number", "width": "90"},
        {"name": "hp", "string": _("hp"), "widget": "number", "width": "80"},
    ])

# ── tax and exchange ───────────────────────────────────────────────────────
car_import_tax_rule_list_view = _list(
    "car_import_tax_rule_list_view", "Tax rules", "car_import.taxrule",
    "car_import_menu_tax_rules",
    [
        {"name": "program", "string": _("Programme"), "widget": "relation",
         "displayField": "name", "width": "200"},
        {"name": "cc_min", "string": _("From (cc)"), "widget": "number", "width": "110"},
        {"name": "cc_max", "string": _("To (cc)"), "widget": "number", "width": "110"},
        {"name": "with_eur1", "string": _("With EUR 1"), "widget": "switch", "width": "120"},
        {"name": "rate_pct", "string": _("Rate %"), "widget": "number", "width": "110"},
        {"name": "effective_from", "string": _("From"), "widget": "date", "width": "120"},
    ])

car_import_fx_list_view = _list(
    "car_import_fx_list_view", "Exchange rates", "car_import.fxreference",
    "car_import_menu_fx",
    [
        {"name": "currency_from", "string": _("From"), "widget": "relation", "displayField": "code", "width": "90"},
        {"name": "currency_to", "string": _("To"), "widget": "relation", "displayField": "code", "width": "90"},
        {"name": "rate", "string": _("Rate"), "widget": "number", "width": "140"},
        {"name": "commission_pct_min", "string": _("Commission % from"), "widget": "number", "width": "150"},
        {"name": "commission_pct_max", "string": _("to"), "widget": "number", "width": "110"},
        {"name": "effective_from", "string": _("In force from"), "widget": "date", "width": "140"},
        {"name": "note", "string": _("Note"), "widget": "text", "width": "220"},
    ])

car_import_fx_form_view = _form(
    "car_import_fx_form_view", "Exchange rate", "car_import.fxreference", "car_import_menu_fx",
    [
        {"title": _("The rate of the day"), "groups": [
            {"fields": [
                {"name": "currency_from", "string": _("From"), "widget": "relation", "displayField": "code", "multiSelect": False},
                {"name": "currency_to", "string": _("To"), "widget": "relation", "displayField": "code", "multiSelect": False},
                {"name": "rate", "string": _("Rate"), "widget": "number", "required": True},
            ]},
            {"fields": [
                {"name": "commission_pct_min", "string": _("Conversion commission % from"),
                 "widget": "number"},
                {"name": "commission_pct_max", "string": _("… to"), "widget": "number"},
                {"name": "note", "string": _("Note"), "widget": "text"},
            ]},
        ]},
        {"title": _("Validity"), "groups": [{"fields": DATES}]},
    ])
