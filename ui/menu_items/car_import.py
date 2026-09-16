# -*- coding: utf-8 -*-
"""The Car Import menu: one root, four groups, the screens under them.

Three levels on purpose. Fifteen flat children spread across the whole top
navigation and pushed the other apps off the bar; a person looking for
"where is the message log" scanned fifteen labels. Four groups read the way the
company talks about its work — selling, the cars, the operations behind a
shipment, and the settings management owns.

No dashboard entry: `/dashboard/` lists every dashboard view as a tab by
itself, and a menu item that pointed at `/genie/<id>/` only ever rendered the
deal list under a dashboard title (that route has no dashboard strategy).

A group's `allowed_groups` is the union of its children's: the group must be
visible to anyone who may see any screen inside it, and each screen still
carries its own gate.
"""
from django.utils.translation import gettext as _

_EVERYONE = ["car_import.sales_agent", "car_import.sales_manager", "car_import.operations",
             "car_import.germany_team", "car_import.showroom", "car_import.management"]

menu_dict = {
    "car_import_main_menu": {
        "name": _("Car Import"),
        "icon": "Car",
        "module": "car_import",
        "sequence": 15,
        "allowed_groups": _EVERYONE,
        "children": {
            # ---------------------------------------------------------- selling
            "car_import_menu_sales": {
                "name": _("Sales"),
                "icon": "Handshake",
                "module": "car_import",
                "sequence": 10,
                "allowed_groups": ["car_import.sales_agent", "car_import.sales_manager",
                                   "car_import.operations", "car_import.showroom",
                                   "car_import.management"],
                "children": {
                    "car_import_menu_deals": {
                        "name": _("Deals"),
                        "icon": "Handshake",
                        "module": "car_import",
                        "model": "car_import.cardeal",
                        "view_types": "kanban,list,form",
                        "sequence": 10,
                        "allowed_groups": ["car_import.sales_agent", "car_import.sales_manager",
                                           "car_import.operations", "car_import.management"],
                    },
                    "car_import_menu_quotes": {
                        "name": _("Quotations"),
                        "icon": "Calculator",
                        "module": "car_import",
                        "model": "car_import.quote",
                        "view_types": "list,form",
                        "sequence": 15,
                        "allowed_groups": ["car_import.sales_agent", "car_import.sales_manager",
                                           "car_import.management"],
                    },
                    "car_import_menu_contracts": {
                        "name": _("Contracts"),
                        "icon": "FileText",
                        "module": "car_import",
                        "model": "car_import.contract",
                        "view_types": "list,form",
                        "sequence": 20,
                        "allowed_groups": ["car_import.sales_agent", "car_import.sales_manager",
                                           "car_import.operations", "car_import.management"],
                    },
                    "car_import_menu_consignment": {
                        "name": _("Consignment mandates"),
                        "icon": "Handshake",
                        "module": "car_import",
                        "model": "car_import.consignmentmandate",
                        "view_types": "list,form",
                        "sequence": 25,
                        "allowed_groups": ["car_import.sales_agent", "car_import.sales_manager",
                                           "car_import.showroom", "car_import.management"],
                    },
                    "car_import_menu_approval_requests": {
                        "name": _("Approval requests"),
                        "icon": "ShieldCheck",
                        "module": "car_import",
                        "model": "car_import.approvalrequest",
                        "view_types": "list,form",
                        "sequence": 30,
                        # Everyone sees the queue — an agent needs to know their own
                        # request is waiting. Only management can decide one, which the
                        # model permissions enforce.
                        "allowed_groups": ["car_import.sales_agent", "car_import.sales_manager",
                                           "car_import.operations", "car_import.management"],
                    },
                },
            },
            # --------------------------------------------------------- the cars
            "car_import_menu_cars_group": {
                "name": _("Cars and listings"),
                "icon": "CarFront",
                "module": "car_import",
                "sequence": 20,
                "allowed_groups": ["car_import.sales_agent", "car_import.sales_manager",
                                   "car_import.germany_team", "car_import.showroom",
                                   "car_import.management"],
                "children": {
                    "car_import_menu_vehicles": {
                        "name": _("Cars"),
                        "icon": "CarFront",
                        "module": "car_import",
                        "model": "car_import.vehicle",
                        "view_types": "list,form",
                        "sequence": 10,
                        "allowed_groups": ["car_import.sales_agent", "car_import.sales_manager",
                                           "car_import.germany_team", "car_import.management"],
                    },
                    "car_import_menu_listings": {
                        "name": _("Supplier listings"),
                        "icon": "Search",
                        "module": "car_import",
                        "model": "car_import.supplierlisting",
                        "view_types": "list,form",
                        "sequence": 15,
                        # Not the sales agents: a listing carries the German purchase
                        # price, which is cost data they must not see.
                        "allowed_groups": ["car_import.sales_manager", "car_import.germany_team",
                                           "car_import.management"],
                    },
                    "car_import_menu_showroom": {
                        "name": _("Showroom cars"),
                        "icon": "Store",
                        "module": "car_import",
                        "model": "car_import.showroomlisting",
                        "view_types": "list,form",
                        "sequence": 20,
                        "allowed_groups": ["car_import.sales_agent", "car_import.sales_manager",
                                           "car_import.showroom", "car_import.management"],
                    },
                    "car_import_menu_initiatives": {
                        "name": _("Initiatives"),
                        "icon": "BadgeCheck",
                        "module": "car_import",
                        "model": "car_import.initiative",
                        "view_types": "list,form",
                        "sequence": 25,
                        "allowed_groups": ["car_import.sales_agent", "car_import.sales_manager",
                                           "car_import.management"],
                    },
                    "car_import_menu_initiative_market": {
                        "name": _("Initiatives for sale"),
                        "icon": "ArrowLeftRight",
                        "module": "car_import",
                        "model": "car_import.initiativelisting",
                        "view_types": "list,form",
                        "sequence": 30,
                        "allowed_groups": ["car_import.sales_agent", "car_import.sales_manager",
                                           "car_import.management"],
                    },
                },
            },
            # ------------------------------------------------------- operations
            "car_import_menu_operations": {
                "name": _("Operations"),
                "icon": "ClipboardCheck",
                "module": "car_import",
                "sequence": 30,
                "allowed_groups": ["car_import.sales_agent", "car_import.sales_manager",
                                   "car_import.operations", "car_import.management"],
                "children": {
                    "car_import_menu_deal_documents": {
                        "name": _("Documents"),
                        "icon": "FileCheck",
                        "module": "car_import",
                        "model": "car_import.dealdocument",
                        "view_types": "list,form",
                        "sequence": 10,
                        "allowed_groups": ["car_import.sales_agent", "car_import.sales_manager",
                                           "car_import.operations", "car_import.management"],
                    },
                    "car_import_menu_calls": {
                        "name": _("Call recordings"),
                        "icon": "PhoneCall",
                        "module": "car_import",
                        "model": "car_import.callrecording",
                        "view_types": "list,form",
                        "sequence": 20,
                        # Internal only. A recording is personal data, and the summaries
                        # are for the company rather than the customer.
                        "allowed_groups": ["car_import.sales_manager", "car_import.operations",
                                           "car_import.management"],
                    },
                    "car_import_menu_stage_log": {
                        "name": _("Message log"),
                        "icon": "Send",
                        "module": "car_import",
                        "model": "car_import.stagechangelog",
                        "view_types": "list",
                        "sequence": 30,
                        "allowed_groups": ["car_import.sales_manager", "car_import.operations",
                                           "car_import.management"],
                    },
                },
            },
            # ---------------------------------------------------- configuration
            "car_import_menu_configuration": {
                "name": _("Configuration"),
                "icon": "Settings",
                "module": "car_import",
                "sequence": 90,
                "allowed_groups": ["car_import.management", "car_import.operations",
                                   "car_import.sales_manager"],
                "children": {
                    "car_import_menu_stages": {
                        "name": _("Stages and messages"),
                        "icon": "ListOrdered",
                        "module": "car_import",
                        "model": "car_import.importstage",
                        "view_types": "list,form",
                        "sequence": 10,
                        "allowed_groups": ["car_import.management", "car_import.operations"],
                    },
                    "car_import_menu_doc_requirements": {
                        "name": _("Document checklists"),
                        "icon": "ClipboardList",
                        "module": "car_import",
                        "model": "car_import.documentrequirement",
                        "view_types": "list,form",
                        "sequence": 15,
                        "allowed_groups": ["car_import.management", "car_import.operations"],
                    },
                    "car_import_menu_programs": {
                        "name": _("Import programmes"),
                        "icon": "Route",
                        "module": "car_import",
                        "model": "car_import.importprogram",
                        "view_types": "list,form",
                        "sequence": 20,
                        "allowed_groups": ["car_import.management"],
                    },
                    "car_import_menu_approval_policies": {
                        "name": _("Approval rules"),
                        "icon": "ShieldAlert",
                        "module": "car_import",
                        "model": "car_import.approvalpolicy",
                        "view_types": "list,form",
                        "sequence": 24,
                        "allowed_groups": ["car_import.management"],
                    },
                    "car_import_menu_pricing_bands": {
                        "name": _("Pricing bands"),
                        "icon": "Calculator",
                        "module": "car_import",
                        "model": "car_import.pricingband",
                        "view_types": "list,form",
                        "sequence": 25,
                        "allowed_groups": ["car_import.management", "car_import.sales_manager"],
                    },
                    "car_import_menu_contract_templates": {
                        "name": _("Contract templates"),
                        "icon": "FileStack",
                        "module": "car_import",
                        "model": "car_import.contracttemplate",
                        "view_types": "list,form",
                        "sequence": 26,
                        # The lawyer's wording. Management only.
                        "allowed_groups": ["car_import.management"],
                    },
                    "car_import_menu_contract_issuers": {
                        "name": _("Contract issuer and signatories"),
                        "icon": "Stamp",
                        "module": "car_import",
                        "model": "car_import.contractissuer",
                        "view_types": "list,form",
                        "sequence": 27,
                        "allowed_groups": ["car_import.management"],
                    },
                    "car_import_menu_fees": {
                        "name": _("Fee schedule"),
                        "icon": "Receipt",
                        "module": "car_import",
                        "model": "car_import.feeschedule",
                        "view_types": "list,form",
                        "sequence": 30,
                        "allowed_groups": ["car_import.management"],
                    },
                    "car_import_menu_financing": {
                        "name": _("Financing plans"),
                        "icon": "CreditCard",
                        "module": "car_import",
                        "model": "car_import.financingplan",
                        "view_types": "list,form",
                        "sequence": 40,
                        "allowed_groups": ["car_import.management"],
                    },
                    "car_import_menu_tax_rules": {
                        "name": _("Tax rules"),
                        "icon": "Percent",
                        "module": "car_import",
                        "model": "car_import.taxrule",
                        "view_types": "list",
                        "sequence": 50,
                        "allowed_groups": ["car_import.management"],
                    },
                    "car_import_menu_deposits": {
                        "name": _("Deposit values"),
                        "icon": "Landmark",
                        "module": "car_import",
                        "model": "car_import.deposittier",
                        "view_types": "list",
                        "sequence": 60,
                        "allowed_groups": ["car_import.management", "car_import.sales_manager"],
                    },
                    "car_import_menu_customs": {
                        "name": _("Customs values"),
                        "icon": "Scale",
                        "module": "car_import",
                        "model": "car_import.customsvaluation",
                        "view_types": "list",
                        "sequence": 70,
                        "allowed_groups": ["car_import.management", "car_import.sales_manager"],
                    },
                    "car_import_menu_price_ranges": {
                        "name": _("Model price ranges"),
                        "icon": "ChartNoAxesColumn",
                        "module": "car_import",
                        "model": "car_import.modelpricerange",
                        "view_types": "list",
                        "sequence": 80,
                        "allowed_groups": ["car_import.management", "car_import.sales_manager"],
                    },
                    "car_import_menu_fx": {
                        "name": _("Exchange rates"),
                        "icon": "ArrowRightLeft",
                        "module": "car_import",
                        "model": "car_import.fxreference",
                        "view_types": "list,form",
                        "sequence": 90,
                        "allowed_groups": ["car_import.management", "car_import.sales_manager"],
                    },
                },
            },
        },
    },
}
