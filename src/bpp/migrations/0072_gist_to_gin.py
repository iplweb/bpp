# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bpp', '0071_fix_liczba_znakow_wyd'),
    ]

    operations = [
        migrations.RunSQL("drop index bpp_rekord_mat_search_index_idx"),
        migrations.RunSQL("CREATE INDEX bpp_rekord_mat_search_index_idx ON bpp_rekord_mat USING GIN(search_index)")
    ]
