# Generated by Django 5.1.7 on 2025-03-30 08:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0008_review_cup_size_review_music_price_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='review',
            name='music_price',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True, verbose_name='音樂價格'),
        ),
        migrations.AlterField(
            model_name='review',
            name='sports_price',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True, verbose_name='體育價格'),
        ),
    ]
