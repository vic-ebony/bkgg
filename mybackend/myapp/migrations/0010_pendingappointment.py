# Generated by Django 5.1.7 on 2025-03-31 14:48

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0009_alter_review_music_price_alter_review_sports_price'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PendingAppointment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('added_at', models.DateTimeField(auto_now_add=True)),
                ('animal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='myapp.animal')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pending_appointments', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
