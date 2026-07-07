"""Faza C / issue #438 — backfill ``poprzednie_nazwy`` (migracja 0466).

PRZED usunięciem modelu ``Wydzial`` (0467) i markera ``legacy_wydzial_id``
(0468) utrwalamy nazwę każdego wydziału w ``poprzednie_nazwy`` jego
węzła-korzenia. Dopóki oba żyją, mapujemy ``root.legacy_wydzial_id ->
Wydzial.nazwa`` i dokładamy tę nazwę do ``poprzednie_nazwy`` roota.

Po co: ``matchuj_wydzial`` (import, Faza C) szuka roota po ``nazwa`` LUB
``poprzednie_nazwy``. Węzeł-lustro nosi nazwę wydziału (match po nazwie), ale
root PROMOWANY z realnej jednostki nosi nazwę tej jednostki — bez backfillu
dawna nazwa wydziału przepadłaby wraz z modelem i import przestałby ją
odnajdywać.

Idempotentne: dokłada nazwę tylko gdy nie jest już nazwą roota ani jedną z
wpisanych ``poprzednie_nazwy`` (porównanie po liniach, case-insensitive).
Reversible = no-op (dane historyczne — nie odtwarzamy dawnego stanu pola).
"""

from django.db import migrations

SEP = "\n"


def backfill_poprzednie_nazwy(apps, schema_editor):
    Jednostka = apps.get_model("bpp", "Jednostka")
    Wydzial = apps.get_model("bpp", "Wydzial")

    roots = Jednostka.objects.filter(legacy_wydzial_id__isnull=False)
    for root in roots.iterator():
        wydzial = Wydzial.objects.filter(pk=root.legacy_wydzial_id).first()
        if wydzial is None:
            continue
        nazwa_wydzialu = (wydzial.nazwa or "").strip()
        if not nazwa_wydzialu:
            continue

        # root nosi już nazwę wydziału (węzeł-lustro) → match po nazwa__iexact,
        # nic nie dokładamy.
        if nazwa_wydzialu.casefold() == (root.nazwa or "").strip().casefold():
            continue

        istniejace = [
            n.strip() for n in (root.poprzednie_nazwy or "").split(SEP) if n.strip()
        ]
        if any(n.casefold() == nazwa_wydzialu.casefold() for n in istniejace):
            continue  # już wpisane — idempotencja

        istniejace.append(nazwa_wydzialu)
        nowa = SEP.join(istniejace)
        if len(nowa) > 4096:
            # nie przepełniaj CharField(4096) — skrajnie nieprawdopodobne
            continue

        root.poprzednie_nazwy = nowa
        root.save(update_fields=["poprzednie_nazwy"])


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0465_merge_20260707_0736"),
    ]

    operations = [
        migrations.RunPython(
            backfill_poprzednie_nazwy,
            migrations.RunPython.noop,
        ),
    ]
