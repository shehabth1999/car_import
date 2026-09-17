# -*- coding: utf-8 -*-
"""Money is a number plus a currency ROW, never a text code.

Every field that held a currency as text becomes a relation to
`base.Currency`, backfilled by code; the quotation, the contract and the
consignment mandate gain one (EUR, EUR, EGP). Written by hand so the rename,
the add, the backfill and the drop travel together — `makemigrations` would
have read a renamed column as "remove and add" and thrown the codes away.
"""
import django.db.models.deletion
from django.db import migrations, models

#: (model, text field holding the code, new relation field, code when blank)
CONVERT = [
    ('cardeal', 'currency_note', 'currency', 'EUR'),
    ('approvalpolicy', 'currency_code', 'currency', 'EUR'),
    ('approvalrequest', 'currency_code', 'currency', 'EUR'),
    ('quoteline', 'currency_code', 'currency', 'EUR'),
    ('feeschedule', 'currency_code', 'currency', 'EUR'),
    ('fxreference', 'currency_from_code', 'currency_from', 'EUR'),
    ('fxreference', 'currency_to_code', 'currency_to', 'EGP'),
]
#: (model, new relation field, default code)
NEW = [
    ('quote', 'currency', 'EUR'),
    ('contract', 'currency', 'EUR'),
    ('consignmentmandate', 'currency', 'EGP'),
]


def _fk(verbose_name):
    return models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                             related_name='+', to='base.currency', verbose_name=verbose_name)


def backfill(apps, schema_editor):
    Currency = apps.get_model('base', 'Currency')
    by_code = {(c.code or '').upper(): c.pk for c in Currency.objects.all()}
    for model, source, target, default in CONVERT:
        Model = apps.get_model('car_import', model)
        for row in Model.objects.all():
            code = (getattr(row, source, None) or default or '').strip().upper()
            pk = by_code.get(code) or by_code.get(default)
            if pk:
                Model.objects.filter(pk=row.pk).update(**{f'{target}_id': pk})
    for model, target, default in NEW:
        Model = apps.get_model('car_import', model)
        pk = by_code.get(default)
        if pk:
            Model.objects.filter(**{f'{target}__isnull': True}).update(**{f'{target}_id': pk})


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0025_backfill_partner_last_seen'),
        ('car_import', '0017_alter_approvalpolicy_subject_and_more'),
    ]

    operations = [
        # step 1 — the text columns step aside under a temporary name
        migrations.RenameField('approvalpolicy', 'currency', 'currency_code'),
        migrations.RenameField('approvalrequest', 'currency', 'currency_code'),
        migrations.RenameField('quoteline', 'currency', 'currency_code'),
        migrations.RenameField('feeschedule', 'currency', 'currency_code'),
        migrations.RenameField('fxreference', 'currency_from', 'currency_from_code'),
        migrations.RenameField('fxreference', 'currency_to', 'currency_to_code'),
        # step 2 — the relations
        migrations.AddField('cardeal', 'currency', _fk('Currency')),
        migrations.AddField('approvalpolicy', 'currency', _fk('Currency')),
        migrations.AddField('approvalrequest', 'currency', _fk('Currency')),
        migrations.AddField('quoteline', 'currency', _fk('Currency')),
        migrations.AddField('feeschedule', 'currency', _fk('Currency')),
        migrations.AddField('fxreference', 'currency_from', _fk('From')),
        migrations.AddField('fxreference', 'currency_to', _fk('To')),
        migrations.AddField('quote', 'currency', _fk('Currency')),
        migrations.AddField('contract', 'currency', _fk('Currency')),
        migrations.AddField('consignmentmandate', 'currency', _fk('Currency')),
        # step 3 — the codes become rows
        migrations.RunPython(backfill, migrations.RunPython.noop),
        # step 4 — the text is gone
        migrations.RemoveField('cardeal', 'currency_note'),
        migrations.RemoveField('approvalpolicy', 'currency_code'),
        migrations.RemoveField('approvalrequest', 'currency_code'),
        migrations.RemoveField('quoteline', 'currency_code'),
        migrations.RemoveField('feeschedule', 'currency_code'),
        migrations.RemoveField('fxreference', 'currency_from_code'),
        migrations.RemoveField('fxreference', 'currency_to_code'),
    ]
