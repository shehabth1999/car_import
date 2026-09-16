# -*- coding: utf-8 -*-
"""The management dashboard — what a manager needs before their first coffee.

Four questions, in the order they get asked:

1. where is everything, and what is it worth? (the pipeline by stage, and the
   agreed, collected and outstanding money on it)
2. what is stuck? (blocked, on hold, waiting on management)
3. who has not paid, and who paid too much?
4. did the customers actually hear from us? (message delivery, escalations)

**Schema note, because the first version of this file got it wrong.** The
dashboard renderer reads exactly three buckets — ``cards``, ``kpis`` and
``sections[].groups[].components[]`` — with ``metric.aggregation`` on a card,
``type: bar|line|pie|donut|table`` on a component, and ``domain`` for filters
(``modules/dashboard/api/custom_resolver.py:53-63``, ``authoring/catalog.py``).
The previous version declared ``rows[].widgets[]`` with ``type: tile``,
``aggregate`` and ``filter`` — none of which the renderer reads — and so drew
an empty page with a title. Reference: ``modules/crm/ui/views/crm_dashboard.py``.

**Every global filter here must exist on every model a component reads.** The
engine applies the filter blob to all components with no exemption, and a
missing field is an HTTP 500 for that component. ``created_at`` is on every
BaseModel; nothing else is, so it is the only system filter. Everything else
is a per-component ``domain``.

Money on this dashboard is the human-set marks on the deal — ``amount_agreed``,
``amount_paid_marked``, ``amount_due_marked`` — not accounting. That is still
what the plan says money is in this system; the calculator now exists, so the
marks are finally worth summing.
"""
from django.utils.translation import gettext as _

_OPEN = {"operator": "and", "filters": [{"field": "state", "operator": "eq", "value": "open"}]}


def _open_and(*extra):
    return {"operator": "and", "filters": [
        {"field": "state", "operator": "eq", "value": "open"}, *extra]}


car_import_dashboard_view = {
    "key": "car_import_dashboard_view",
    "name": _("Car import dashboard"),
    "model": "car_import.cardeal",
    "menu_item": "car_import_menu_dashboard",
    "view_type": "dashboard",
    "priority": 10,
    "module": "car_import",
    "body": {
        "icon": "Car",
        "model": "car_import.cardeal",
        "filter_section": {
            "system_filters": [
                {
                    "name": "created_on",
                    "string": _("Created"),
                    "default": "all_time",
                    "filters": [
                        {"name": "all_time", "string": _("All time"), "filter": {}},
                        {"name": "last_30_days", "string": _("Last 30 days"),
                         "filter": {"field": "created_at", "operator": "gte", "value": "30_days_ago"}},
                        {"name": "last_90_days", "string": _("Last 90 days"),
                         "filter": {"field": "created_at", "operator": "gte", "value": "90_days_ago"}},
                        {"name": "this_year", "string": _("This year"),
                         "filter": {"field": "created_at", "operator": "this_year"}},
                    ],
                },
            ],
            "field_filters": [],
        },
        "cards": [
            {"name": "open_deals", "title": _("Open deals"), "subtitle": "Deals still moving",
             "metric": {"field": "id", "aggregation": "count", "format": "number"},
             "domain": _OPEN, "icon": "Handshake", "color": "primary"},
            {"name": "blocked_deals", "title": _("Blocked"), "subtitle": "A stage gate is refusing",
             "metric": {"field": "id", "aggregation": "count", "format": "number"},
             "domain": {"operator": "and", "filters": [
                 {"field": "stage_is_blocked", "operator": "eq", "value": True}]},
             "icon": "OctagonAlert", "color": "danger"},
            {"name": "on_hold", "title": _("On hold"), "subtitle": "Paused by a person",
             "metric": {"field": "id", "aggregation": "count", "format": "number"},
             "domain": {"operator": "and", "filters": [
                 {"field": "state", "operator": "eq", "value": "on_hold"}]},
             "icon": "PauseCircle", "color": "warning"},
            {"name": "unpaid_open", "title": _("Not paid"), "subtitle": "Open deals with no payment mark",
             "metric": {"field": "id", "aggregation": "count", "format": "number"},
             "domain": _open_and({"field": "payment_state", "operator": "eq", "value": "not_paid"}),
             "icon": "Wallet", "color": "warning"},
            {"name": "awaiting_management", "title": _("Waiting for management"),
             "subtitle": "Approval requests nobody has decided",
             "model": "car_import.approvalrequest",
             "metric": {"field": "id", "aggregation": "count", "format": "number"},
             "domain": {"operator": "and", "filters": [
                 {"field": "state", "operator": "eq", "value": "pending"}]},
             "icon": "ShieldAlert", "color": "danger"},
            {"name": "messages_failed", "title": _("Messages that failed"),
             "subtitle": "Customers who were NOT told about a stage",
             "model": "car_import.stagechangelog",
             "metric": {"field": "id", "aggregation": "count", "format": "number"},
             "domain": {"operator": "and", "filters": [
                 {"field": "notification_state", "operator": "eq", "value": "failed"}]},
             "icon": "MessageSquareWarning", "color": "danger"},
        ],
        "kpis": [
            {
                "name": "pipeline_agreed",
                "title": _("Pipeline value"),
                "subtitle": _("Agreed amounts on open deals, per agent"),
                "type": "revenue",
                "aggregation": "sum",
                "aggregation_field": "amount_agreed",
                "domain": _OPEN,
                "loop_on": "assigned_to",
                "loop_order_by": "-amount_agreed",
                "loop_limit": 8,
                "record_title_field": "assigned_to__name",
                "record_subtitle_field": "assigned_to__email",
                "max_type": "auto",
                "min_field": 0,
                "format": "currency",
            },
            {
                "name": "collected_vs_agreed",
                "title": _("Collected"),
                "subtitle": _("Marked as paid, against everything agreed"),
                "type": "circular",
                "aggregation": "sum",
                "aggregation_field": "amount_paid_marked",
                "domain": _OPEN,
                "max_type": "auto",
                "min_field": 0,
                "format": "currency",
            },
            {
                "name": "outstanding",
                "title": _("Still owed"),
                "subtitle": _("Marked as due on open deals"),
                "type": "linear",
                "aggregation": "sum",
                "aggregation_field": "amount_due_marked",
                "domain": _OPEN,
                "max_type": "auto",
                "min_field": 0,
                "format": "currency",
            },
        ],
        "sections": [
            {
                "name": "pipeline",
                "title": _("The pipeline"),
                "subtitle": "Where every open car is, and what it is worth",
                "groups": [
                    {"title": _("Deals by stage"), "components": [{
                        "type": "bar", "name": "deals_by_stage",
                        "subtitle": "Open deals per shipping stage",
                        "on_click": "kanban",
                        "field": "import_stage__name", "measure": "id", "aggregation": "count",
                        "group_by": ["import_stage__name"], "domain": _OPEN}]},
                    {"title": _("Agreed value by stage"), "components": [{
                        "type": "donut", "name": "value_by_stage",
                        "subtitle": "Where the money sits",
                        "field": "import_stage__name", "measure": "amount_agreed",
                        "aggregation": "sum", "group_by": ["import_stage__name"],
                        "domain": _OPEN}]},
                    {"title": _("Deals by programme"), "components": [{
                        "type": "pie", "name": "deals_by_program",
                        "subtitle": "Which revenue line each deal belongs to",
                        "field": "program", "measure": "id", "aggregation": "count",
                        "group_by": ["program"]}]},
                    {"title": _("Deals per agent, by stage"), "fullWidth": True, "components": [{
                        "type": "bar", "name": "deals_by_agent_stage",
                        "subtitle": "Who carries what",
                        "on_click": "kanban", "stacked": True,
                        "field": "assigned_to__name", "measure": "id", "aggregation": "count",
                        "group_by": ["assigned_to__name", "import_stage__name"],
                        "domain": _OPEN}]},
                ],
            },
            {
                "name": "money",
                "title": _("Money"),
                "subtitle": "The marks people set — not accounting",
                "groups": [
                    {"title": _("Payment state"), "components": [{
                        "type": "pie", "name": "payment_state_pie",
                        "subtitle": "Open deals by payment mark",
                        "field": "payment_state", "measure": "id", "aggregation": "count",
                        "group_by": ["payment_state"], "domain": _OPEN}]},
                    {"title": _("Quotations per month"), "components": [{
                        "type": "line", "name": "quotes_by_month",
                        "subtitle": "Sent and accepted, by month",
                        "model": "car_import.quote",
                        "field": "quote_date", "interval": "month",
                        "available_intervals": ["week", "month", "quarter"],
                        "measure": "id", "aggregation": "count", "group_by": ["state"],
                        "order_by": "quote_date", "show_total": True,
                        "domain": {"operator": "and", "filters": [
                            {"field": "state", "operator": "in", "value": ["sent", "accepted"]}]}}]},
                    {"title": _("Overpaid"), "fullWidth": True, "components": [{
                        # An overpayment is a fact worth a row: the customer sent
                        # more than the total, and an agent who cannot see it will
                        # ask for money already paid.
                        "type": "table", "name": "overpaid_quotes",
                        "subtitle": "Customers who paid more than the quotation total",
                        "model": "car_import.quote",
                        "fields": [
                            {"name": "name", "string": _("Reference"), "format": "text"},
                            {"name": "partner__name", "string": _("Customer"), "format": "text"},
                            {"name": "total_eur", "string": _("Total €"), "format": "number", "align": "right"},
                            {"name": "paid_eur", "string": _("Paid €"), "format": "number", "align": "right"},
                            {"name": "overpaid_eur", "string": _("Overpaid €"), "format": "number", "align": "right"},
                        ],
                        "limit": 10, "order_by": "-overpaid_eur",
                        "domain": {"operator": "and", "filters": [
                            {"field": "overpaid_eur", "operator": "gt", "value": 0}]}}]},
                ],
            },
            {
                "name": "customers_heard",
                "title": _("Did the customer hear from us?"),
                "subtitle": "Message delivery and what is waiting on people",
                "groups": [
                    {"title": _("Customer messages"), "components": [{
                        "type": "pie", "name": "message_states",
                        "subtitle": "Every stage message, by what happened to it",
                        "model": "car_import.stagechangelog",
                        "field": "notification_state", "measure": "id", "aggregation": "count",
                        "group_by": ["notification_state"]}]},
                    {"title": _("Approval requests"), "components": [{
                        "type": "bar", "name": "approvals_by_subject",
                        "subtitle": "What management is being asked, and how often",
                        "model": "car_import.approvalrequest",
                        "field": "subject", "measure": "id", "aggregation": "count",
                        "group_by": ["subject", "state"], "stacked": True}]},
                    {"title": _("Waiting on paperwork"), "components": [{
                        "type": "table", "name": "paperwork_waiting",
                        "subtitle": "Documents still missing, rejected or expired",
                        "model": "car_import.dealdocument",
                        "fields": [
                            {"name": "deal__name", "string": _("Deal"), "format": "text"},
                            {"name": "name", "string": _("Document"), "format": "text"},
                            {"name": "state", "string": _("State"), "format": "badge"},
                        ],
                        "limit": 10, "order_by": "-updated_at",
                        "domain": {"operator": "and", "filters": [
                            {"field": "state", "operator": "in",
                             "value": ["missing", "rejected", "expired"]}]}}]},
                    {"title": _("Calls to review"), "components": [{
                        "type": "table", "name": "calls_to_review",
                        "subtitle": "Recordings nobody could match to a customer",
                        "model": "car_import.callrecording",
                        "fields": [
                            {"name": "recorded_at", "string": _("Recorded at"), "format": "datetime"},
                            {"name": "customer_phone", "string": _("Customer number"), "format": "text"},
                            {"name": "match_note", "string": _("Match note"), "format": "text"},
                        ],
                        "limit": 10, "order_by": "-recorded_at",
                        "domain": {"operator": "and", "filters": [
                            {"field": "match_state", "operator": "in",
                             "value": ["unmatched", "ambiguous"]}]}}]},
                ],
            },
        ],
    },
}
