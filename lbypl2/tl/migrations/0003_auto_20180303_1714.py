# Generated by Django 2.0.2 on 2018-03-03 17:14

import datetime
from django.db import migrations, models
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('tl', '0002_providers_last_update'),
    ]

    operations = [
        migrations.AlterField(
            model_name='providers',
            name='last_update',
            field=models.DateTimeField(default=datetime.datetime(2018, 3, 3, 17, 14, 0, 510569, tzinfo=utc)),
        ),
    ]
