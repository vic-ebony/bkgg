# Generated by Django 5.1.7 on 2025-04-26 14:37

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('appointments', '0006_alter_appointment_beautician_and_more'),
        ('myapp', '0031_hall_address'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='appointment',
            name='hall',
            field=models.ForeignKey(default=1, help_text='選擇此預約/看台發生的館別。', on_delete=django.db.models.deletion.PROTECT, to='myapp.hall', verbose_name='館別'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='appointment',
            name='beautician',
            field=models.ForeignKey(blank=True, help_text='選擇提供服務的美容師。若是『現場看台』，此欄留空。', limit_choices_to={'is_active': True}, null=True, on_delete=django.db.models.deletion.PROTECT, to='myapp.animal', verbose_name='美容師 (可選)'),
        ),
        migrations.AddIndex(
            model_name='appointment',
            index=models.Index(fields=['hall', 'appointment_datetime'], name='appointment_hall_id_0a40ff_idx'),
        ),
    ]
