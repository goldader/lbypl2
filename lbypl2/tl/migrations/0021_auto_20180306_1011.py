# Generated by Django 2.0.2 on 2018-03-06 10:11

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tl', '0020_auto_20180306_0952'),
    ]

    operations = [
        migrations.RenameField(
            model_name='token',
            old_name='user',
            new_name='User',
        ),
        migrations.AlterField(
            model_name='providers',
            name='last_update',
            field=models.DateTimeField(default=datetime.datetime(2018, 3, 6, 10, 11, 11, 61375)),
        ),
    ]
