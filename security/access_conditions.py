# -*- coding: utf-8 -*-
"""Row-level access — the contractual half of security.

The six groups control which SCREENS a person can open. They do nothing about
which ROWS they see once inside, and until this file existed every user who
could open the deals list saw every deal, every customer and every figure in
the company.

The client's brief makes that a contractual obligation rather than a
preference: cost prices, supplier terms and other agents' customers must be
invisible to a sales agent. So:

* a sales agent sees the deals **assigned to them**, and nothing else;
* supplier listings — which carry the German purchase price — are not theirs to
  see at all, enforced one layer up in `model_permissions.py`;
* managers, operations and management are unrestricted, because they need the
  whole pipeline to do their jobs.

A condition here applies to the MODEL, everywhere it appears — list, form,
kanban, export, search and the API alike. That is the point: a rule that only
holds on one screen is not a rule.
"""
from modules.base.genie_filter import create_own_records_condition

ACCESS_CONDITIONS = [
    {
        "name": "car import: an agent sees their own deals",
        "model": "car_import.cardeal",
        # `assigned_to`, not `created_by`: a deal created by a manager and
        # handed to an agent is that agent's deal, and a deal an agent typed in
        # and handed on is not.
        "condition": create_own_records_condition('assigned_to'),
        "permissions": [1, 1, 1, 0],
        "groups": ["car_import.sales_agent"],
    },
    # The same line, drawn around everything that hangs off a deal: an
    # agent's quotations, contracts and paperwork are theirs; another agent's
    # are not. Until now a sales agent could open any quotation in the company
    # and read every price ever given.
    {
        "name": "car import: an agent sees their own quotations",
        "model": "car_import.quote",
        "condition": create_own_records_condition('assigned_to'),
        "permissions": [1, 1, 1, 0],
        "groups": ["car_import.sales_agent"],
    },
    {
        "name": "car import: an agent sees their own deals' payment receipts",
        "model": "car_import.paymentreceipt",
        "condition": {'filters': {"operator": "and", "filters": [
            {"field": "deal.assigned_to", "operator": "eq", "value": "user.id"},
        ]}},
        "permissions": [1, 0, 0, 0],
        "groups": ["car_import.sales_agent"],
    },
    {
        "name": "car import: an agent sees their own deals' proforma invoices",
        "model": "car_import.proformainvoice",
        "condition": {'filters': {"operator": "and", "filters": [
            {"field": "deal.assigned_to", "operator": "eq", "value": "user.id"},
        ]}},
        "permissions": [1, 0, 0, 0],
        "groups": ["car_import.sales_agent"],
    },
    {
        "name": "car import: an agent sees their own deals' contracts",
        "model": "car_import.contract",
        "condition": {'filters': {"operator": "and", "filters": [
            {"field": "deal.assigned_to", "operator": "eq", "value": "user.id"},
        ]}},
        "permissions": [1, 1, 1, 0],
        "groups": ["car_import.sales_agent"],
    },
    {
        "name": "car import: an agent sees their own deals' paperwork",
        "model": "car_import.dealdocument",
        "condition": {'filters': {"operator": "and", "filters": [
            {"field": "deal.assigned_to", "operator": "eq", "value": "user.id"},
        ]}},
        "permissions": [1, 1, 1, 0],
        "groups": ["car_import.sales_agent"],
    },
    {
        "name": "car import: an agent sees the approvals they asked for",
        "model": "car_import.approvalrequest",
        "condition": create_own_records_condition('requested_by'),
        "permissions": [1, 0, 0, 0],
        "groups": ["car_import.sales_agent"],
    },
    {
        "name": "car import: an agent sees their own deals' message log",
        "model": "car_import.stagechangelog",
        "condition": {'filters': {"operator": "and", "filters": [
            {"field": "deal.assigned_to", "operator": "eq", "value": "user.id"},
        ]}},
        "permissions": [1, 0, 0, 0],
        "groups": ["car_import.sales_agent"],
    },
]
