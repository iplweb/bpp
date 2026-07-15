"""Faza B / issue #438 — IV-2 (OSTATNIE zadanie Fazy B): migracja WARTOŚCI
zapisanych wyszukiwań multiseek (``multiseek_searchform.data``, JSON).

Po konsolidacji Wydział→Jednostka zapisane searche trzymają w ``data`` wartości,
które wskazują w próżnię:

* pola ``"Wydział"`` / ``"Pierwszy wydział"`` (autocomplete) — ``value`` to
  **goły pk (string)** starego ``Wydzial`` (np. ``"132434"``). UWAGA: mimo że
  ``value_to_web`` zwraca ``[pk, label]`` (server→JS, do odtworzenia widżetu),
  PERSYSTOWANA wartość to sam pk — potwierdzone empirycznie zrzutem ``.data`` z
  realnego ``multiseek:save_form`` oraz przez ``value_from_web`` (``int(value)``,
  ``unit_fields.py``), które na liście ``[pk, label]`` rzuciłoby wyjątek.
* pole ``"Rodzaj jednostki"`` (value-list) — ``value`` to **goły label
  (string)** ze starego ``RODZAJ_JEDNOSTKI.labels``.

Struktura ``data`` (potwierdzona empirycznie):
``{"form_data": [<prev_op|null>, <węzeł>, <węzeł>, ...], ...}`` gdzie węzeł to
albo dict pola ``{"field","operator","value","prev_op"}``, albo **grupa** = lista
``[<prev_op str>, <węzeł>, <węzeł>, ...]`` (element 0 = ``prev_op`` grupy).
Zagnieżdżenie AND/OR jest dowolnie głębokie → walker jest rekurencyjny.

Remap (tylko ``value`` — NIE ruszamy nazw pól ani operatorów):

A. ``"Wydział"`` / ``"Pierwszy wydział"``:
   ``mapa = {legacy_wydzial_id: jednostka.id}`` (węzły-wydziały po konsolidacji).
   Mapa obejmuje OBA rodzaje węzłów niosących ``legacy_wydzial_id``: syntetyczne
   lustra (``rodzaj="Wydział"``) ORAZ promowane realne jednostki (I-4/0457 krok
   6 — 1-elementowy wydział, którego jedyna jednostka stała się rootem i dostała
   ``legacy_wydzial_id`` zastąpionego wydziału). Dzięki temu zapisany search po
   promowanym wydziale remapuje się na promowaną jednostkę zamiast zostać
   zdropowany.
   - ``int(value) in mapa`` → ``value = str(mapa[pk])`` (nowy pk węzła; BEZ labela —
     JS sam odtworzy label przez ``value_to_web`` przy wczytaniu).
   - ``int(value)`` już wskazuje węzeł docelowy (``in target_pks``) i NIE jest
     starym pk w ``wydzial_mapa`` → SKIP (re-run idempotentny).
   - w p.p. → **DROP tego wpisu + log** (id searcha, stary pk). Reszta searcha
     nietknięta. Po dropie wpis znika, więc kolejny run już go nie widzi
     (drop też idempotentny).
   Kolejność guardów (kolizja pk): pk-e węzłów (``Jednostka``) i starych
   ``Wydzial`` pochodzą z NIEZALEŻNYCH sekwencji, więc liczbowo się PRZECINAJĄ —
   inwariant rozłączności jest fałszywy (choćby przez promocje z 0457, gdzie
   promowana jednostka-root trafia do ``target_pks`` z arbitralnym pk). Dlatego
   ``wydzial_mapa`` (kluczowana starym pk Wydzialu = to, czym ``value`` JEST na
   pierwszym przebiegu) sprawdzamy PRZED ``target_pks``: inaczej stary pk
   kolidujący z pk promowanej jednostki zostałby błędnie zeskipowany i wskazywał
   cudzy wydział. Idempotencja re-runu jest wtedy słabsza, ale forward leci raz
   (reverse = noop), więc poprawność pierwszego przebiegu ma priorytet.
   Rezydualny (zaakceptowany) przypadek: NIEMAPOWALNY stary pk (brak węzła), który
   liczbowo koliduje z pk w ``target_pks``, trafia w SKIP zamiast w DROP+log —
   zostaje cicho przy starej wartości. Wymaga podwójnej koincydencji (usunięty
   wydział + kolizja pk) i dotyczy tylko forward-once; alternatywą byłoby całkiem
   usunąć guard ``target_pks`` (wtedy taka kolizja → DROP+log), ale kosztem
   idempotencji re-runu — świadomie zostawiamy guard.

B. ``"Rodzaj jednostki"``: stary label → nowa nazwa ``RodzajJednostki``:
   - ``"zwyczajna jednostka (katedra, zakład, pracownia, itp.)"`` → ``"Standard"``
   - ``"koło naukowe"`` → ``"Koło naukowe"``
   Wartość będąca aktualną nazwą słownika ``RodzajJednostki`` (w tym już
   zmapowane ``"Standard"``/``"Koło naukowe"`` oraz tenant-specyficzne rodzaje) →
   SKIP (nie gubimy poprawnych filtrów; naturalna idempotencja). Wartość pusta →
   SKIP. Pozostałe (niepusty, nierozpoznany label) → **DROP + log**.

Reverse = noop — nie odwracamy przemapowania user-danych.
"""

import json
import logging

from django.db import migrations

logger = logging.getLogger(__name__)

WYDZIAL_FIELD_LABELS = frozenset({"Wydział", "Pierwszy wydział"})
RODZAJ_FIELD_LABEL = "Rodzaj jednostki"

# Stare labele CharField ``RODZAJ_JEDNOSTKI`` (git 29f111758~1, przed III-1) →
# nazwy słownika ``RodzajJednostki`` (seed Fazy A).
RODZAJ_VALUE_MAPA = {
    "zwyczajna jednostka (katedra, zakład, pracownia, itp.)": "Standard",
    "koło naukowe": "Koło naukowe",
}


def _remap_wydzial_entry(entry, wydzial_mapa, target_pks, search_id):
    """(entry|None, changed). None → drop wpisu."""
    value = entry.get("value")
    try:
        pk = int(value)
    except (TypeError, ValueError):
        # ``value`` nie jest int-owalnym pk (puste pole / już uszkodzone) —
        # zostaw; to nie nasz przypadek (jak guard w ``value_from_web``).
        return entry, False

    if pk in wydzial_mapa:
        # Na pierwszym przebiegu ``value`` jest DEFINICYJNIE starym pk Wydzialu,
        # a ``wydzial_mapa`` jest kluczowana właśnie ``legacy_wydzial_id`` — więc
        # to autorytatywny test remapu. MUSI być sprawdzany PRZED ``target_pks``:
        # pk-e ``Wydzial`` i ``Jednostka`` pochodzą z niezależnych sekwencji, więc
        # stary pk Wydzialu potrafi liczbowo kolidować z pk promowanej
        # jednostki-roota (I-4/0457) siedzącej w ``target_pks``. Gdyby guard
        # idempotencji szedł pierwszy, taka kolizja zacieniłaby remap i wpis
        # zostałby przy starej wartości → wskazywałby cudzy wydział.
        new_value = str(wydzial_mapa[pk])
        if entry.get("value") == new_value:
            return entry, False
        new_entry = dict(entry)
        new_entry["value"] = new_value
        return new_entry, True

    if pk in target_pks:
        # Już wskazuje węzeł docelowy (a NIE jest starym pk w mapie) — re-run,
        # nic nie rób (idempotencja). Uwaga: forward leci raz, reverse to noop,
        # więc ten przypadek to praktycznie tylko ręczne ponowienie migracji.
        return entry, False

    # Stary pk bez odpowiednika po konsolidacji — niemapowalny.
    logger.warning(
        "multiseek 0463: SearchForm id=%s — pole %r ma niemapowalny pk "
        "wydziału %r; usuwam ten wpis.",
        search_id,
        entry.get("field"),
        value,
    )
    return None, True


def _remap_rodzaj_entry(entry, valid_rodzaj, search_id):
    """(entry|None, changed). None → drop wpisu."""
    value = entry.get("value")
    if value in RODZAJ_VALUE_MAPA:
        new_entry = dict(entry)
        new_entry["value"] = RODZAJ_VALUE_MAPA[value]
        return new_entry, True

    if not value or value in valid_rodzaj:
        # Puste pole albo aktualna nazwa słownika (w tym już zmapowane
        # "Standard"/"Koło naukowe" oraz tenant-custom) — zostaw.
        return entry, False

    logger.warning(
        "multiseek 0463: SearchForm id=%s — nieznana wartość "
        "'Rodzaj jednostki' %r; usuwam ten wpis.",
        search_id,
        value,
    )
    return None, True


def _remap_nodes(nodes, wydzial_mapa, target_pks, valid_rodzaj, search_id):
    """Rekurencyjny walker po liście węzłów. Zwraca (nowe_węzły, changed)."""
    result = []
    changed = False
    for node in nodes:
        if isinstance(node, list):
            if not node:
                # Zdegenerowany pusty węzeł-grupa (ręcznie zepsute dane) —
                # zostaw bez zmian; bez tego ``node[0]`` niżej rzuca IndexError
                # i wywala CAŁĄ migrację (odwrotnie niż inne guardy w tym pliku).
                result.append(node)
                continue
            # Grupa: [prev_op, węzeł, węzeł, ...] — zachowaj prev_op (node[0]).
            inner, inner_changed = _remap_nodes(
                node[1:], wydzial_mapa, target_pks, valid_rodzaj, search_id
            )
            changed = changed or inner_changed
            result.append([node[0], *inner])
        elif isinstance(node, dict):
            field = node.get("field")
            if field in WYDZIAL_FIELD_LABELS:
                kept, node_changed = _remap_wydzial_entry(
                    node, wydzial_mapa, target_pks, search_id
                )
            elif field == RODZAJ_FIELD_LABEL:
                kept, node_changed = _remap_rodzaj_entry(node, valid_rodzaj, search_id)
            else:
                kept, node_changed = node, False
            changed = changed or node_changed
            if kept is not None:
                result.append(kept)
        else:
            # Nieznany kształt węzła — nie ruszamy.
            result.append(node)
    return result, changed


def _remap_form_data(form_data, wydzial_mapa, target_pks, valid_rodzaj, search_id):
    """form_data = [prev_op, węzeł, ...]. Zwraca (nowe_form_data, changed)."""
    if not isinstance(form_data, list) or not form_data:
        return form_data, False
    new_nodes, changed = _remap_nodes(
        form_data[1:], wydzial_mapa, target_pks, valid_rodzaj, search_id
    )
    return [form_data[0], *new_nodes], changed


def remap_saved_searches(apps, schema_editor):
    SearchForm = apps.get_model("multiseek", "SearchForm")
    Jednostka = apps.get_model("bpp", "Jednostka")
    RodzajJednostki = apps.get_model("bpp", "RodzajJednostki")

    wydzial_mapa = dict(
        Jednostka.objects.filter(legacy_wydzial_id__isnull=False).values_list(
            "legacy_wydzial_id", "id"
        )
    )
    target_pks = set(wydzial_mapa.values())
    valid_rodzaj = set(RodzajJednostki.objects.values_list("nazwa", flat=True))

    for search in SearchForm.objects.all().iterator():
        try:
            data = json.loads(search.data)
        except (ValueError, TypeError):
            logger.warning(
                "multiseek 0463: SearchForm id=%s — data nie jest poprawnym "
                "JSON-em; pomijam.",
                search.pk,
            )
            continue

        form_data = data.get("form_data") if isinstance(data, dict) else None
        if not isinstance(form_data, list) or not form_data:
            continue

        new_form_data, changed = _remap_form_data(
            form_data, wydzial_mapa, target_pks, valid_rodzaj, search.pk
        )
        if changed:
            data["form_data"] = new_form_data
            search.data = json.dumps(data, ensure_ascii=False)
            search.save(update_fields=["data"])


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0462_faza_b_iv1_przelicz_aktualna"),
        ("multiseek", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(remap_saved_searches, migrations.RunPython.noop),
    ]
