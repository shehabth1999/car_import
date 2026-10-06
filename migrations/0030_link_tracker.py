# The lists of the client's Odoo "Link Tracker" menu that had no table here:
# model years, colours, trim levels, buyers, ports, destinations, shippers,
# clearance people, product types, the on-hold salespeople and the customer
# blacklist. Twelve new tables; nothing existing changes.

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

HOLD_HELP = ('While a salesperson is on this list, the automatic lead assignment gives them no new leads. '
             'The leads they already have stay with them.')
HIDDEN_HELP = 'Kept as it was in Odoo. It has no effect here.'


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


def _pick_list(name, verbose_name, verbose_name_plural, extra=()):
    """A list of names: the audit columns, `name`, and whatever else the list carries."""
    return migrations.CreateModel(
        name=name,
        fields=_audit() + [
            ('name', models.CharField(max_length=128, verbose_name='Name')),
        ] + list(extra) + _people(),
        options={
            'verbose_name': verbose_name,
            'verbose_name_plural': verbose_name_plural,
            'ordering': ['name'],
            'abstract': False,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('car_import', '0029_lead_assignment'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Cars
        _pick_list('CarModelYear', 'Car model year', 'Car model years'),
        _pick_list('CarColour', 'Car colour', 'Car colours'),
        _pick_list('CarTrimLevel', 'Car trim level', 'Car trim levels', extra=[
            ('options_features', models.TextField(blank=True, verbose_name='Options/Features')),
        ]),
        _pick_list('CarBuyer', 'Car buyer', 'Car buyers', extra=[
            ('company_name', models.CharField(blank=True, max_length=255, verbose_name='Company name')),
            ('address', models.CharField(blank=True, max_length=255, verbose_name='Address')),
        ]),
        # Delivery
        _pick_list('ArrivalPort', 'Arrival port', 'Arrival ports'),
        _pick_list('ShippingDestination', 'Shipping destination', 'Shipping destinations'),
        _pick_list('InternationalShipper', 'International shipper', 'International shippers'),
        _pick_list('LoadingPort', 'Loading port', 'Loading ports'),
        _pick_list('CustomsClearancePerson', 'Customs clearance person', 'Customs clearance people'),
        # Opportunities
        _pick_list('OpportunityProductType', 'Product type', 'Product types'),
        # Salespersons
        migrations.CreateModel(
            name='OnHoldSalesperson',
            fields=_audit() + [
                ('hidden', models.BooleanField(default=False, help_text=HIDDEN_HELP, verbose_name='Hidden')),
            ] + _people() + [
                ('user', models.OneToOneField(help_text=HOLD_HELP, on_delete=django.db.models.deletion.CASCADE, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='Salesperson')),
            ],
            options={
                'verbose_name': 'On-hold salesperson',
                'verbose_name_plural': 'On-hold salespeople',
                'ordering': ['id'],
            },
        ),
        # Blacklist
        _pick_list('BlacklistedCustomer', 'Blacklisted customer', 'Blacklisted customers', extra=[
            ('phone', models.CharField(blank=True, max_length=32, verbose_name='Phone')),
        ]),
    ]
