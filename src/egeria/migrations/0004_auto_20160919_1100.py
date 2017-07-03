# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('egeria', '0003_auto_20160919_0936'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='diff_autor_create',
            name='commited',
        ),
        migrations.RemoveField(
            model_name='diff_autor_delete',
            name='commited',
        ),
        migrations.RemoveField(
            model_name='diff_autor_update',
            name='commited',
        ),
        migrations.RemoveField(
            model_name='diff_funkcja_autora_create',
            name='commited',
        ),
        migrations.RemoveField(
            model_name='diff_funkcja_autora_delete',
            name='commited',
        ),
        migrations.RemoveField(
            model_name='diff_jednostka_create',
            name='commited',
        ),
        migrations.RemoveField(
            model_name='diff_jednostka_delete',
            name='commited',
        ),
        migrations.RemoveField(
            model_name='diff_jednostka_update',
            name='commited',
        ),
        migrations.RemoveField(
            model_name='diff_tytul_create',
            name='commited',
        ),
        migrations.RemoveField(
            model_name='diff_tytul_delete',
            name='commited',
        ),
        migrations.RemoveField(
            model_name='diff_wydzial_create',
            name='commited',
        ),
        migrations.RemoveField(
            model_name='diff_wydzial_delete',
            name='commited',
        ),
    ]
