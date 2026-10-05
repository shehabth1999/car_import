# Lead assignment groups — the client's Odoo `crm.assignment.group`, field for
# field (name, tags, salespeople, daily limit, the round-robin pointer) — and
# the log the job counts a salesperson's day from. Two new tables and their
# many-to-many tables; nothing existing changes.

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

TAGS_HELP = ('A lead that carries any of these tags belongs to this group. Leave empty to make this a catch-all '
             'group: it is tried last and takes the leads no tagged group matched.')
LIMIT_HELP = 'The most leads one salesperson receives from this group in a day. 0 means no limit.'


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


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0025_backfill_partner_last_seen'),
        ('car_import', '0028_contract_related_names'),
        ('crm', '0016_lead_lead_origin'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LeadAssignmentGroup',
            fields=_audit() + [
                ('name', models.CharField(max_length=128, verbose_name='Name')),
                ('daily_limit', models.PositiveIntegerField(default=100, help_text=LIMIT_HELP, verbose_name='Daily limit')),
                ('last_assigned_index', models.PositiveIntegerField(blank=True, editable=False, null=True, verbose_name='Last turn')),
            ] + _people() + [
                ('salespeople', models.ManyToManyField(blank=True, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='Salespeople')),
                ('tags', models.ManyToManyField(blank=True, help_text=TAGS_HELP, related_name='+', to='crm.tag', verbose_name='Lead tags')),
            ],
            options={
                'verbose_name': 'Lead assignment group',
                'verbose_name_plural': 'Lead assignment groups',
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='LeadAssignmentLog',
            fields=_audit() + [
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assignments', to='car_import.leadassignmentgroup', verbose_name='Group')),
                ('lead', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='crm.lead', verbose_name='Lead')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='Salesperson')),
            ] + _people(),
            options={
                'verbose_name': 'Lead assignment log',
                'verbose_name_plural': 'Lead assignment log',
                'ordering': ['-id'],
                'indexes': [models.Index(fields=['group', 'user', 'created_at'], name='ka_lead_assign_day_idx')],
            },
        ),
    ]
