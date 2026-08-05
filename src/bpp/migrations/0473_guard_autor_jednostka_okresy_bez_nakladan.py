"""Guard: nakladajace sie okresy zatrudnienia autor-jednostka (krok 1 z 2).

``0474`` zaklada ``ExclusionConstraint`` zabraniajacy NAKLADAJACYCH sie okresow
zatrudnienia tego samego autora w tej samej jednostce (dla wierszy z NIE-NULL
``rozpoczal_prace``). Zanim ``ALTER TABLE ... ADD CONSTRAINT`` sie wykona, baza
NIE moze zawierac takich nakladan — inaczej DDL wywalilby sie surowym
komunikatem PostgreSQL bez wskazania, KTORE wiersze koliduja.

Ta migracja jest GUARDEM, nie deduplikatorem. W odroznieniu od pary
``0471``/``0472`` (gdzie duplikaty bez daty byly jednoznacznie identyczne i dalo
sie je bezpiecznie scalic po najnizszym pk), nakladajace sie DATOWANE okresy
niosa realna informacje (rozne funkcje/stanowiska/wymiary etatu na czesciowo
pokrywajacych sie przedzialach). Automatyczne scalenie mogloby po cichu zgubic
dane historyczne, wiec zamiast zgadywac — ODMAWIAMY migracji i wypisujemy
czytelna liste kolizji do recznego rozstrzygniecia przez operatora.

Na dzisiejszych danych produkcyjnych nakladan NIE ma — migracja jest no-opem.
Guard chroni instalacje, ktore moglyby miec takie okresy (stare importy, reczne
edycje), przed nieczytelnym bledem DDL w ``0474``.

Semantyka nakladania jest DOKLADNIE taka jak w constraincie z ``0474``:
``daterange(rozpoczal_prace, zakonczyl_prace, '[]')`` (granice obustronnie
DOMKNIETE) + operator ``&&``. NULL-owy ``zakonczyl_prace`` daje zakres otwarty
w prawo ``[rozpoczal, )``. Rozdzielenie guardu (RunPython) i DDL (AddConstraint)
na osobne migracje jest zgodne z regula repo (dedup/guard i DDL osobno).
"""

from django.db import migrations

# Ta sama semantyka co ExclusionConstraint w 0474: przedzialy '[]' + '&&',
# tylko wiersze z NIE-NULL rozpoczal_prace (NULL-e pilnuje partial-unique
# z 0472, nie ten constraint).
SQL_KOLIZJE = """
    SELECT a.autor_id, a.jednostka_id,
           a.id, a.rozpoczal_prace, a.zakonczyl_prace,
           b.id, b.rozpoczal_prace, b.zakonczyl_prace
    FROM bpp_autor_jednostka a
    JOIN bpp_autor_jednostka b
      ON a.autor_id = b.autor_id
     AND a.jednostka_id = b.jednostka_id
     AND a.id < b.id
    WHERE a.rozpoczal_prace IS NOT NULL
      AND b.rozpoczal_prace IS NOT NULL
      AND daterange(a.rozpoczal_prace, a.zakonczyl_prace, '[]')
          && daterange(b.rozpoczal_prace, b.zakonczyl_prace, '[]')
    ORDER BY a.autor_id, a.jednostka_id, a.id, b.id
"""


def sprawdz_nakladania(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(SQL_KOLIZJE)
        kolizje = cursor.fetchall()

    if not kolizje:
        return

    Autor = apps.get_model("bpp", "Autor")
    Jednostka = apps.get_model("bpp", "Jednostka")

    def _nazwa(model, pk, cache):
        if pk not in cache:
            obj = model.objects.filter(pk=pk).first()
            cache[pk] = str(obj) if obj is not None else f"?({pk})"
        return cache[pk]

    autorzy, jednostki = {}, {}
    linie = []
    for (
        autor_id,
        jednostka_id,
        a_id,
        a_start,
        a_koniec,
        b_id,
        b_start,
        b_koniec,
    ) in kolizje:
        linie.append(
            f"  - autor={_nazwa(Autor, autor_id, autorzy)!r} "
            f"jednostka={_nazwa(Jednostka, jednostka_id, jednostki)!r}: "
            f"pk={a_id} [{a_start}..{a_koniec or ''}] "
            f"NAKLADA sie z pk={b_id} [{b_start}..{b_koniec or ''}]"
        )

    raise RuntimeError(
        "Nie moge zalozyc constraintu 'bpp_autor_jednostka_okresy_bez_nakladan' "
        f"(migracja 0474): w bazie sa {len(kolizje)} nakladajace sie okresy "
        "zatrudnienia tego samego autora w tej samej jednostce. Rozstrzygnij je "
        "recznie (skoryguj lub scal daty), a potem powtorz migracje. Kolizje:\n"
        + "\n".join(linie)
    )


def wstecz(apps, schema_editor):
    """Guard niczego nie zmienia w danych — cofniecie jest no-opem."""


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0472_constraint_autor_jednostka_bez_daty"),
    ]

    operations = [
        migrations.RunPython(sprawdz_nakladania, wstecz),
    ]
