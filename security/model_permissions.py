# -*- coding: utf-8 -*-
"""
Access rights for car_import.
Format: [view, add, change, delete].
"""

VIEW_ONLY = [1, 0, 0, 0]
MANAGE = [1, 1, 1, 0]      # create and edit, never delete — a deal is history
FULL = [1, 1, 1, 1]

MODEL_PERMISSIONS = [
    # ── the deal ────────────────────────────────────────────────────────────
    {'model': 'car_import.cardeal', 'group': 'car_import.sales_agent', 'permissions': MANAGE},
    {'model': 'car_import.cardeal', 'group': 'car_import.sales_manager', 'permissions': MANAGE},
    {'model': 'car_import.cardeal', 'group': 'car_import.operations', 'permissions': MANAGE},
    {'model': 'car_import.cardeal', 'group': 'car_import.germany_team', 'permissions': [1, 0, 1, 0]},
    {'model': 'car_import.cardeal', 'group': 'car_import.showroom', 'permissions': VIEW_ONLY},
    {'model': 'car_import.cardeal', 'group': 'car_import.management', 'permissions': FULL},

    # ── the car ─────────────────────────────────────────────────────────────
    {'model': 'car_import.vehicle', 'group': 'car_import.sales_agent', 'permissions': VIEW_ONLY},
    {'model': 'car_import.vehicle', 'group': 'car_import.sales_manager', 'permissions': MANAGE},
    {'model': 'car_import.vehicle', 'group': 'car_import.germany_team', 'permissions': MANAGE},
    {'model': 'car_import.vehicle', 'group': 'car_import.operations', 'permissions': VIEW_ONLY},
    {'model': 'car_import.vehicle', 'group': 'car_import.management', 'permissions': FULL},

    # ── stages and their messages: ops and management only ──────────────────
    {'model': 'car_import.importstage', 'group': 'car_import.sales_agent', 'permissions': VIEW_ONLY},
    {'model': 'car_import.importstage', 'group': 'car_import.operations', 'permissions': MANAGE},
    {'model': 'car_import.importstage', 'group': 'car_import.management', 'permissions': FULL},

    # ── supplier listings carry the German purchase price ───────────────────
    # Deliberately NOT granted to sales_agent: that price is cost data, and the
    # brief makes hiding it from agents a contractual obligation.
    {'model': 'car_import.supplierlisting', 'group': 'car_import.sales_manager', 'permissions': MANAGE},
    {'model': 'car_import.supplierlisting', 'group': 'car_import.germany_team', 'permissions': MANAGE},
    {'model': 'car_import.supplierlisting', 'group': 'car_import.management', 'permissions': FULL},

    # ── the reference tables: management owns the numbers ───────────────────
    # Sales managers may READ the deposits, customs values and price ranges —
    # they quote from them — but nobody except management may change a figure.
    {'model': 'car_import.importprogram', 'group': 'car_import.management', 'permissions': FULL},
    {'model': 'car_import.taxrule', 'group': 'car_import.management', 'permissions': FULL},
    {'model': 'car_import.eur1rule', 'group': 'car_import.management', 'permissions': FULL},
    {'model': 'car_import.feeschedule', 'group': 'car_import.management', 'permissions': FULL},
    {'model': 'car_import.financingplan', 'group': 'car_import.management', 'permissions': FULL},
    {'model': 'car_import.firstownerdiscount', 'group': 'car_import.management', 'permissions': FULL},
    {'model': 'car_import.deposittier', 'group': 'car_import.management', 'permissions': FULL},
    {'model': 'car_import.deposittier', 'group': 'car_import.sales_manager', 'permissions': VIEW_ONLY},
    {'model': 'car_import.customsvaluation', 'group': 'car_import.management', 'permissions': FULL},
    {'model': 'car_import.customsvaluation', 'group': 'car_import.sales_manager', 'permissions': VIEW_ONLY},
    {'model': 'car_import.modelpricerange', 'group': 'car_import.management', 'permissions': FULL},
    {'model': 'car_import.modelpricerange', 'group': 'car_import.sales_manager', 'permissions': VIEW_ONLY},
    {'model': 'car_import.fxreference', 'group': 'car_import.management', 'permissions': FULL},
    {'model': 'car_import.fxreference', 'group': 'car_import.sales_manager', 'permissions': VIEW_ONLY},
    # The bands ARE the price list. A sales manager reads them — they have to,
    # to explain a deposit — and only management moves a percentage.
    {'model': 'car_import.pricingband', 'group': 'car_import.management', 'permissions': FULL},
    {'model': 'car_import.pricingband', 'group': 'car_import.sales_manager', 'permissions': VIEW_ONLY},
    {'model': 'car_import.pricingband', 'group': 'car_import.sales_agent', 'permissions': VIEW_ONLY},

    # ── quotations ──────────────────────────────────────────────────────────
    # An agent writes offers; nobody deletes one. A quote that vanishes is a
    # price the company can no longer prove it gave.
    {'model': 'car_import.quote', 'group': 'car_import.sales_agent', 'permissions': MANAGE},
    {'model': 'car_import.quote', 'group': 'car_import.sales_manager', 'permissions': MANAGE},
    {'model': 'car_import.quote', 'group': 'car_import.operations', 'permissions': VIEW_ONLY},
    {'model': 'car_import.quote', 'group': 'car_import.management', 'permissions': FULL},
    {'model': 'car_import.quoteline', 'group': 'car_import.sales_agent', 'permissions': VIEW_ONLY},
    {'model': 'car_import.quoteline', 'group': 'car_import.sales_manager', 'permissions': VIEW_ONLY},
    {'model': 'car_import.quoteline', 'group': 'car_import.operations', 'permissions': VIEW_ONLY},
    {'model': 'car_import.quoteline', 'group': 'car_import.management', 'permissions': FULL},

    # ── contracts ───────────────────────────────────────────────────────────
    # An agent fills and generates one; nobody deletes one, because a generated
    # contract is evidence of what was agreed.
    {'model': 'car_import.contract', 'group': 'car_import.sales_agent', 'permissions': MANAGE},
    {'model': 'car_import.contract', 'group': 'car_import.sales_manager', 'permissions': MANAGE},
    {'model': 'car_import.contract', 'group': 'car_import.operations', 'permissions': MANAGE},
    {'model': 'car_import.contract', 'group': 'car_import.management', 'permissions': FULL},
    # The lawyer's wording: everybody reads it, only management replaces it.
    {'model': 'car_import.contracttemplate', 'group': 'car_import.sales_agent',
     'permissions': VIEW_ONLY},
    {'model': 'car_import.contracttemplate', 'group': 'car_import.sales_manager',
     'permissions': VIEW_ONLY},
    {'model': 'car_import.contracttemplate', 'group': 'car_import.operations',
     'permissions': VIEW_ONLY},
    {'model': 'car_import.contracttemplate', 'group': 'car_import.management',
     'permissions': FULL},

    # ── paperwork ───────────────────────────────────────────────────────────
    {'model': 'car_import.documentrequirement', 'group': 'car_import.management', 'permissions': FULL},
    {'model': 'car_import.documentrequirement', 'group': 'car_import.operations', 'permissions': MANAGE},
    {'model': 'car_import.dealdocument', 'group': 'car_import.sales_agent', 'permissions': MANAGE},
    {'model': 'car_import.dealdocument', 'group': 'car_import.sales_manager', 'permissions': MANAGE},
    {'model': 'car_import.dealdocument', 'group': 'car_import.operations', 'permissions': MANAGE},
    {'model': 'car_import.dealdocument', 'group': 'car_import.management', 'permissions': FULL},

    # ── initiatives ─────────────────────────────────────────────────────────
    {'model': 'car_import.initiative', 'group': 'car_import.sales_agent', 'permissions': VIEW_ONLY},
    {'model': 'car_import.initiative', 'group': 'car_import.sales_manager', 'permissions': MANAGE},
    {'model': 'car_import.initiative', 'group': 'car_import.management', 'permissions': FULL},

    # ── the company's own two markets ──────────────────────────────
    {'model': 'car_import.showroomlisting', 'group': 'car_import.sales_agent', 'permissions': VIEW_ONLY},
    {'model': 'car_import.showroomlisting', 'group': 'car_import.showroom', 'permissions': MANAGE},
    {'model': 'car_import.showroomlisting', 'group': 'car_import.sales_manager', 'permissions': MANAGE},
    {'model': 'car_import.showroomlisting', 'group': 'car_import.management', 'permissions': FULL},
    {'model': 'car_import.initiativelisting', 'group': 'car_import.sales_agent', 'permissions': VIEW_ONLY},
    {'model': 'car_import.initiativelisting', 'group': 'car_import.sales_manager', 'permissions': MANAGE},
    {'model': 'car_import.initiativelisting', 'group': 'car_import.management', 'permissions': FULL},

    # ── call recordings: internal, and an agent never deletes one ──────
    {'model': 'car_import.callrecording', 'group': 'car_import.sales_manager', 'permissions': MANAGE},
    {'model': 'car_import.callrecording', 'group': 'car_import.operations', 'permissions': MANAGE},
    {'model': 'car_import.callrecording', 'group': 'car_import.management', 'permissions': FULL},

    # ── the log is evidence: nobody edits it ────────────────────────────────
    {'model': 'car_import.stagechangelog', 'group': 'car_import.sales_agent', 'permissions': VIEW_ONLY},
    {'model': 'car_import.stagechangelog', 'group': 'car_import.sales_manager', 'permissions': VIEW_ONLY},
    {'model': 'car_import.stagechangelog', 'group': 'car_import.operations', 'permissions': VIEW_ONLY},
    {'model': 'car_import.stagechangelog', 'group': 'car_import.management', 'permissions': VIEW_ONLY},
]
