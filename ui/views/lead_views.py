# -*- coding: utf-8 -*-
"""What car_import adds to the CRM lead form.

The module already puts eleven qualification fields and an @action on the lead
(see `extensions.py`), but a field the form never draws is a field nobody can
fill, and an action no button calls is an action nobody can run. This patch is
the screen half of that work.

Strings here are written as {"en": …, "ar": …} on purpose: labels inside
`inheritance_operations` are NOT translated at sync — only the view body is —
so a `gettext` call here would ship English to an Arabic user.
"""

lead_form_car_import_batch = {
    "key": "lead_form_car_import_batch",
    "name": "Lead form — car import qualification",
    "model": "crm.lead",
    "view_type": "form",
    "priority": 25,
    "inherit_mode": "extension",
    "inherit_id": "crm_lead_form_view",
    # The module that owns the BASE view, not the one that owns this patch.
    "module": "crm",
    "inheritance_operations": [
        {
            "operation": "append",
            "target": "header.actions",
            "content": [
                {
                    "name": "action_create_car_deal",
                    "string": {"en": "Create car deal", "ar": "إنشاء صفقة سيارة"},
                    "type": "server",
                    "icon": "Car",
                    "as": "button",
                },
            ],
        },
        {
            "operation": "append",
            "target": "sheet.tabs",
            "content": {
                "title": {"en": "Car import", "ar": "استيراد السيارات"},
                "sections": [
                    {
                        "title": {"en": "What the customer wants",
                                  "ar": "العميل عايز إيه"},
                        "groups": [
                            {
                                "title": "",
                                "fields": [
                                    {"name": "ka_program",
                                     "string": {"en": "Programme", "ar": "البرنامج"},
                                     "widget": "text"},
                                    {"name": "ka_initiative_type",
                                     "string": {"en": "Initiative type", "ar": "نوع المبادرة"},
                                     "widget": "text"},
                                    {"name": "ka_model_wanted",
                                     "string": {"en": "Model wanted", "ar": "الموديل المطلوب"},
                                     "widget": "text"},
                                    {"name": "ka_model_year_wanted",
                                     "string": {"en": "Model year", "ar": "سنة الموديل"},
                                     "widget": "number"},
                                    {"name": "ka_trim_wanted",
                                     "string": {"en": "Trim", "ar": "الفئة"},
                                     "widget": "text"},
                                ],
                            },
                            {
                                "title": "",
                                "fields": [
                                    {"name": "ka_colour_wanted",
                                     "string": {"en": "Colour", "ar": "اللون"},
                                     "widget": "text"},
                                    {"name": "ka_condition_wanted",
                                     "string": {"en": "Zero or used", "ar": "زيرو ولا مستعملة"},
                                     "widget": "text"},
                                    {"name": "ka_budget_eur",
                                     "string": {"en": "Budget (EUR)", "ar": "الميزانية (يورو)"},
                                     "widget": "number"},
                                    {"name": "ka_funds_ready_on",
                                     "string": {"en": "Funds ready on", "ar": "الفلوس جاهزة في"},
                                     "widget": "date"},
                                ],
                            },
                        ],
                    },
                    {
                        "title": {"en": "Eligibility", "ar": "الأهلية"},
                        "groups": [
                            {
                                "title": "",
                                "fields": [
                                    # Written by ka_check_import_eligibility, so the
                                    # agent reads the verdict rather than retyping it.
                                    {"name": "ka_eligibility_verdict",
                                     "string": {"en": "Verdict", "ar": "النتيجة"},
                                     "widget": "text", "readonly": True},
                                    {"name": "ka_eligibility_reason",
                                     "string": {"en": "Why", "ar": "السبب"},
                                     "widget": "text", "readonly": True},
                                ],
                            },
                        ],
                    },
                ],
            },
        },
    ],
}
