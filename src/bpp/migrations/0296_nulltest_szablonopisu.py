# Generated by Django 3.0.14 on 2021-09-26 05:54

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0295_instaluj_szablony"),
    ]

    operations = [
        migrations.RunSQL(
            "CREATE UNIQUE INDEX bpp_szablondlaopisubibliograficznego_nulltest ON "
            "bpp_szablondlaopisubibliograficznego((model_id IS NULL)) WHERE model_id IS NULL",
            "DROP INDEX IF EXISTS bpp_szablondlaopisubibliograficznego_nulltest",
        ),
        migrations.RunSQL(
            "CREATE UNIQUE INDEX dbtemplates_template_name ON django_template(name)",
            "DROP INDEX IF EXISTS dbtemplates_template_name",
        ),
    ]
