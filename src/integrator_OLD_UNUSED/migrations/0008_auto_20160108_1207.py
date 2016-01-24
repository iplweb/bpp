# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('integrator_OLD_UNUSED', '0007_auto_20160107_2232'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='autorintegrationrecord',
            name='matching_autor',
        ),
        migrations.RemoveField(
            model_name='autorintegrationrecord',
            name='matching_jednostka',
        ),
        migrations.RemoveField(
            model_name='autorintegrationrecord',
            name='parent',
        ),
        migrations.DeleteModel(
            name='AutorIntegrationRecord',
        ),
        migrations.RemoveField(
            model_name='integrationfile',
            name='owner',
        ),
        migrations.RemoveField(
            model_name='listaministerialnaintegrationrecord',
            name='matching_zrodlo',
        ),
        migrations.RemoveField(
            model_name='listaministerialnaintegrationrecord',
            name='parent',
        ),
        migrations.DeleteModel(
            name='ListaMinisterialnaIntegrationRecord',
        ),
        migrations.RemoveField(
            model_name='zrodlointegrationrecord',
            name='matching_zrodlo',
        ),
        migrations.RemoveField(
            model_name='zrodlointegrationrecord',
            name='parent',
        ),
        migrations.DeleteModel(
            name='IntegrationFile',
        ),
        migrations.DeleteModel(
            name='ZrodloIntegrationRecord',
        ),
    ]
