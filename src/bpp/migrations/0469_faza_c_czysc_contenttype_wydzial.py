# Faza C (#438): ``DeleteModel("Wydzial")`` (0467) usunął tabelę, ale osierocił
# wiersz ``ContentType(app_label="bpp", model="wydzial")`` oraz jego 4
# auto-generowane uprawnienia (``add/change/delete/view_wydzial``). Django NIE
# kasuje stale content-type'ów w migracjach (robi to tylko interaktywna komenda
# ``remove_stale_contenttypes``), więc na realnym upgrade DB, która MIAŁA ten
# CT, wiersze zostałyby na zawsze. Ta migracja sprząta je deterministycznie.
#
# Na świeżej bazie CT nigdy nie powstaje (post_migrate tworzy CT tylko dla
# istniejących modeli, a Wydzial już nie istnieje) — wtedy to no-op.
from django.db import migrations


def czysc_contenttype_wydzial(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")

    cts = ContentType.objects.filter(app_label="bpp", model="wydzial")
    # Uprawnienia FK-ują do ContentType (CASCADE), ale kasujemy je jawnie —
    # czytelniej i niezależnie od kolejności/konfiguracji cascade w stanie
    # historycznym migracji.
    Permission.objects.filter(content_type__in=cts).delete()
    cts.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0468_faza_c_drop_legacy_markery"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(czysc_contenttype_wydzial, migrations.RunPython.noop),
    ]
