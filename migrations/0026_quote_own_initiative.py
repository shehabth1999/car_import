# The owner's second answer of 2026-09-30: a new current-year car may come on
# the customer's OWN initiative; a company-provided initiative adds the powers
# of attorney to the price. Both nullable — no existing quotation moves.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('car_import', '0025_quote_programme'),
    ]

    operations = [
        migrations.AddField(
            model_name='quote',
            name='own_initiative',
            field=models.BooleanField(blank=True, null=True, verbose_name='The customer holds the initiative'),
        ),
        migrations.AddField(
            model_name='quote',
            name='poa_usd',
            field=models.DecimalField(blank=True, decimal_places=2, editable=False, max_digits=12, null=True,
                                      verbose_name='Powers of attorney (USD)'),
        ),
    ]
