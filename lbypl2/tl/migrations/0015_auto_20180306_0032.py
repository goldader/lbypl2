# Generated by Django 2.0.2 on 2018-03-06 00:32

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tl', '0014_auto_20180306_0001'),
    ]

    operations = [
        migrations.RenameField(
            model_name='token',
            old_name='username',
            new_name='user_id',
        ),
        migrations.AlterField(
            model_name='providers',
            name='last_update',
            field=models.DateTimeField(default=datetime.datetime(2018, 3, 6, 0, 32, 15, 789092)),
        ),
    ]
