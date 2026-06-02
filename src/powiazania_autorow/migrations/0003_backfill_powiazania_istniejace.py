from django.db import migrations


def backfill_powiazania(apps, schema_editor):
    """Jednorazowy backfill powiązań dla istniejących instalacji.

    Na nie-pustej bazie (są już autorzy) liczymy powiązania od razu, żeby graf
    na stronie autora działał natychmiast po wdrożeniu — bez czekania na nocny
    przelicznik (celerybeat 4:00). Na świeżej/pustej bazie oraz w testach jest
    to no-op (nie ma czego liczyć, a baseline test-DB i tak migruje na pusto).
    """
    from django.conf import settings

    if getattr(settings, "TESTING", False):
        return

    Autor = apps.get_model("bpp", "Autor")
    if not Autor.objects.exists():
        # Pusta/świeża baza — brak danych do policzenia.
        return

    # Backfill jednorazowy: wołamy realną funkcję przelicznika. Operuje na
    # bieżących modelach, co jest bezpieczne — ta migracja jest ostatnia w
    # łańcuchu (zależy od najnowszej migracji bpp), więc wszystkie tabele
    # publikacji już istnieją.
    from powiazania_autorow.core import calculate_author_connections

    calculate_author_connections()


class Migration(migrations.Migration):

    dependencies = [
        ("powiazania_autorow", "0002_alter_authorconnection_primary_author_and_more"),
        ("bpp", "0419_merge_20260601_1319"),
    ]

    operations = [
        migrations.RunPython(backfill_powiazania, migrations.RunPython.noop),
    ]
