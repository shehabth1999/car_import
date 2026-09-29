# The quotation's PDF, sent to the customer as a file (owner, 2026-09-29).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('car_import', '0023_car_catalogue_cleanup'),
    ]

    operations = [
        migrations.AddField(
            model_name='quote',
            name='document',
            field=models.FileField(blank=True, editable=False, upload_to='car_import/quotes/',
                                   verbose_name='Offer file'),
        ),
    ]
