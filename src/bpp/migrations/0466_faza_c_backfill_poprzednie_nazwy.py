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
MAX_LEN = 4096


def nowa_poprzednie_nazwy(poprzednie, nazwa_wydzialu, nazwa_roota):
    """Czysta logika: zwraca nową wartość ``poprzednie_nazwy`` po dołożeniu
    ``nazwa_wydzialu``, albo ``None`` gdy nic nie trzeba zmieniać.

    Pomija (zwraca None) gdy: nazwa wydziału pusta; równa nazwie roota (root
    to węzeł-lustro — match po ``nazwa__iexact``); już wpisana (idempotencja);
    dołożenie przepełniłoby ``CharField(4096)``. Wydzielona z ``apps.get_model``,
    by dało się ją przetestować także po usunięciu modelu ``Wydzial`` (0467).
    """
    nazwa_wydzialu = (nazwa_wydzialu or "").strip()
    if not nazwa_wydzialu:
        return None
    if nazwa_wydzialu.casefold() == (nazwa_roota or "").strip().casefold():
        return None
    istniejace = [n.strip() for n in (poprzednie or "").split(SEP) if n.strip()]
    if any(n.casefold() == nazwa_wydzialu.casefold() for n in istniejace):
        return None  # już wpisane — idempotencja
    istniejace.append(nazwa_wydzialu)
    nowa = SEP.join(istniejace)
    if len(nowa) > MAX_LEN:
        return None  # nie przepełniaj kolumny — skrajnie nieprawdopodobne
    return nowa


def backfill_poprzednie_nazwy(apps, schema_editor):
    Jednostka = apps.get_model("bpp", "Jednostka")
    Wydzial = apps.get_model("bpp", "Wydzial")

    roots = Jednostka.objects.filter(legacy_wydzial_id__isnull=False)
    for root in roots.iterator():
        wydzial = Wydzial.objects.filter(pk=root.legacy_wydzial_id).first()
        if wydzial is None:
            continue
        nowa = nowa_poprzednie_nazwy(root.poprzednie_nazwy, wydzial.nazwa, root.nazwa)
        if nowa is None:
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
