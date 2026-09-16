# -*- coding: utf-8 -*-
"""The management dashboard — what a manager needs before their first coffee.

Four questions, in the order they get asked:

1. where is everything? (the pipeline by stage)
2. what is stuck? (deals sitting too long, blocked, or on hold)
3. who has not paid? (the payment marks, which are marks and not accounting)
4. did the customers actually hear from us? (message delivery, and the
   escalations nobody picked up)

Nothing here computes money the business has not confirmed. The tiles count
rows and days; they do not add up a pipeline value, because the pricing engine
does not exist yet and a wrong total on a dashboard becomes a number people
repeat in meetings.
"""
from django.utils.translation import gettext as _

car_import_dashboard_view = {
    "key": "car_import_dashboard_view",
    "name": _("Car import dashboard"),
    "model": "car_import.cardeal",
    "menu_item": "car_import_menu_dashboard",
    "view_type": "dashboard",
    "priority": 10,
    "module": "car_import",
    "body": {
        "dashboard": {
            "id": "car-import-overview",
            "name": _("Car import"),
            "description": _("The pipeline, what is stuck, and what the customer was told"),
            "rows": [
                {
                    "widgets": [
                        {
                            "type": "tile",
                            "title": _("Open deals"),
                            "model": "car_import.cardeal",
                            "aggregate": "count",
                            "filter": {"operator": "and", "filters": [
                                {"field": "state", "operator": "eq", "value": "open"},
                            ]},
                            "icon": "Handshake",
                            "width": 3,
                        },
                        {
                            "type": "tile",
                            "title": _("Blocked"),
                            "model": "car_import.cardeal",
                            "aggregate": "count",
                            "filter": {"operator": "and", "filters": [
                                {"field": "stage_is_blocked", "operator": "eq", "value": True},
                            ]},
                            "icon": "OctagonAlert",
                            "width": 3,
                        },
                        {
                            "type": "tile",
                            "title": _("On hold"),
                            "model": "car_import.cardeal",
                            "aggregate": "count",
                            "filter": {"operator": "and", "filters": [
                                {"field": "state", "operator": "eq", "value": "on_hold"},
                            ]},
                            "icon": "PauseCircle",
                            "width": 3,
                        },
                        {
                            "type": "tile",
                            "title": _("Not paid"),
                            "model": "car_import.cardeal",
                            "aggregate": "count",
                            "filter": {"operator": "and", "filters": [
                                {"field": "payment_state", "operator": "eq", "value": "not_paid"},
                                {"field": "state", "operator": "eq", "value": "open"},
                            ]},
                            "icon": "Wallet",
                            "width": 3,
                        },
                    ],
                },
                {
                    "widgets": [
                        {
                            "type": "chart",
                            "chart_type": "bar",
                            "title": _("Pipeline by stage"),
                            "model": "car_import.cardeal",
                            "group_by": ["import_stage__name"],
                            "aggregate": "count",
                            "filter": {"operator": "and", "filters": [
                                {"field": "state", "operator": "eq", "value": "open"},
                            ]},
                            "width": 8,
                        },
                        {
                            "type": "chart",
                            "chart_type": "pie",
                            "title": _("By programme"),
                            "model": "car_import.cardeal",
                            "group_by": ["program"],
                            "aggregate": "count",
                            "width": 4,
                        },
                    ],
                },
                {
                    "widgets": [
                        {
                            "type": "chart",
                            "chart_type": "bar",
                            "title": _("Deals per agent"),
                            "model": "car_import.cardeal",
                            "group_by": ["assigned_to__name"],
                            "aggregate": "count",
                            "filter": {"operator": "and", "filters": [
                                {"field": "state", "operator": "eq", "value": "open"},
                            ]},
                            "width": 6,
                        },
                        {
                            # Did the customer actually hear from us? A failed
                            # message is a customer who will telephone instead.
                            "type": "chart",
                            "chart_type": "pie",
                            "title": _("Customer messages"),
                            "model": "car_import.stagechangelog",
                            "group_by": ["notification_state"],
                            "aggregate": "count",
                            "width": 6,
                        },
                    ],
                },
                {
                    "widgets": [
                        {
                            "type": "list",
                            "title": _("Waiting on paperwork"),
                            "model": "car_import.dealdocument",
                            "filter": {"operator": "and", "filters": [
                                {"field": "state", "operator": "in",
                                 "value": ["missing", "rejected", "expired"]},
                            ]},
                            "fields": ["deal", "name", "state"],
                            "limit": 10,
                            "width": 6,
                        },
                        {
                            "type": "list",
                            "title": _("Calls to review"),
                            "model": "car_import.callrecording",
                            "filter": {"operator": "and", "filters": [
                                {"field": "match_state", "operator": "in",
                                 "value": ["unmatched", "ambiguous"]},
                            ]},
                            "fields": ["recorded_at", "customer_phone", "match_note"],
                            "limit": 10,
                            "width": 6,
                        },
                    ],
                },
            ],
        },
    },
}
