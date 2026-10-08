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

    # ── the car catalogue: everyone reads it, the people who add cars extend it
    # Never deleted by anyone but management — every car, advert and price row
    # points at it (and the database refuses while one does).
    *[{'model': model, 'group': group, 'permissions': rights}
      for model in ('car_import.carbrand', 'car_import.carmodel')
      for group, rights in (('car_import.sales_agent', VIEW_ONLY), ('car_import.operations', VIEW_ONLY),
                            ('car_import.accountant', VIEW_ONLY), ('car_import.showroom', MANAGE),
                            ('car_import.germany_team', MANAGE), ('car_import.sales_manager', MANAGE),
                            ('car_import.management', FULL))],

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

    # ── the operating switches (base.ConfigParameter) ─────────────────────
    # Management flips them from the screen; nobody deletes one — a missing
    # row silently reverts to the code's default.
    {'model': 'base.configparameter', 'group': 'car_import.management', 'permissions': MANAGE},
    {'model': 'base.configparameter', 'group': 'car_import.sales_manager', 'permissions': VIEW_ONLY},

    # ── chat wizards ────────────────────────────────────────────────────────
    # Transient rows behind the chat-header actions. Whoever may act may
    # open the wizard; the action it runs enforces the real rules.
    {'model': 'car_import.qualifycustomer', 'group': 'car_import.sales_agent', 'permissions': MANAGE},
    {'model': 'car_import.qualifycustomer', 'group': 'car_import.sales_manager', 'permissions': MANAGE},
    {'model': 'car_import.qualifycustomer', 'group': 'car_import.management', 'permissions': FULL},
    {'model': 'car_import.setstage', 'group': 'car_import.sales_agent', 'permissions': MANAGE},
    {'model': 'car_import.setstage', 'group': 'car_import.sales_manager', 'permissions': MANAGE},
    {'model': 'car_import.setstage', 'group': 'car_import.operations', 'permissions': MANAGE},
    {'model': 'car_import.setstage', 'group': 'car_import.management', 'permissions': FULL},

    # ── contracts ───────────────────────────────────────────────────────────
    # An agent fills and generates one; nobody deletes one, because a generated
    # contract is evidence of what was agreed.
    # ── the company website ─────────────────────────────────────────────────
    # The connection holds the website password: management only.
    {'model': 'car_import.websiteconnection', 'group': 'car_import.management', 'permissions': MANAGE},
    {'model': 'car_import.websitecar', 'group': 'car_import.management', 'permissions': FULL},
    {'model': 'car_import.websitecar', 'group': 'car_import.sales_manager', 'permissions': MANAGE},
    {'model': 'car_import.websitecar', 'group': 'car_import.showroom', 'permissions': MANAGE},
    {'model': 'car_import.websitecar', 'group': 'car_import.germany_team', 'permissions': MANAGE},
    {'model': 'car_import.websitecar', 'group': 'car_import.sales_agent', 'permissions': VIEW_ONLY},
    {'model': 'car_import.websitelookup', 'group': 'car_import.management', 'permissions': MANAGE},
    {'model': 'car_import.websitelookup', 'group': 'car_import.sales_manager', 'permissions': MANAGE},
    {'model': 'car_import.websitelookup', 'group': 'car_import.showroom', 'permissions': VIEW_ONLY},
    {'model': 'car_import.websitelookup', 'group': 'car_import.germany_team', 'permissions': VIEW_ONLY},
    {'model': 'car_import.websitelookup', 'group': 'car_import.sales_agent', 'permissions': VIEW_ONLY},
    {'model': 'car_import.websitesubmission', 'group': 'car_import.management', 'permissions': FULL},
    {'model': 'car_import.websitesubmission', 'group': 'car_import.sales_manager', 'permissions': VIEW_ONLY},
    {'model': 'car_import.websitesubmission', 'group': 'car_import.sales_agent', 'permissions': VIEW_ONLY},
    {'model': 'car_import.websiteapilog', 'group': 'car_import.management', 'permissions': VIEW_ONLY},

    # ── the money a person confirms ─────────────────────────────────────────
    # An agent SEES their customer's receipt and cannot change it: confirming
    # your own customer's payment is the control this whole flow keeps.
    {'model': 'car_import.paymentreceipt', 'group': 'car_import.accountant', 'permissions': MANAGE},
    {'model': 'car_import.paymentreceipt', 'group': 'car_import.sales_agent', 'permissions': VIEW_ONLY},
    {'model': 'car_import.paymentreceipt', 'group': 'car_import.sales_manager', 'permissions': VIEW_ONLY},
    {'model': 'car_import.paymentreceipt', 'group': 'car_import.management', 'permissions': FULL},
    {'model': 'car_import.proformainvoice', 'group': 'car_import.accountant', 'permissions': MANAGE},
    {'model': 'car_import.proformainvoice', 'group': 'car_import.sales_agent', 'permissions': VIEW_ONLY},
    {'model': 'car_import.proformainvoice', 'group': 'car_import.sales_manager', 'permissions': MANAGE},
    {'model': 'car_import.proformainvoice', 'group': 'car_import.management', 'permissions': FULL},
    # What the accountant has to be able to open from a receipt.
    {'model': 'car_import.cardeal', 'group': 'car_import.accountant', 'permissions': VIEW_ONLY},
    {'model': 'car_import.quote', 'group': 'car_import.accountant', 'permissions': VIEW_ONLY},
    {'model': 'car_import.contract', 'group': 'car_import.accountant', 'permissions': VIEW_ONLY},

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

    # ── approvals ───────────────────────────────────────────────────────────
    # The rules are policy: management writes them. Everyone reads their own
    # queue — an agent whose save was blocked has to be able to see that the
    # request exists — and only management may decide one, which is the whole
    # point of the matrix.
    {'model': 'car_import.approvalpolicy', 'group': 'car_import.management', 'permissions': FULL},
    {'model': 'car_import.approvalpolicy', 'group': 'car_import.sales_manager',
     'permissions': VIEW_ONLY},
    {'model': 'car_import.approvalrequest', 'group': 'car_import.sales_agent',
     'permissions': [1, 1, 0, 0]},
    {'model': 'car_import.approvalrequest', 'group': 'car_import.sales_manager',
     'permissions': [1, 1, 0, 0]},
    {'model': 'car_import.approvalrequest', 'group': 'car_import.operations',
     'permissions': VIEW_ONLY},
    {'model': 'car_import.approvalrequest', 'group': 'car_import.management', 'permissions': FULL},

    # ── lead assignment ─────────────────────────────────────────────────────
    # Who gets which leads is management's to set. The log is what the job
    # counts a salesperson's day from: read, never edited.
    {'model': 'car_import.leadassignmentgroup', 'group': 'car_import.management',
     'permissions': FULL},
    {'model': 'car_import.leadassignmentlog', 'group': 'car_import.management',
     'permissions': VIEW_ONLY},

    # ── the Link Tracker lists ──────────────────────────────────────────────
    # Management keeps them. Sales and operations may read the plain lists —
    # they are what a lead or a shipment will be described with — and nothing
    # more. Who is on hold and who is blacklisted is management's alone.
    *[{'model': f'car_import.{model}', 'group': group, 'permissions': rights}
      for model in ('carmodelyear', 'carcolour', 'cartrimlevel', 'carbuyer',
                    'arrivalport', 'shippingdestination', 'internationalshipper', 'loadingport',
                    'customsclearanceperson', 'opportunityproducttype', 'eumadebrand')
      for group, rights in (('car_import.sales_agent', VIEW_ONLY), ('car_import.sales_manager', VIEW_ONLY),
                            ('car_import.operations', VIEW_ONLY), ('car_import.management', FULL))],
    {'model': 'car_import.onholdsalesperson', 'group': 'car_import.management', 'permissions': FULL},
    {'model': 'car_import.blacklistedcustomer', 'group': 'car_import.management', 'permissions': FULL},
    # Mediums and Sources are crm's tables, and crm grants them to no group at
    # all: without these two rows the entries open on "not authorized" for
    # anybody who is not a superuser. No delete — every lead's source and
    # medium point at these rows, and removing one blanks them silently.
    {'model': 'crm.utmmedium', 'group': 'car_import.management', 'permissions': MANAGE},
    {'model': 'crm.utmsource', 'group': 'car_import.management', 'permissions': MANAGE},

    # ── the company's own legal identity ────────────────────────────────────
    {'model': 'car_import.contractissuer', 'group': 'car_import.management', 'permissions': FULL},
    {'model': 'car_import.contractissuer', 'group': 'car_import.sales_manager',
     'permissions': VIEW_ONLY},
    {'model': 'car_import.contractsignatory', 'group': 'car_import.management',
     'permissions': FULL},
    {'model': 'car_import.contractsignatory', 'group': 'car_import.sales_manager',
     'permissions': VIEW_ONLY},

    # ── consignment (L6) ────────────────────────────────────────────────────
    {'model': 'car_import.consignmentmandate', 'group': 'car_import.sales_agent',
     'permissions': MANAGE},
    {'model': 'car_import.consignmentmandate', 'group': 'car_import.sales_manager',
     'permissions': MANAGE},
    {'model': 'car_import.consignmentmandate', 'group': 'car_import.showroom',
     'permissions': MANAGE},
    {'model': 'car_import.consignmentmandate', 'group': 'car_import.management',
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
