# -*- coding: utf-8 -*-
"""The stage's Arabic label becomes `name`.

The form's status header resolves its options through
``UIView._extract_status_from_combined_view``, which reads ``record.name`` off
the related model (`modules/base/models/ui_view.py:1146`). A stage that called
its label `name_ar` therefore broke the whole deal form — the view loader
swallowed the AttributeError and the page answered "No form view found for this
menu item". Every other stage table in the platform (crm.Stage) calls it `name`;
this one now does too.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('car_import', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='importstage',
            old_name='name_ar',
            new_name='name',
        ),
        migrations.AlterField(
            model_name='importstage',
            name='name',
            field=models.CharField(max_length=128, verbose_name='Stage name'),
        ),
    ]
