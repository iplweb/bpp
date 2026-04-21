from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0001_initial"),
        ("pbn_api", "0001_initial"),
        (
            "importer_publikacji",
            "0004_rename_user_to_created_by_add_modified_by",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="importsession",
            name="wydawnictwo_nadrzedne",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="bpp.wydawnictwo_zwarte",
                verbose_name="wydawnictwo nadrzędne",
            ),
        ),
        migrations.AddField(
            model_name="importsession",
            name="wydawnictwo_nadrzedne_w_pbn",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="pbn_api.publication",
                verbose_name="wydawnictwo nadrzędne w PBN",
            ),
        ),
    ]
