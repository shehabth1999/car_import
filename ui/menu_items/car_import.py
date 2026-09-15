# -*- coding: utf-8 -*-
from django.utils.translation import gettext as _

menu_dict = {
    "car_import_main_menu": {
        "name": _("Car Import"),
        "icon": "Car",
        "module": "car_import",
        "sequence": 15,
        "allowed_groups": ["car_import.sales_agent", "car_import.sales_manager",
                           "car_import.operations", "car_import.germany_team",
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
            "car_import_menu_vehicles": {
                "name": _("Cars"),
                "icon": "CarFront",
                "module": "car_import",
                "model": "car_import.vehicle",
                "view_types": "list,form",
                "sequence": 20,
                "allowed_groups": ["car_import.sales_agent", "car_import.sales_manager",
                                   "car_import.germany_team", "car_import.management"],
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
            "car_import_menu_configuration": {
                "name": _("Configuration"),
                "icon": "Settings",
                "module": "car_import",
                "sequence": 90,
                "allowed_groups": ["car_import.management"],
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
                },
            },
        },
    },
}
