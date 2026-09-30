# The programme on the quotation (owner, 2026-09-30): model year and condition
# decide it, it decides the port, and the offer states customs (personal
# import) or the initiative's deposit (initiative). All nullable / defaulted —
# every existing quotation keeps its port and its numbers.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('car_import', '0024_quote_document'),
    ]

    operations = [
        migrations.AddField(
            model_name='quote',
            name='programme',
            field=models.CharField(blank=True, choices=[('initiative', 'Initiative'),
                                                        ('personal', 'Personal import')],
                                   default='', max_length=16, verbose_name='Programme'),
        ),
        migrations.AddField(
            model_name='quote',
            name='model_year',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Model year'),
        ),
        migrations.AddField(
            model_name='quote',
            name='car_condition',
            field=models.CharField(blank=True, choices=[('new', 'Zero km'), ('used', 'Used')],
                                   default='', max_length=8, verbose_name='Condition'),
        ),
        migrations.AddField(
            model_name='quote',
            name='customs_eur',
            field=models.DecimalField(blank=True, decimal_places=2, editable=False, max_digits=12,
                                      null=True, verbose_name='Customs value'),
        ),
        migrations.AddField(
            model_name='quote',
            name='initiative_deposits',
            field=models.JSONField(blank=True, default=list, editable=False, verbose_name='Deposit values'),
        ),
    ]
