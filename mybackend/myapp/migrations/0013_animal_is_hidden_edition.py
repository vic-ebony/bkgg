# Generated by Django 5.1.7 on 2025-04-12 19:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0012_announcement_alter_animal_options_alter_hall_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='animal',
            name='is_hidden_edition',
            field=models.BooleanField(default=False, verbose_name='隱藏版'),
        ),
    ]
