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
     # Arabic, because these strings are read by Arabic-speaking agents on an
     # internal briefing screen — an English sentence dropped into the middle
     # of an Arabic paragraph is a sentence people skip.
     'first_instalment_note': 'أول قسط بعد التسليم بشهر',
     'covers': 'كل حاجة لحد باب العميل ما عدا الترخيص',
     'not_available_when': 'العميل هو صاحب المبادرة نفسه'},
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


# From the client's own calculator (New Quotation.xlsx, 2026-09-16), cell B16
# for the admin fee and B20 for the deposit. The bands are reproduced exactly,
# including the two things that look wrong and are not: the cheapest band's
# admin fee is a DISCOUNT of 750, and the deposit percentage is not monotonic.
PRICING_BANDS = [
    ('0 – 30,000 €',       0,     30000, 'fixed',          -750, 15),
    ('30,001 – 48,000 €',  30001, 48000, 'fixed',             0, 25),
    ('48,001 – 59,000 €',  48001, 59000, 'percent_of_net',  3.0, 25),
    ('59,001 – 88,000 €',  59001, 88000, 'percent_of_net',  5.7, 15),
    ('88,001 € and above', 88001,  None, 'percent_of_net',  6.5, 15),
]

# The fees the calculator and the owner's message name. Ports differ by more
# than the sheet's note admits: it says "about 50,000 EGP", the owner says
# Alexandria 55,000 and Port Said 105,000 — twice the money.
CALCULATOR_FEES = [
    {'code': 'shipping_cost', 'name': 'مصاريف الشحن', 'amount': 4750, 'currency': 'EUR'},
    {'code': 'eur1_certificate', 'name': 'شهادة يورو 1', 'amount': 550, 'currency': 'EUR',
     'applies_to': 'with_eur1'},
    {'code': 'shipping_vip_roro', 'name': 'شحن VIP RORO', 'amount': 250, 'currency': 'EUR',
     'applies_to': 'optional'},
    {'code': 'shipping_container', 'name': 'شحن بالحاوية', 'amount': 1000, 'currency': 'EUR',
     'applies_to': 'optional'},
    {'code': 'port_alexandria', 'name': 'مصاريف ميناء الإسكندرية', 'amount': 55000,
     'currency': 'EGP', 'notes': 'Collected on arrival, in Egypt.'},
    {'code': 'port_said', 'name': 'مصاريف ميناء بورسعيد', 'amount': 105000, 'currency': 'EGP',
     'notes': 'Collected on arrival, in Egypt.'},
    {'code': 'showroom_collection', 'name': 'الاستلام من المعرض', 'amount': 5000,
     'currency': 'EGP', 'applies_to': 'optional'},
]


# The client's approval matrix (process map §6), as rows. The column heading in
# their own document is "Never decided by an agent or the AI", and until this
# existed the matrix described a company the software did not implement.
# `None` as a threshold means "always", which is how most of them are worded:
# ANY discount on the company fees, ANY non-standard schedule.
APPROVALS = [
    ('car_discount', 'خصم على سعر العربية أكتر من 500 يورو', 500, 'EUR'),
    ('fee_discount', 'أي خصم على مصاريف الشركة', None, 'EUR'),
    ('payment_schedule', 'أي جدول سداد غير القياسي', None, 'EUR'),
    ('cancellation', 'الإلغاء والاسترداد والتسوية (البند السابع)', None, 'EUR'),
    ('fx_rate', 'سعر التحويل وعمولته 1.5–2%', None, 'EGP'),
    ('bank_details', 'إعطاء بيانات الحساب البنكي', None, 'EUR'),
    ('complaint', 'شكوى حالة أو مواصفة ناقصة أو ضرر', None, 'EUR'),
    ('sourcing_outside_eu', 'الشراء من خارج ألمانيا أو الاتحاد الأوروبي', None, 'EUR'),
    ('contract_signature', 'التوقيع على العقد', None, 'EUR'),
]


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

            from car_import.models import PricingBand
            made = 0
            for seq, (name, low, high, fee_type, fee_value, deposit) in enumerate(PRICING_BANDS, 1):
                _row, m = PricingBand.objects.update_or_create(
                    name=name,
                    defaults={'sequence': seq * 10, 'gross_from_eur': low, 'gross_to_eur': high,
                              'admin_fee_type': fee_type, 'admin_fee_value': fee_value,
                              'deposit_pct': deposit, 'effective_from': date(2026, 9, 16),
                              'source_note': "the client's calculator, 2026-09-16"})
                made += bool(m)
            counts['pricing bands'] = f'{made} new'

            for data in CALCULATOR_FEES:
                FeeSchedule.objects.update_or_create(
                    code=data['code'],
                    defaults=dict({k: v for k, v in data.items() if k != 'code'},
                                  effective_from=date(2026, 9, 16),
                                  source_note="the client's calculator, 2026-09-16"))
            counts['calculator fees'] = len(CALCULATOR_FEES)

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

            # The showroom's winter hours, confirmed by the client 2026-09-16:
            # 9am to 9pm. They happen to match what the quiet-hours code always
            # defaulted to — written down anyway, because a default nobody
            # recorded is a default the next person changes by accident, and
            # this one decides whether a customer's phone lights up at 3am.
            from modules.base.models import ConfigParameter
            for key, value, note in (
                ('car_import.quiet_hours_start', '21',
                 'Showroom closes at 9pm (winter hours, client 2026-09-16)'),
                ('car_import.quiet_hours_end', '9',
                 'Showroom opens at 9am (winter hours, client 2026-09-16)'),
            ):
                ConfigParameter.objects.update_or_create(
                    key=key, defaults={'value': value, 'description': note})
            counts['quiet hours'] = '09:00 – 21:00 (client, 2026-09-16)'

            from car_import.models import ApprovalPolicy
            for subject, name, threshold, currency in APPROVALS:
                ApprovalPolicy.objects.update_or_create(
                    subject=subject,
                    defaults={'name': name, 'threshold_amount': threshold,
                              'currency': currency, 'approver_group': 'car_import.management',
                              'is_active': True, 'effective_from': CONFIRMED,
                              'source_note': "the client's approval matrix"})
            counts['approval rules'] = len(APPROVALS)

            # K&T's legal identity, taken from the contracts they sent rather
            # than asked for again — every value below is printed in their own
            # templates. The signatory is a separate row because he changes.
            from car_import.models import ContractIssuer, ContractSignatory
            issuer, _made = ContractIssuer.objects.update_or_create(
                code='kt',
                defaults={
                    'name': 'شركة كيه آند تي (K&T) لبيع السيارات لحساب الغير',
                    'name_en': 'K&T Company for car sales on behalf of third parties',
                    'commercial_register': '230794',
                    'chamber': 'غرفة القاهرة التجارية',
                    'tax_card': '368-740-761',
                    'represents': 'مجموعة شركات خالد أوتوموبيل المحدودة',
                    'legal_rep_name': 'خالد صابر عبد الرحمن عبد الله',
                    'legal_rep_national_id': '27912030100833',
                    'email': 'Info@khaledautomobile.de',
                    'is_default': True,
                })
            ContractSignatory.objects.update_or_create(
                issuer=issuer, name='احمد فايز جميل نايف',
                defaults={'national_id': '29008138800679',
                          'title': 'المفوض بالتوقيع', 'is_default': True})
            counts['contract issuer'] = 'K&T + 1 signatory'

        for label, value in counts.items():
            self.stdout.write(f'  {label}: {value}')

        if dry:
            self.stdout.write(self.style.WARNING('Dry run — nothing written.'))
            return

        self.stdout.write(self.style.SUCCESS('\nReference data seeded.'))
        self.stdout.write(
            'Deliberately NOT seeded, because the client has not confirmed it:\n'
            '  · bank financing terms\n'
            'The pricing engine refuses rather than guesses while that is missing.\n\n'
            'Answered since, and seeded:\n'
            '  · the deposit formula — their own calculator, 2026-09-16\n'
            '  · the customs basis — the workbook figures are the amount actually PAID '
            '(question V1, answered 2026-09-16), and they move when the government '
            'moves them, which is what the dates on these rows are for\n'
            'Run `price_car --check` to prove the calculator still matches their sheet.')
