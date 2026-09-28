# The car catalogue (brands and models) and the relations that will replace the
# free-text make/model columns. 0022 fills them, 0023 drops the text.

import django.db.models.deletion
import django.utils.timezone
import modules.base.fields
from django.conf import settings
from django.db import migrations, models

ALIASES_HELP = 'Other spellings that mean this one, comma separated — e.g. Mercedes-Benz, مرسيدس بنز'


def _audit():
    return [
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Creation date')),
        ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Update date')),
        ('active', models.BooleanField(default=True, help_text='Whether this item is active and should be displayed', verbose_name='Active')),
        ('key', models.CharField(blank=True, help_text="Unique identifier for this record like 'contact_1'", max_length=255, null=True, unique=True)),
    ]


def _people():
    return [
        ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_created_by_related', to=settings.AUTH_USER_MODEL, verbose_name='Created By')),
        ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_modified_by_related', to=settings.AUTH_USER_MODEL, verbose_name='Modified By')),
    ]


def _model_fk(related_name, null=True, blank=True):
    return models.ForeignKey(blank=blank, null=null, on_delete=django.db.models.deletion.PROTECT,
                             related_name=related_name, to='car_import.carmodel', verbose_name='Model')


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0025_backfill_partner_last_seen'),
        ('car_import', '0020_website_integration'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CarBrand',
            fields=_audit() + [
                ('name', models.CharField(max_length=64, unique=True, verbose_name='Brand')),
                ('name_ar', models.CharField(blank=True, max_length=64, verbose_name='Name (Arabic)')),
                ('aliases', models.CharField(blank=True, help_text=ALIASES_HELP, max_length=255, verbose_name='Also matches')),
                ('website_id', models.PositiveIntegerField(blank=True, help_text='The brand\'s number on the company website. Empty when the website does not carry it', null=True, unique=True, verbose_name='Website id')),
                ('logo', modules.base.fields.AttachmentForeignKeyField(allowed_types=['image'], blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='base.attachment', upload_to='car_import/brands', verbose_name='Logo')),
                ('sequence', models.PositiveIntegerField(default=10, verbose_name='Order')),
            ] + _people(),
            options={
                'verbose_name': 'Car brand',
                'verbose_name_plural': 'Car brands',
                'ordering': ['sequence', 'name'],
            },
        ),
        migrations.CreateModel(
            name='CarModel',
            fields=_audit() + [
                ('name', models.CharField(max_length=128, verbose_name='Model')),
                ('name_ar', models.CharField(blank=True, max_length=128, verbose_name='Name (Arabic)')),
                ('aliases', models.CharField(blank=True, help_text=ALIASES_HELP, max_length=255, verbose_name='Also matches')),
                ('website_id', models.PositiveIntegerField(blank=True, help_text='The model\'s number on the company website. Empty when the website does not carry it', null=True, unique=True, verbose_name='Website id')),
                ('display_name', models.CharField(blank=True, db_index=True, editable=False, max_length=200, verbose_name='Brand and model')),
                ('brand', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='car_models', to='car_import.carbrand', verbose_name='Brand')),
            ] + _people(),
            options={
                'verbose_name': 'Car model',
                'verbose_name_plural': 'Car models',
                'ordering': ['brand__sequence', 'brand__name', 'name'],
                'constraints': [models.UniqueConstraint(fields=('brand', 'name'), name='uniq_car_model_per_brand')],
            },
        ),

        # ── the car ─────────────────────────────────────────────────────────
        migrations.AddField(
            model_name='vehicle', name='brand',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='vehicles', to='car_import.carbrand', verbose_name='Brand'),
        ),
        migrations.AddField(model_name='vehicle', name='car_model', field=_model_fk('vehicles')),
        migrations.AddField(
            model_name='vehicle', name='name',
            field=models.CharField(blank=True, db_index=True, editable=False, max_length=255, verbose_name='Car'),
        ),

        # ── supplier adverts ────────────────────────────────────────────────
        migrations.AddField(
            model_name='supplierlisting', name='brand',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='supplier_listings', to='car_import.carbrand', verbose_name='Brand'),
        ),
        migrations.AddField(model_name='supplierlisting', name='car_model', field=_model_fk('supplier_listings')),

        # ── the workbook's tables ───────────────────────────────────────────
        migrations.AddField(model_name='deposittier', name='car_model', field=_model_fk('deposit_values', blank=False)),
        migrations.AddField(model_name='customsvaluation', name='car_model', field=_model_fk('customs_values', blank=False)),
        migrations.AddField(model_name='modelpricerange', name='car_model', field=_model_fk('price_ranges', blank=False)),

        # ── website cars: the new brand arrives under a temporary name ──────
        migrations.AddField(
            model_name='websitecar', name='catalogue_brand',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='car_import.carbrand', verbose_name='Brand'),
        ),
        migrations.AddField(model_name='websitecar', name='car_model', field=_model_fk('website_cars')),

        # ── the qualification wizard ────────────────────────────────────────
        migrations.AddField(
            model_name='qualifycustomer', name='brand_wanted',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='car_import.carbrand', verbose_name='Brand wanted'),
        ),
        migrations.AddField(
            model_name='qualifycustomer', name='car_model_wanted',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='car_import.carmodel', verbose_name='Model wanted'),
        ),
        migrations.AlterField(
            model_name='qualifycustomer', name='model_wanted',
            field=models.CharField(blank=True, max_length=128, null=True, verbose_name="In the customer's words"),
        ),
    ]
