"""Zgłoszenia publikacji w zbiorczym koszu: trigger ``bpp_kosz_straznik``.

``Zgloszenie_Publikacji`` miało od 2024 r. własny, starszy soft-delete
(pakiet ``django_softdelete`` z jego kaskadą). Teraz jest pełnoprawnym
członkiem kosza BPP (``BppSoftDeleteSlownikMixin``) — więc tak jak każda
inna tabela z koszem dostaje trigger zamrożenia z ``bpp/0523``: zmiana
``deleted_at`` tylko przez ``delete()``/``restore()``, ``UPDATE`` i fizyczny
``DELETE`` zgłoszenia w koszu są odrzucane (``BPP_KOSZ:``).

Danych nie migrujemy: kolumny ``deleted_at``/``restored_at``/
``transaction_id`` są te same (``0016``), więc zgłoszenia skasowane starym
mechanizmem od razu są w nowym koszu (``deleted_objects``). Ich autorzy
i załączniki zostały wtedy skasowane TWARDO przez kaskadę pakietu — tego
nie da się odtworzyć; przywrócone takie zgłoszenie wraca bez nich.

NIEODWRACALNA (brak ``reverse_sql``) — jak cały łańcuch soft-delete;
powrót wyłącznie z kopii bazy.
"""

from django.db import migrations

TABELA = "zglos_publikacje_zgloszenie_publikacji"


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0523_kosz_zamrozony_trigger"),
        ("zglos_publikacje", "0030_zgloszenie_autor_protect"),
    ]

    operations = [
        migrations.RunSQL(
            f"DROP TRIGGER IF EXISTS {TABELA}_kosz_straznik ON {TABELA}; "
            f"CREATE TRIGGER {TABELA}_kosz_straznik "
            f"BEFORE UPDATE OR DELETE ON {TABELA} "
            f"FOR EACH ROW EXECUTE FUNCTION bpp_kosz_straznik();"
        ),
    ]
