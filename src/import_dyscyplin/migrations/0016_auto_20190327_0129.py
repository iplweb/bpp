# Generated by Django 2.1.7 on 2019-03-27 00:29

import django.contrib.postgres.fields.jsonb
import django.core.serializers.json
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('import_dyscyplin', '0015_auto_20190326_0553'),
    ]

    operations = [
        migrations.AlterField(
            model_name='import_dyscyplin_row',
            name='original',
            field=django.contrib.postgres.fields.jsonb.JSONField(encoder=django.core.serializers.json.DjangoJSONEncoder),
        ),
    ]