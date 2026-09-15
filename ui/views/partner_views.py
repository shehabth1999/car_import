# -*- coding: utf-8 -*-
"""What car_import adds to the contact form.

The module has been putting ten identity fields on `base.Partner` since the
first install — national ID, passport, nationality, address on the ID, country
of residence, expatriate flag, initiative status, budget band, documents
complete, media consent — and not one of them had a screen. Exactly the same
oversight as the lead: the column existed, the field was invisible, and nobody
could fill in what the contract generator will need.

The identity block is restricted to management and operations. The client's
brief treats a customer's national ID and passport as confidential, and this is
the layer that decides who can read them on a screen.

Strings are {"en", "ar"} dicts: labels inside `inheritance_operations` are not
translated at sync, only the view body is.
"""

partner_form_car_import_batch = {
    "key": "partner_form_car_import_batch",
    "name": "Contact form — car import identity",
    "model": "base.partner",
    "view_type": "form",
    "priority": 26,
    "inherit_mode": "extension",
    "inherit_id": "base_partner_form_view",
    # The module that owns the BASE view, not the one that owns this patch.
    "module": "contacts",
    "inheritance_operations": [
        {
            "operation": "append",
            "target": "sheet.tabs",
            "content": {
                "title": {"en": "Car import", "ar": "استيراد السيارات"},
                "allowed_groups": ["car_import.management", "car_import.operations",
                                   "car_import.sales_manager"],
                "sections": [
                    {
                        "title": {"en": "Identity — needed for the contract",
                                  "ar": "بيانات الهوية — مطلوبة للعقد"},
                        "groups": [
                            {
                                "title": "",
                                "fields": [
                                    {"name": "national_id",
                                     "string": {"en": "National ID", "ar": "الرقم القومي"},
                                     "widget": "text"},
                                    {"name": "passport_number",
                                     "string": {"en": "Passport number", "ar": "رقم الباسبور"},
                                     "widget": "text"},
                                    {"name": "nationality",
                                     "string": {"en": "Nationality", "ar": "الجنسية"},
                                     "widget": "text"},
                                    {"name": "id_address",
                                     "string": {"en": "Address on the ID", "ar": "العنوان في البطاقة"},
                                     "widget": "text"},
                                ],
                            },
                            {
                                "title": "",
                                "fields": [
                                    {"name": "residence_country",
                                     "string": {"en": "Country of residence", "ar": "بلد الإقامة"},
                                     "widget": "text"},
                                    {"name": "is_expat",
                                     "string": {"en": "Egyptian abroad", "ar": "مصري بالخارج"},
                                     "widget": "switch"},
                                    {"name": "initiative_status",
                                     "string": {"en": "Initiative", "ar": "المبادرة"},
                                     "widget": "text"},
                                    {"name": "budget_band",
                                     "string": {"en": "Budget", "ar": "الميزانية"},
                                     "widget": "text"},
                                ],
                            },
                        ],
                    },
                    {
                        "title": {"en": "Consent and paperwork", "ar": "الموافقات والورق"},
                        "groups": [
                            {
                                "title": "",
                                "fields": [
                                    {"name": "kyc_complete",
                                     "string": {"en": "Documents complete", "ar": "المستندات مكتملة"},
                                     "widget": "switch"},
                                    {"name": "media_consent",
                                     "string": {"en": "Agreed to appear in content",
                                                "ar": "موافق على التصوير"},
                                     "widget": "switch"},
                                    # The one switch a customer owns: it outranks
                                    # every switch the company has.
                                    {"name": "stage_messages_opt_out",
                                     "string": {"en": "No automatic updates",
                                                "ar": "مش عايز رسايل تلقائية"},
                                     "widget": "switch"},
                                ],
                            },
                        ],
                    },
                ],
            },
        },
    ],
}
