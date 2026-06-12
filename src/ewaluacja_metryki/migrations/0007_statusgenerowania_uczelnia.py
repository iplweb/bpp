import django.db.models.deletion
from django.db import migrations, models


def backfill_status_uczelnia(apps, schema_editor):
    Uczelnia = apps.get_model("bpp", "Uczelnia")
    StatusGenerowania = apps.get_model("ewaluacja_metryki", "StatusGenerowania")

    null_qs = StatusGenerowania.objects.filter(uczelnia__isnull=True)
    if not null_qs.exists():
        return

    uczelnie = list(Uczelnia.objects.all()[:2])
    if len(uczelnie) == 1:
        null_qs.update(uczelnia=uczelnie[0])
        return

    # Status to ulotny stan postępu, nie dane — przy >1 (lub 0) uczelni usuń
    # osierocony singleton (odtworzy się przy następnym generowaniu per uczelnia).
    null_qs.delete()


def backfill_status_uczelnia_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0428_cpd_uczelnia_not_null"),
        ("ewaluacja_metryki", "0006_metrykaautora_uczelnia"),
    ]

    operations = [
        migrations.AddField(
            model_name="statusgenerowania",
            name="uczelnia",
            field=models.OneToOneField(
                blank=True,
                help_text="Uczelnia, której dotyczy ten status (multi-hosted)",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="bpp.uczelnia",
            ),
        ),
        migrations.RunPython(
            backfill_status_uczelnia, backfill_status_uczelnia_reverse
        ),
    ]
