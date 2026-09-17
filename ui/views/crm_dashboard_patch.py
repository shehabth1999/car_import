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
4. **A new section cannot be `append`ed to `sections`.** A bare key is looked
   up as an element *type*, never as a key, so the target is silently "not
   found" (`ui_view.py:_find_target_elements`). Only a dotted path resolves a
   key, hence `after sections.4`: insert as a sibling of the last core section.

Scoped to the car-import leads (`ka_program` set, an extension field) so the
tenant's other funnels do not pile into these charts.

Labels are `{"en", "ar"}` dicts, not `_()`: the sync translates only a view's
own body, never the strings inside `inheritance_operations`, so a gettext
label here would stay English in the Arabic UI. Only `title` and `string` may
carry a dict — `_flatten_translations` localises `VIEW_TRANSLATABLE_KEYS` and
nothing else, and a dict left in `subtitle` reaches React as an object and
takes the whole dashboard page down (React #31). Subtitles are plain Arabic.
"""

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
            "operation": "after",
            "target": "sections.4",
            "content": {
                    "name": "car_import_funnel",
                    "title": {"en": "Car import — the funnel", "ar": "استيراد السيارات — القمع البيعي"},
                    "subtitle": "العملاء المحتملون على برامج استيراد السيارات فقط",
                    "groups": [
                        {"title": {"en": "Leads by stage", "ar": "العملاء المحتملون حسب المرحلة"}, "components": [{
                            "type": "bar", "name": "ka_funnel_by_stage",
                            "subtitle": "أين يقف عملاء الاستيراد المحتملون",
                            "on_click": "kanban",
                            "field": "stage__name", "measure": "id", "aggregation": "count",
                            "group_by": ["stage__name"], "domain": _KA}]},
                        {"title": {"en": "Leads by programme", "ar": "العملاء المحتملون حسب البرنامج"}, "components": [{
                            "type": "pie", "name": "ka_leads_by_program",
                            "subtitle": "مبادرة، شخصي، تجاري، معرض…",
                            "field": "ka_program", "measure": "id", "aggregation": "count",
                            "group_by": ["ka_program"], "domain": _KA}]},
                        {"title": {"en": "Paid or organic", "ar": "من إعلان أم بشكل طبيعي"}, "components": [{
                            "type": "donut", "name": "ka_leads_by_origin",
                            "subtitle": "هل جاء العميل من إعلان أم وجدنا بنفسه؟",
                            "field": "lead_origin", "measure": "id", "aggregation": "count",
                            "group_by": ["lead_origin"], "domain": _KA}]},
                        {"title": {"en": "Leads by campaign", "ar": "العملاء المحتملون حسب الحملة"}, "components": [{
                            "type": "bar", "name": "ka_leads_by_campaign",
                            "subtitle": "أي إعلان جاء بالعميل",
                            "on_click": "kanban",
                            "field": "utm_campaign__name", "measure": "id", "aggregation": "count",
                            "group_by": ["utm_campaign__name"], "domain": _KA_ATTRIBUTED}]},
                        {"title": {"en": "Won deals by agent", "ar": "الصفقات المكسوبة حسب المندوب"}, "components": [{
                            "type": "bar", "name": "ka_won_by_agent",
                            "subtitle": "صفقات الاستيراد المكسوبة لكل مندوب",
                            "field": "assigned_to__name", "measure": "id", "aggregation": "count",
                            "group_by": ["assigned_to__name"], "domain": _KA_WON}]},
                        {"title": {"en": "Won deals by campaign", "ar": "الصفقات المكسوبة حسب الحملة"}, "fullWidth": True, "components": [{
                            # Won counts need their own table: one aggregation per
                            # column over the whole group, so "leads AND won in
                            # one row" is not expressible (table_strategy.py:81).
                            "type": "table", "name": "ka_won_by_campaign",
                            "subtitle": "الإعلانات التي تحولت إلى سيارات",
                            "fields": [
                                {"name": "utm_campaign__name", "string": {"en": "Campaign", "ar": "الحملة"}, "format": "text"},
                                {"name": "utm_source__name", "string": {"en": "Source", "ar": "المصدر"}, "format": "text"},
                                {"name": "id", "string": {"en": "Won", "ar": "مكسوب"}, "format": "number",
                                 "aggregation": "count", "align": "right"},
                                {"name": "expected_revenue", "string": {"en": "Revenue", "ar": "الإيراد"},
                                 "format": "number", "aggregation": "sum", "align": "right"},
                            ],
                            "group_by": ["utm_campaign__name", "utm_source__name"],
                            "limit": 15, "order_by": "-expected_revenue",
                            "domain": {"operator": "and", "filters": [
                                {"field": "ka_program", "operator": "is_not_null"},
                                {"field": "utm_campaign", "operator": "is_not_null"},
                                {"field": "stage__is_won", "operator": "eq", "value": True}]}}]},
                    ],
            },
        }
    ],
}
