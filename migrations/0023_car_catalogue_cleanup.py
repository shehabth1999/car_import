# The free-text make/model columns go; the relations filled by 0022 take their
# place, with the same uniqueness rules keyed on the model instead of two strings.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('car_import', '0022_car_catalogue_data'),
    ]

    operations = [
        # ── the workbook's tables ───────────────────────────────────────────
        migrations.RemoveConstraint(model_name='deposittier', name='uniq_deposit_tier'),
        migrations.RemoveConstraint(model_name='customsvaluation', name='uniq_customs_value'),
        migrations.RemoveConstraint(model_name='modelpricerange', name='uniq_model_price_range'),
        migrations.RemoveField(model_name='deposittier', name='make'),
        migrations.RemoveField(model_name='deposittier', name='model'),
        migrations.RemoveField(model_name='customsvaluation', name='make'),
        migrations.RemoveField(model_name='customsvaluation', name='model'),
        migrations.RemoveField(model_name='modelpricerange', name='make'),
        migrations.RemoveField(model_name='modelpricerange', name='model'),
        migrations.AddConstraint(
            model_name='deposittier',
            constraint=models.UniqueConstraint(fields=('car_model', 'model_year', 'tier', 'region'), name='uniq_deposit_tier'),
        ),
        migrations.AddConstraint(
            model_name='customsvaluation',
            constraint=models.UniqueConstraint(fields=('car_model', 'model_year'), name='uniq_customs_value'),
        ),
        migrations.AddConstraint(
            model_name='modelpricerange',
            constraint=models.UniqueConstraint(fields=('car_model', 'model_year'), name='uniq_model_price_range'),
        ),
        migrations.AlterModelOptions(
            name='deposittier',
            options={'ordering': ['car_model__display_name', 'model_year', 'tier', 'region'],
                     'verbose_name': 'Deposit value', 'verbose_name_plural': 'Deposit values'},
        ),
        migrations.AlterModelOptions(
            name='customsvaluation',
            options={'ordering': ['car_model__display_name', 'model_year'],
                     'verbose_name': 'Customs value', 'verbose_name_plural': 'Customs values'},
        ),
        migrations.AlterModelOptions(
            name='modelpricerange',
            options={'ordering': ['car_model__display_name', 'model_year'],
                     'verbose_name': 'Model price range', 'verbose_name_plural': 'Model price ranges'},
        ),

        # ── the car and the adverts ─────────────────────────────────────────
        migrations.RemoveField(model_name='vehicle', name='make'),
        migrations.RemoveField(model_name='vehicle', name='model'),
        migrations.RemoveIndex(model_name='supplierlisting', name='car_import__make_da038c_idx'),
        migrations.RemoveField(model_name='supplierlisting', name='make'),
        migrations.RemoveField(model_name='supplierlisting', name='model'),
        migrations.AddIndex(
            model_name='supplierlisting',
            index=models.Index(fields=['brand', 'car_model', 'model_year'], name='car_import_listing_brand_idx'),
        ),

        # ── website cars and their lists ────────────────────────────────────
        migrations.RemoveField(model_name='websitecar', name='brand'),
        migrations.RemoveField(model_name='websitecar', name='model'),
        migrations.RenameField(model_name='websitecar', old_name='catalogue_brand', new_name='brand'),
        migrations.AlterField(
            model_name='websitecar', name='brand',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='website_cars', to='car_import.carbrand', verbose_name='Brand'),
        ),
        migrations.RemoveField(model_name='websitelookup', name='brand_website_id'),
        migrations.RemoveField(model_name='websitelookup', name='category_website_id'),
        migrations.AlterField(
            model_name='websitelookup', name='kind',
            field=models.CharField(choices=[('category', 'Category'), ('origin', 'Origin'), ('country', 'Car location'), ('fuel', 'Fuel'), ('bodytype', 'Body type'), ('gearbox', 'Gearbox'), ('engine', 'Engine'), ('extra_option', 'Extra option'), ('vehicle_option', 'Vehicle option')], db_index=True, max_length=16, verbose_name='List'),
        ),
    ]
