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

    # ── the log is evidence: nobody edits it ────────────────────────────────
    {'model': 'car_import.stagechangelog', 'group': 'car_import.sales_agent', 'permissions': VIEW_ONLY},
    {'model': 'car_import.stagechangelog', 'group': 'car_import.sales_manager', 'permissions': VIEW_ONLY},
    {'model': 'car_import.stagechangelog', 'group': 'car_import.operations', 'permissions': VIEW_ONLY},
    {'model': 'car_import.stagechangelog', 'group': 'car_import.management', 'permissions': VIEW_ONLY},
]
