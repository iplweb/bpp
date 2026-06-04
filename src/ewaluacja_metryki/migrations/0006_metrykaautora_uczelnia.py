import django.db.models.deletion
from django.db import migrations, models


def backfill_uczelnia(apps, schema_editor):
    Uczelnia = apps.get_model("bpp", "Uczelnia")
    MetrykaAutora = apps.get_model("ewaluacja_metryki", "MetrykaAutora")

    null_qs = MetrykaAutora.objects.filter(uczelnia__isnull=True)
    if not null_qs.exists():
        return

    uczelnie = list(Uczelnia.objects.all()[:2])
    if len(uczelnie) == 1:
        null_qs.update(uczelnia=uczelnie[0])
        return

    # MetrykaAutora to regenerowalny cache (delete+create przy generowaniu);
    # przy >1 uczelni nie da się zdeterministycznie przypisać legacy wierszy,
    # więc czyścimy — odtworzą się przy najbliższym generuj_metryki per uczelnia.
    null_qs.delete()


def backfill_uczelnia_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0428_cpd_uczelnia_not_null"),
        ("ewaluacja_metryki", "0005_alter_metrykaautora_rodzaj_autora_and_more"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="metrykaautora",
            unique_together=set(),
        ),
        migrations.AddField(
            model_name="metrykaautora",
            name="uczelnia",
            field=models.ForeignKey(
                blank=True,
                help_text="Uczelnia, dla której policzono metrykę (multi-hosted)",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="bpp.uczelnia",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="metrykaautora",
            unique_together={("autor", "dyscyplina_naukowa", "uczelnia")},
        ),
        migrations.AddIndex(
            model_name="metrykaautora",
            index=models.Index(
                fields=["uczelnia", "-srednia_za_slot_nazbierana"],
                name="ewaluacja_m_uczelni_1e8d4d_idx",
            ),
        ),
        migrations.RunPython(backfill_uczelnia, backfill_uczelnia_reverse),
    ]
