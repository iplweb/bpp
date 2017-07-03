# -*- coding: utf-8 -*-


from django.db import migrations, models
import egeria.models.core


class Migration(migrations.Migration):

    dependencies = [
        ('egeria', '0009_egeriaimport_uczelnia'),
    ]

    operations = [
        migrations.AlterField(
            model_name='egeriaimport',
            name='od',
            field=models.DateField(default=egeria.models.core.get_today_date),
        ),
    ]
