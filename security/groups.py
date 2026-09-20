# -*- coding: utf-8 -*-
"""
Who does what.

The client asked for confidentiality in writing, so these are not decoration:
a sales agent must not see another agent's customers, and the Germany team must
not see customers' money at all (doc 06 §7).
"""

GROUPS = [
    {
        'name': 'Car Import / Sales Agent',
        'technical_name': 'car_import.sales_agent',
        'category': 'Car Import',
        'description': 'Own leads and deals, quotes, stages 1–2, the payment mark',
    },
    {
        'name': 'Car Import / Sales Manager',
        'technical_name': 'car_import.sales_manager',
        'category': 'Car Import',
        'implied_groups': ['car_import.sales_agent'],
        'description': 'Every deal in the company, approvals, reopening',
    },
    {
        'name': 'Car Import / Operations',
        'technical_name': 'car_import.operations',
        'category': 'Car Import',
        'description': 'Stages, logistics, documents, delivery and licensing',
    },
    {
        'name': 'Car Import / Germany Team',
        'technical_name': 'car_import.germany_team',
        'category': 'Car Import',
        'description': 'Cars and suppliers, and the stages that happen in Germany. '
                       'No customer contact data and no payment marks',
    },
    {
        'name': 'Car Import / Showroom',
        'technical_name': 'car_import.showroom',
        'category': 'Car Import',
        'description': 'Showroom cars, deliveries and appointments',
    },
    {
        'name': 'Car Import / Accountant',
        'technical_name': 'car_import.accountant',
        'category': 'Car Import',
        'description': 'Confirms that money arrived — the one step of a sale a person does. '
                       'Payment receipts, proforma invoices, and the deals and quotations they belong to',
    },
    {
        'name': 'Car Import / Management',
        'technical_name': 'car_import.management',
        'category': 'Car Import',
        'implied_groups': ['car_import.sales_manager', 'car_import.operations',
                           'car_import.germany_team', 'car_import.showroom',
                           'car_import.accountant'],
        'description': 'Everything, including configuration and the stage messages',
    },
]
