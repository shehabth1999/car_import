# -*- coding: utf-8 -*-
"""The car-import funnel, injected into the CRM dashboard.

Attribution is already captured by the platform — `crm/services/ad_lead.py`
normalises every click-to-WhatsApp, click-to-Messenger and Instagram referral
onto `Lead.utm_*`, `lead_origin` and `ctwa_*`, and `meta_ads` adds the campaign
and ad FKs. What the client could not do was *see* it for their own leads:
which advert produced which sale, which agent converts, how long a reply takes.
That is a reporting gap, not a capture gap, and this is the report.

Modelled on `modules/meta_ads/ui/views/crm_dashboard_patch.py`, and its three
constraints apply here unchanged:

1. **Every component stays on `crm.lead`.** The CRM dashboard's global filters
   read lead fields; a component on any other model would 500.
2. **Money reads the denormalised FKs** (`utm_campaign`, `meta_campaign`), never
   `lead.ad_touches` — the reverse join fans out and inflates every sum.
3. **Priority 30, not 10.** Priority 10 with a null module collides with
   `crm_dashboard`'s own key and the registry deletes the base view.

Scoped to the car-import leads (`ka_program` set, an extension field) so the
tenant's other funnels do not pile into these charts.
"""
from django.utils.translation import gettext as _

_KA = {"operator": "and", "filters": [{"field": "ka_program", "operator": "is_not_null"}]}
_KA_WON = {"operator": "and", "filters": [
    {"field": "ka_program", "operator": "is_not_null"},
    {"field": "stage__is_won", "operator": "eq", "value": True}]}
_KA_ATTRIBUTED = {"operator": "and", "filters": [
    {"field": "ka_program", "operator": "is_not_null"},
    {"field": "utm_campaign", "operator": "is_not_null"}]}


crm_dashboard_car_import_batch = {
    "key": "crm_dashboard_car_import_batch",
    "name": "CRM Dashboard - Car import funnel",
    "model": "crm.lead",
    "view_type": "dashboard",
    "priority": 30,
    "inherit_mode": "extension",
    "inherit_id": "crm_dashboard",
    "module": "car_import",
    "inheritance_operations": [
        {
            "operation": "append",
            "target": "sections",
            "content": [
                {
                    "name": "car_import_funnel",
                    "title": _("Car import — the funnel"),
                    "subtitle": "Only leads on a car-import programme",
                    "groups": [
                        {"title": _("Leads by stage"), "components": [{
                            "type": "bar", "name": "ka_funnel_by_stage",
                            "subtitle": "Where the car-import leads are",
                            "on_click": "kanban",
                            "field": "stage__name", "measure": "id", "aggregation": "count",
                            "group_by": ["stage__name"], "domain": _KA}]},
                        {"title": _("Leads by programme"), "components": [{
                            "type": "pie", "name": "ka_leads_by_program",
                            "subtitle": "Initiative, personal, commercial, showroom…",
                            "field": "ka_program", "measure": "id", "aggregation": "count",
                            "group_by": ["ka_program"], "domain": _KA}]},
                        {"title": _("Paid or organic"), "components": [{
                            "type": "donut", "name": "ka_leads_by_origin",
                            "subtitle": "Did an advert bring this lead, or did they find us?",
                            "field": "lead_origin", "measure": "id", "aggregation": "count",
                            "group_by": ["lead_origin"], "domain": _KA}]},
                        {"title": _("Leads by campaign"), "components": [{
                            "type": "bar", "name": "ka_leads_by_campaign",
                            "subtitle": "Which advert produced the lead",
                            "on_click": "kanban",
                            "field": "utm_campaign__name", "measure": "id", "aggregation": "count",
                            "group_by": ["utm_campaign__name"], "domain": _KA_ATTRIBUTED}]},
                        {"title": _("Won deals by agent"), "components": [{
                            "type": "bar", "name": "ka_won_by_agent",
                            "subtitle": "Closed-won car-import leads per agent",
                            "field": "assigned_to__name", "measure": "id", "aggregation": "count",
                            "group_by": ["assigned_to__name"], "domain": _KA_WON}]},
                        {"title": _("Won deals by campaign"), "fullWidth": True, "components": [{
                            # Won counts need their own table: one aggregation per
                            # column over the whole group, so "leads AND won in
                            # one row" is not expressible (table_strategy.py:81).
                            "type": "table", "name": "ka_won_by_campaign",
                            "subtitle": "The adverts that turned into cars",
                            "fields": [
                                {"name": "utm_campaign__name", "string": _("Campaign"), "format": "text"},
                                {"name": "utm_source__name", "string": _("Source"), "format": "text"},
                                {"name": "id", "string": _("Won"), "format": "number",
                                 "aggregation": "count", "align": "right"},
                                {"name": "expected_revenue", "string": _("Revenue"),
                                 "format": "currency", "aggregation": "sum", "align": "right"},
                            ],
                            "group_by": ["utm_campaign__name", "utm_source__name"],
                            "limit": 15, "order_by": "-expected_revenue",
                            "domain": {"operator": "and", "filters": [
                                {"field": "ka_program", "operator": "is_not_null"},
                                {"field": "utm_campaign", "operator": "is_not_null"},
                                {"field": "stage__is_won", "operator": "eq", "value": True}]}}]},
                    ],
                },
            ],
        }
    ],
}
