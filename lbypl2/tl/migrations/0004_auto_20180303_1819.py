# Generated by Django 2.0.2 on 2018-03-03 18:19

import datetime
from django.db import migrations, models
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('tl', '0003_auto_20180303_1714'),
    ]

    operations = [
        migrations.AlterField(
            model_name='providers',
            name='last_update',
            field=models.DateTimeField(default=datetime.datetime(2018, 3, 3, 18, 19, 45, 66685, tzinfo=utc)),
        ),
    ]
