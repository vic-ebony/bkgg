# Generated by Django 5.1.7 on 2025-04-17 17:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0023_alter_hall_options_alter_note_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='hall',
            name='schedule_format_type',
            field=models.CharField(choices=[('format_a', '格式A (舊LINE格式)'), ('chatanghui', '茶湯會格式'), ('xinyuan', '芯苑館格式')], default='format_a', help_text='指定此館別使用的班表文字格式，以便系統選擇正確的解析器', max_length=20, verbose_name='班表格式類型'),
        ),
    ]
