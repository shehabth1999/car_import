# -*- coding: utf-8 -*-
"""Seed the rules the client has actually confirmed — and only those.

Everything written here traces to a dated answer from the owner (2026-09-14 /
2026-09-15). Anything still open is left ABSENT rather than guessed: an empty
table makes the pricing engine refuse, while a plausible wrong number makes it
quote confidently and be wrong by a factor.

Idempotent: run it as often as you like.
"""
from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

CONFIRMED = date(2026, 9, 14)
SOURCE = "owner's answers 2026-09-14/15"

PROGRAMS = [
    {'code': 'initiative', 'name': 'مبادرة المصريين بالخارج', 'name_en': 'Expatriate initiative',
     'sequence': 10, 'min_model_year': 2023, 'instalments_allowed': True,
     'notes': 'Registration for new participants closed in 2024. Instalments are refused when '
              'the customer is the initiative holder himself: clearance is in his name, so the '
              'company has no lien on the car.'},
    {'code': 'personal', 'name': 'استيراد شخصي', 'name_en': 'Personal import',
     'sequence': 20, 'requires_zero_km': True, 'requires_current_model_year': True},
    {'code': 'commercial', 'name': 'استيراد تجاري', 'name_en': 'Commercial import',
     'sequence': 30, 'requires_zero_km': True, 'requires_current_model_year': True,
     'requires_management_approval': True},
    {'code': 'first_owner', 'name': 'أول مالك', 'name_en': 'First owner',
     'sequence': 40, 'notes': '5% discount per year of ownership, between five and nine years.'},
    {'code': 'disability', 'name': 'سيارات ذوي الهمم', 'name_en': 'Disability route',
     'sequence': 50, 'is_blocked': True,
     'blocked_reason': 'Suspended by law — refuse, and never quote.'},
    {'code': 'showroom', 'name': 'من المعرض', 'name_en': 'Showroom car',
     'sequence': 60, 'notes': 'A car already in Egypt.'},
    {'code': 'shipping_only', 'name': 'شحن فقط', 'name_en': 'Shipping only',
     'sequence': 70, 'notes': 'The customer sources the car; the company ships and clears it.'},
]

# 19 / 38 / 66 with EUR 1, and 66 / 135 / 241 without — by engine size band.
TAX_BANDS = [
    (0, 1600, 19, 66),
    (1601, 2000, 38, 135),
    (2001, None, 66, 241),
]

FEES = [
    {'code': 'company_fee', 'name': 'أتعاب الشركة', 'amount': 4750, 'currency': 'EUR'},
    {'code': 'company_fee_eur1', 'name': 'أتعاب الشركة مع شهادة يورو 1', 'amount': 5250,
     'currency': 'EUR', 'applies_to': 'with_eur1'},
    {'code': 'port_and_clearance', 'name': 'الميناء والتخليص', 'amount': 55000, 'currency': 'EGP',
     'notes': 'Indicative at today’s rate.'},
    {'code': 'powers_of_attorney', 'name': 'التوكيلات', 'amount': 300, 'currency': 'USD'},
    {'code': 'licensing_service', 'name': 'خدمة مندوب الترخيص', 'amount': 3000, 'currency': 'EGP'},
    {'code': 'protection_film', 'name': 'فيلم الحماية', 'amount': 65000, 'amount_to': 75000,
     'currency': 'EGP', 'applies_to': 'optional'},
    # The licence cost itself is never quoted — the client's own rule. The row
    # exists so the refusal has somewhere to point.
    {'code': 'licence_cost', 'name': 'تكلفة الرخصة نفسها', 'amount': None, 'currency': 'EGP',
     'applies_to': 'on_request', 'quotable_to_customer': False,
     'notes': 'Depends on the car; refer the customer to the licensing office. Never quote.'},
]

FINANCING = [
    {'code': 'direct_instalments', 'name': 'تقسيط الشركة', 'down_payment_pct': 50,
     'term_months': [12, 24], 'rate_pct_flat': 27, 'cheques_required': True,
     'first_instalment_note': 'One month after delivery',
     'covers': 'Everything to the customer’s door except licensing',
     'not_available_when': 'The customer is the initiative holder himself'},
    {'code': 'bank_financing', 'name': 'تمويل بنكي', 'available': False,
     'notes': 'For cars already in Egypt. Terms not yet supplied by the client.'},
    {'code': 'cash', 'name': 'كاش', 'down_payment_pct': 100, 'term_months': []},
]


# The checklists the eligibility tool has been reciting since day one, now as
# rows somebody can tick. Confirmed with the owner on 2026-09-14.
DOCUMENTS = {
    None: [                      # every route
        ('national_id_front_back', 'صورة البطاقة وش وضهر', True, False, True),
        ('passport', 'الباسبور', True, True, True),
    ],
    'initiative': [
        ('residence_permit', 'الإقامة', True, True, True),
        ('bank_statement_6m', 'كشف حساب 6 شهور فيه تحويل الوديعة', True, False, True),
        ('deposit_receipts', 'إيصالات الوديعة', True, False, False),
        ('import_approval', 'الموافقة الاستيرادية', True, False, False),
        ('customs_broker_poa', 'توكيل المخلص الجمركي', True, False, False),
        ('ownership_transfer_poa', 'توكيل نقل الملكية', False, False, False),
        ('licensing_poa', 'توكيل الترخيص', False, False, False),
    ],
    'personal': [
        ('eur1_certificate', 'شهادة يورو 1', False, False, False),
        ('coc_and_papers', 'شهادة المطابقة وأوراق العربية', True, False, False),
        ('acid_permit', 'رقم ACID', True, False, False),
        ('bill_of_lading', 'بوليصة الشحن', True, False, False),
    ],
}
DOCUMENTS['commercial'] = DOCUMENTS['personal']


class Command(BaseCommand):
    help = "Seed the confirmed programmes, tax bands, fees, financing plans and EUR 1 rule"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        from car_import.models import (Eur1Rule, FeeSchedule, FinancingPlan,
                                       FirstOwnerDiscount, ImportProgram, TaxRule)

        dry = options['dry_run']
        counts = {}

        def upsert(model, lookup, defaults):
            defaults = dict(defaults, effective_from=CONFIRMED, source_note=SOURCE)
            if dry:
                exists = model.objects.filter(**lookup).exists()
                return None, not exists
            return model.objects.update_or_create(**lookup, defaults=defaults)

        created = 0
        for data in PROGRAMS:
            _row, made = upsert(ImportProgram, {'code': data['code']},
                                {k: v for k, v in data.items() if k != 'code'})
            created += bool(made)
        counts['programmes'] = f'{len(PROGRAMS)} ({created} new)'

        if not dry:
            made = 0
            for code in ('initiative', 'personal', 'commercial', 'first_owner'):
                program = ImportProgram.objects.filter(code=code).first()
                if not program:
                    continue
                for cc_min, cc_max, with_eur1_rate, without_rate in TAX_BANDS:
                    for with_eur1, rate in ((True, with_eur1_rate), (False, without_rate)):
                        _row, m = TaxRule.objects.update_or_create(
                            program=program, cc_min=cc_min, cc_max=cc_max, with_eur1=with_eur1,
                            defaults={'rate_pct': rate, 'effective_from': CONFIRMED,
                                      'source_note': SOURCE})
                        made += bool(m)
            counts['tax rules'] = f'{made} new'

            Eur1Rule.objects.update_or_create(
                name='EUR 1',
                defaults={'eligible_residencies': ['EU', 'UK', 'TR'],
                          'notes': 'Built in the EU, built for the EU market, and exported from an '
                                   'EU port — all three, or the certificate does not apply.',
                          'effective_from': CONFIRMED, 'source_note': SOURCE})
            counts['EUR 1 rule'] = 'set'

            for data in FEES:
                FeeSchedule.objects.update_or_create(
                    code=data['code'],
                    defaults=dict({k: v for k, v in data.items() if k != 'code'},
                                  effective_from=CONFIRMED, source_note=SOURCE))
            counts['fees'] = len(FEES)

            for data in FINANCING:
                FinancingPlan.objects.update_or_create(
                    code=data['code'],
                    defaults=dict({k: v for k, v in data.items() if k != 'code'},
                                  effective_from=CONFIRMED, source_note=SOURCE))
            counts['financing plans'] = len(FINANCING)

            for years in range(5, 10):
                FirstOwnerDiscount.objects.update_or_create(
                    years_owned=years,
                    defaults={'discount_pct': 5 * years, 'effective_from': CONFIRMED,
                              'source_note': SOURCE})
            counts['first-owner discounts'] = 5

            from car_import.models import DocumentRequirement
            made = 0
            for code, rows in DOCUMENTS.items():
                program = ImportProgram.objects.filter(code=code).first() if code else None
                if code and program is None:
                    continue
                for sequence, (doc_code, name, mandatory, expires, sensitive) in enumerate(rows, 1):
                    _row, m = DocumentRequirement.objects.update_or_create(
                        code=doc_code, program=program,
                        defaults={'name': name, 'sequence': sequence * 10,
                                  'mandatory': mandatory, 'expires': expires,
                                  'is_sensitive': sensitive,
                                  'effective_from': CONFIRMED, 'source_note': SOURCE})
                    made += bool(m)
            counts['document requirements'] = f'{made} new'

        for label, value in counts.items():
            self.stdout.write(f'  {label}: {value}')

        if dry:
            self.stdout.write(self.style.WARNING('Dry run — nothing written.'))
            return

        self.stdout.write(self.style.SUCCESS('\nReference data seeded.'))
        self.stdout.write(
            'Deliberately NOT seeded, because the client has not confirmed them:\n'
            '  · the down-payment formula (questions F1–F3)\n'
            '  · whether the customs figure is the amount payable or the value the rate '
            'applies to (question V1)\n'
            '  · bank financing terms\n'
            'The pricing engine refuses rather than guesses while these are missing.')
