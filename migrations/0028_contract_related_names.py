# hr.Contract and car_import.Contract both carry the chatter mixin, whose reverse
# names are built from the class name alone. With hr installed the two collide
# and Django's system checks stop every migrate. Names only — no column changes.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('car_import', '0027_customs_values_2026_09_30'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contract',
            name='message_main_attachment_id',
            field=models.ForeignKey(blank=True, help_text='Main attachment for this record', null=True,
                                    on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='car_import_contract_main_attachment', to='base.attachment'),
        ),
        migrations.AlterField(
            model_name='contract',
            name='activity_user_id',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='car_import_contract_next_activities',
                                    to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='contract',
            name='activity_type_id',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='car_import_contract_next_activities',
                                    to='notifications.activitytype'),
        ),
        migrations.AlterField(
            model_name='contract',
            name='alias_id',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                       related_name='car_import_contract_alias', to='notifications.alias'),
        ),
    ]
