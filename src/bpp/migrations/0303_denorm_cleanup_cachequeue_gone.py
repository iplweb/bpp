# Generated by Django 3.0.14 on 2021-10-04 08:37

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0302_denorm_autor_dyscyplina_new_trigger"),
    ]

    operations = [
        migrations.DeleteModel(
            name="CacheQueue",
        ),
        migrations.RunSQL("DROP FUNCTION IF EXISTS bpp_wydawca_change CASCADE"),
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS bpp_alias_wydawcy_change_trigger CASCADE"
        ),
        migrations.RunSQL(
            "DROP FUNCTION IF EXISTS bpp_poziom_wydawcy_change_trigger CASCADE"
        ),
    ]
