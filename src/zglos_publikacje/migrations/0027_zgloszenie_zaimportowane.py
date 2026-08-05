# Audyt domknięcia zgłoszenia przez importer prac (FD#443).
# Migracja napisana ręcznie — patrz docs/superpowers/specs/
# 2026-07-22-zgloszenie-zaimportowane-przez-importer-design.md §4.1
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zglos_publikacje", "0026_faza_b_ii2_repoint_wydzial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="zgloszenie_publikacji",
            name="zaimportowano",
            field=models.DateTimeField(
                blank=True, db_index=True, null=True, verbose_name="Zaimportowano"
            ),
        ),
        migrations.AddField(
            model_name="zgloszenie_publikacji",
            name="zaimportowal",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Zaimportował",
            ),
        ),
        migrations.AlterField(
            model_name="zgloszenie_publikacji",
            name="status",
            field=models.PositiveSmallIntegerField(
                choices=[
                    (0, "nowe zgłoszenie"),
                    (1, "zaakceptowany - dodany do bazy BPP"),
                    (2, "wymaga zmian - odesłano do zgłaszającego"),
                    (3, "zmiany naniesione przez zgłaszającego"),
                    (4, "odrzucono w całości"),
                    (5, "spam"),
                    (6, "zaimportowany przez importer prac"),
                ],
                default=0,
            ),
        ),
    ]
