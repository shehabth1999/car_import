# -*- coding: utf-8 -*-
"""Turn the lawyer's `.docx` files into templates the system can fill.

The client sent five contracts on 2026-09-16. This reads them, replaces each
blank with a named token, and stores the result as a `ContractTemplate` — after
which `Contract.generate()` produces a real, filled, signable document.

The rules below are written out by hand, grouped by what each clause is for and
anchored on the clause's own words. That is deliberate. A regex clever enough to
guess which blank is the customer's name and which is his national ID is a regex
that will guess wrong on the next version of the contract, silently, into a
document somebody signs. Anchored rules cannot: a clause nothing matched is
named in the output, and the person importing decides whether that contract
simply has no such clause or whether the client reworded it.

    uv run python manage.py import_contract_templates --dir "/path/to/docx"
    uv run python manage.py import_contract_templates --dir ... --inspect
"""
import os

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

#: filename fragment -> (code, human name, programme)
KNOWN = [
    ('عقد استيراد شخصي', 'personal_import', 'عقد استيراد شخصي', 'personal'),
    ('توفير مبادرة', 'initiative_supply', 'عقد استيراد مع توفير مبادرة', 'initiative'),
    ('عقد مبادرة', 'initiative', 'عقد مبادرة', 'initiative'),
]

#: The clauses, grouped by what they are *for*. Each group lists every wording
#: the client's five files actually use, because they are five drafts of the
#: same contract and no two word a clause identically: one says "acknowledges
#: receiving", another folds the same three amounts into one sentence, a third
#: says "notices shall be sent to" where the others say "the email is".
#:
#: Grouping matters for the reporting, not just the matching. A flat list makes
#: an initiative contract — which has no car clause at all — report five
#: "missing" anchors on every import, and an error people see every time is an
#: error people stop reading. A group is satisfied when ANY of its wordings
#: matched, and a group that legitimately does not apply is reported as absent
#: rather than broken.
RULE_GROUPS = [
    ('the date', [
        ('أنه في يوم', ['contract_day', 'contract_month']),
        ('On this day', ['contract_day', 'contract_month']),
    ]),
    ('the customer', [
        ('ويحمل بطاقة رقم قومي رقم',
         ['customer_name', 'customer_national_id', 'customer_address']),
        ('بطاقة رقم قومي / ',
         ['customer_name', 'customer_national_id', 'customer_address']),
        ('holder of National ID No',
         ['customer_name', 'customer_national_id', 'customer_address']),
    ]),
    ('whose name it ships in', [
        ('وشحنها باسم السيد', ['shipping_name']),
        ('hereas, the Second Party desires', ['shipping_name']),
    ]),
    ('the car', [
        ('شراء سيارة', ['car_model', 'car_trim', 'car_configuration']),
        ('The First Party agrees to purchase',
         ['car_model', 'car_trim', 'car_configuration']),
    ]),
    ('the total', [
        ('إجمالي القيمة التعاقدية للسيارة', ['contract_total_eur']),
        # Two shapes: some files put the total alone, others fold the down
        # payment and the balance into the same sentence. Listing all three
        # tokens is safe either way — the extra ones simply find no blank.
        ('total contractual value of the vehicle',
         ['contract_total_eur', 'contract_down_payment_eur', 'contract_balance_eur']),
    ]),
    ('what was paid at signing', [
        ('بإستلامه من الطرف الثاني', ['contract_down_payment_eur', 'contract_balance_eur']),
        ('acknowledges receiving', ['contract_down_payment_eur', 'contract_balance_eur']),
    ]),
    ('the bank transfer', [
        ('يُحول بنكياً من حساب الطرف الثاني', ['contract_bank_transfer_eur']),
        ('via bank transfer from the Second Party', ['contract_bank_transfer_eur']),
        ('transferred via bank wire', ['contract_bank_transfer_eur']),
    ]),
    ('the cash on the bill of lading', [
        ('يُسدد نقداً فور إصدار بوليصة الشحن', ['contract_cash_on_bl_eur']),
        ('in cash immediately upon the issuance', ['contract_cash_on_bl_eur']),
    ]),
    ('the deposit percentage', [
        ('دفعة الجدية المقدرة بـ', ['deposit_pct']),
        ('paying the down payment of', ['deposit_pct']),
        ('By signing and paying the', ['deposit_pct']),
    ]),
    ("the customer's email", [
        ('في حالة الإرسال إلى الطرف الثاني', ['customer_email']),
        ('For the Second Party, the email is', ['customer_email']),
        ('For the Second Party, notices shall be sent', ['customer_email']),
    ]),
]

#: Fixed text the contract hard-codes, swapped inside anchored paragraphs only.
#: The year is hard-coded twice and the two halves of the same document
#: disagree — the Arabic says 2026 and the English says 2025. Tokenising both
#: means the generated contract cannot carry that contradiction forward.
LITERALS = [
    ('أنه في يوم', [('2026', 'contract_year')]),
    ('On this day', [('2026', 'contract_year'), ('2025', 'contract_year')]),
    ('شراء سيارة', [('2026', 'car_model_year'), ('2025', 'car_model_year')]),
    ('The First Party agrees to purchase',
     [('2026', 'car_model_year'), ('2025', 'car_model_year')]),
]

#: Annex 1's payment schedule: three identical date paragraphs, told apart only
#: by their order — which is exactly what a payment schedule means.
ANNEX_DATE_TEXT = '…… / …….. / 2026'
ANNEX_DATE_TOKENS = ['instalment_1_date', 'instalment_2_date', 'instalment_3_date']
ANNEX_AMOUNT_TOKENS = ['instalment_1_amount', 'instalment_2_amount', 'instalment_3_amount']


class Command(BaseCommand):
    help = "Import the client's contract .docx files as fillable templates"

    def add_arguments(self, parser):
        parser.add_argument('--dir', required=True, help="Folder holding the .docx files")
        parser.add_argument('--inspect', action='store_true',
                            help="Only report the blanks found; write nothing")

    def handle(self, *args, **options):
        from car_import.models import ContractTemplate
        from car_import.services import contract_docx

        folder = options['dir']
        files = sorted(f for f in os.listdir(folder) if f.lower().endswith('.docx')
                       and not f.startswith('~$'))
        if not files:
            self.stderr.write(f'No .docx files in {folder}')
            return

        for filename in files:
            with open(os.path.join(folder, filename), 'rb') as handle:
                data = handle.read()

            if options['inspect']:
                self.stdout.write(self.style.NOTICE(f'\n{filename}'))
                for index, text, count in contract_docx.blanks_in(data):
                    self.stdout.write(f'  [{index:3}] {count} blank(s)  {text[:110]}')
                continue

            match = next((k for k in KNOWN if k[0] in filename), None)
            if match is None:
                self.stdout.write(self.style.WARNING(
                    f'{filename}: no rule set for this file — skipped.'))
                continue
            _fragment, code, name, program = match
            # Two files map onto the same programme; the one whose name carries
            # "(Configuration)" is the version the lawyer marked as the fill-in
            # master, so it wins.
            is_master = 'configuration' in filename.lower()

            tokenised, applied, absent = _tokenise_groups(contract_docx, data)
            tokenised = contract_docx.replace_literals(tokenised, LITERALS)
            tokenised = contract_docx.repeat_rule(tokenised, ANNEX_DATE_TEXT,
                                                  ANNEX_DATE_TOKENS)
            tokenised = contract_docx.fill_table_row(tokenised, 'Amount',
                                                     ANNEX_AMOUNT_TOKENS)

            tokens = sorted({t for t in _tokens_in(contract_docx, tokenised)})
            row, created = ContractTemplate.objects.update_or_create(
                code=code if is_master else f'{code}_reference',
                defaults={
                    'name': name + ('' if is_master else ' (نسخة مرجعية)'),
                    'program': program,
                    'source_filename': filename,
                    'is_fillable': is_master,
                    'tokens': tokens,
                },
            )
            row.docx.save(f'{row.code}.docx', ContentFile(tokenised), save=True)

            self.stdout.write(self.style.SUCCESS(
                f'{filename}\n  -> {row.code} ({"new" if created else "updated"}), '
                f'{applied} clause(s) tokenised, {len(tokens)} field(s)'))
            if absent:
                # Not necessarily an error: an initiative-supply contract has no
                # car clause, so "the car" being absent from it is the truth.
                # It IS worth printing, because the other reading — that the
                # client reworded a clause and its blank will now be signed
                # empty — looks exactly the same from here.
                self.stdout.write(self.style.WARNING(
                    '  no clause found for: ' + ', '.join(absent)))
                self.stdout.write(
                    '  (fine when this contract genuinely has no such clause; '
                    'check the wording if it does)')


def _tokenise_groups(contract_docx, data):
    """Apply every group, and report the ones nothing matched."""
    applied, absent = 0, []
    for label, alternatives in RULE_GROUPS:
        result, hits, _missing = contract_docx.tokenise(data, alternatives)
        if hits:
            data = result
            applied += hits
        else:
            absent.append(label)
    return data, applied, absent


def _tokens_in(contract_docx, data):
    import re
    return re.findall(r'\{\{(\w+)\}\}', ' '.join(contract_docx.paragraphs(data)))
