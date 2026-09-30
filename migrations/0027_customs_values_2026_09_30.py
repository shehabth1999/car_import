# The customs figures the owner sent on 2026-09-30 for the new 2026 cars most
# asked for and available now — the amount payable, in EUR. Five replace the
# workbook's values (kept in the note), six are new. A model missing from the
# catalogue is skipped, never invented; the offer then says customs are
# confirmed before contracting.

import re
from datetime import date

from django.db import migrations

YEAR = 2026
SOURCE = "owner's customs list 2026-09-30"
VALUES = [
    ('C180', 13500), ('C200', 14500), ('CLA 200', 14000), ('GLA 200', 14000), ('GLB 200', 15000),
    ('E200', 31000), ('GLC 200', 31500), ('GLC 300', 32000), ('GLC 43', 37500), ('G 63', 115000),
    # The owner wrote S580L; the catalogue has one S 580.
    ('S 580', 112000),
]


def _key(text):
    return re.sub(r'\s+', '', str(text or '')).lower()


def load(apps, schema_editor):
    CarModel = apps.get_model('car_import', 'CarModel')
    CustomsValuation = apps.get_model('car_import', 'CustomsValuation')
    mercedes = list(CarModel.objects.filter(brand__name__iexact='Mercedes-Benz'))
    for name, value in VALUES:
        model = next((m for m in mercedes if _key(m.name) == _key(name)), None)
        if model is None:
            continue
        row = CustomsValuation.objects.filter(car_model=model, model_year=YEAR).first()
        if row is None:
            CustomsValuation.objects.create(car_model=model, model_year=YEAR, value_eur=value, basis='payable',
                                            effective_from=date(2026, 9, 30), source_note=SOURCE)
            continue
        if row.value_eur is not None and int(row.value_eur) != value:
            note = f'{SOURCE} (was {int(row.value_eur):,} € — {row.source_note or "earlier"})'
        else:
            note = SOURCE
        row.value_eur = value
        row.basis = 'payable'
        row.effective_from = date(2026, 9, 30)
        row.effective_to = None
        row.source_note = note[:190]
        row.save()


class Migration(migrations.Migration):

    dependencies = [
        ('car_import', '0026_quote_own_initiative'),
    ]

    operations = [
        migrations.RunPython(load, migrations.RunPython.noop),
    ]
