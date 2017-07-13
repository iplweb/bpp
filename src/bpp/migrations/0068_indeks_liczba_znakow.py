# -*- coding: utf-8 -*-


from django.db import migrations, models
from django.db.migrations.operations.special import RunSQL


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0067_typ_kbn_artykul_pbn'),
    ]

    operations = [
        RunSQL("CREATE INDEX bpp_rekord_mat_liczba_znakow_wydawniczych ON bpp_rekord_mat(liczba_znakow_wydawniczych)",
                "DROP INDEX IF EXISTS bpp_rekord_mat_liczba_znakow_wydawniczych")
    ]
