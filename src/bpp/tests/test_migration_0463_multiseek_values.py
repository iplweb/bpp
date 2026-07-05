"""Testy migracji 0463 (Faza B / #438, IV-2): remap wartości zapisanych
wyszukiwań multiseek po konsolidacji Wydział→Jednostka.

Część testów działa na czystych funkcjach-helperach migracji (bez DB) —
weryfikują rekurencyjny walker, remap A/B, drop i idempotencję. Osobny test
integracyjny puszcza pełne ``remap_saved_searches`` na realnych modelach.
"""

import importlib
import json

import pytest
from django.apps import apps as global_apps
from model_bakery import baker

mod = importlib.import_module("bpp.migrations.0463_faza_b_iv2_multiseek_values")


def _remap(form_data, wydzial_mapa, valid_rodzaj=frozenset(), search_id=1):
    target_pks = set(wydzial_mapa.values())
    return mod._remap_form_data(
        form_data, wydzial_mapa, target_pks, valid_rodzaj, search_id
    )


def _entry(field, value, prev_op=None, operator="equals"):
    return {"field": field, "operator": operator, "value": value, "prev_op": prev_op}


# --- A: Wydział / Pierwszy wydział -----------------------------------------


def test_wydzial_pk_remapped_value_is_new_node_pk_as_string():
    form_data = [None, _entry("Wydział", "500")]
    new_fd, changed = _remap(form_data, {500: 9001})
    assert changed is True
    assert new_fd == [None, _entry("Wydział", "9001")]


def test_wydzial_pk_remapped_from_int_value_written_back_as_string():
    # Niektóre wiersze mogą mieć value jako int, nie string — int() to łyka,
    # a zapisujemy zawsze jako str (dominujący format).
    form_data = [None, _entry("Wydział", 500)]
    new_fd, changed = _remap(form_data, {500: 9001})
    assert changed is True
    assert new_fd[1]["value"] == "9001"


def test_pusty_wezel_grupy_nie_wywala_migracji():
    """Regresja (#438): zdegenerowany pusty węzeł-grupa ``[]`` w form_data NIE
    może wywalić migracji IndexError-em (był bug ``node[0]`` na pustej liście).
    Reszta form_data ma się nadal przemapować."""
    form_data = [None, [], _entry("Wydział", "500")]
    new_fd, changed = _remap(form_data, {500: 9001})
    assert changed is True
    assert [] in new_fd  # pusty węzeł zachowany bez zmian
    assert _entry("Wydział", "9001") in new_fd


def test_pierwszy_wydzial_pk_remapped():
    form_data = [None, _entry("Pierwszy wydział", "77")]
    new_fd, changed = _remap(form_data, {77: 8002})
    assert changed is True
    assert new_fd == [None, _entry("Pierwszy wydział", "8002")]


# --- B: Rodzaj jednostki ----------------------------------------------------


def test_rodzaj_old_normalna_label_maps_to_standard():
    form_data = [
        None,
        _entry(
            "Rodzaj jednostki", "zwyczajna jednostka (katedra, zakład, pracownia, itp.)"
        ),
    ]
    new_fd, changed = _remap(form_data, {})
    assert changed is True
    assert new_fd[1]["value"] == "Standard"


def test_rodzaj_old_kolo_label_maps_to_kolo_naukowe():
    form_data = [None, _entry("Rodzaj jednostki", "koło naukowe")]
    new_fd, changed = _remap(form_data, {})
    assert changed is True
    assert new_fd[1]["value"] == "Koło naukowe"


def test_rodzaj_current_dictionary_value_untouched():
    # Wartość będąca aktualną nazwą słownika (np. tenant-custom) — zostaje.
    form_data = [None, _entry("Rodzaj jednostki", "Instytut")]
    new_fd, changed = _remap(form_data, {}, valid_rodzaj={"Instytut"})
    assert changed is False
    assert new_fd == form_data


def test_rodzaj_unknown_value_dropped():
    form_data = [
        None,
        _entry("Rodzaj jednostki", "całkiem-nieznany-rodzaj"),
        _entry("Tytuł oryginalny", "x", prev_op="and"),
    ]
    new_fd, changed = _remap(form_data, {})
    assert changed is True
    assert new_fd == [None, _entry("Tytuł oryginalny", "x", prev_op="and")]


# --- Drop niemapowalnego wydziału ------------------------------------------


def test_unmappable_wydzial_pk_dropped_rest_untouched():
    form_data = [
        None,
        _entry("Wydział", "999"),  # brak w mapie → drop
        _entry("Tytuł oryginalny", "abc", prev_op="and"),
    ]
    new_fd, changed = _remap(form_data, {500: 9001})
    assert changed is True
    # wpis wydziału usunięty, reszta nietknięta
    assert new_fd == [None, _entry("Tytuł oryginalny", "abc", prev_op="and")]


# --- Idempotencja -----------------------------------------------------------


def test_idempotent_second_run_no_change():
    form_data = [None, _entry("Wydział", "500")]
    mapa = {500: 9001}
    new_fd, changed1 = _remap(form_data, mapa)
    assert changed1 is True
    # drugi przebieg na już-przemapowanych danych
    new_fd2, changed2 = _remap(new_fd, mapa)
    assert changed2 is False
    assert new_fd2 == new_fd


def test_idempotent_rodzaj_second_run_no_change():
    form_data = [None, _entry("Rodzaj jednostki", "koło naukowe")]
    valid = {"Standard", "Koło naukowe"}
    new_fd, changed1 = _remap(form_data, {}, valid_rodzaj=valid)
    assert changed1 is True
    new_fd2, changed2 = _remap(new_fd, {}, valid_rodzaj=valid)
    assert changed2 is False
    assert new_fd2[1]["value"] == "Koło naukowe"


# --- Zagnieżdżenie AND/OR ---------------------------------------------------


def test_nested_group_wydzial_remapped_structure_preserved():
    form_data = [
        None,
        [
            "or",
            _entry("Wydział", "500"),
            _entry("Pierwszy wydział", "77", prev_op="and"),
        ],
    ]
    new_fd, changed = _remap(form_data, {500: 9001, 77: 8002})
    assert changed is True
    assert new_fd == [
        None,
        [
            "or",
            _entry("Wydział", "9001"),
            _entry("Pierwszy wydział", "8002", prev_op="and"),
        ],
    ]


def test_deeply_nested_group_remapped():
    form_data = [
        None,
        _entry("Tytuł oryginalny", "x"),
        ["and", ["or", _entry("Wydział", "500", prev_op="and")]],
    ]
    new_fd, changed = _remap(form_data, {500: 9001})
    assert changed is True
    assert new_fd[2] == ["and", ["or", _entry("Wydział", "9001", prev_op="and")]]


def test_unmappable_wydzial_in_nested_group_dropped():
    form_data = [
        None,
        [
            "or",
            _entry("Wydział", "999"),
            _entry("Tytuł oryginalny", "y", prev_op="and"),
        ],
    ]
    new_fd, changed = _remap(form_data, {500: 9001})
    assert changed is True
    assert new_fd == [None, ["or", _entry("Tytuł oryginalny", "y", prev_op="and")]]


# --- Search bez pól wydziału/rodzaju ---------------------------------------


def test_search_without_relevant_fields_untouched():
    form_data = [
        None,
        _entry("Tytuł oryginalny", "abc"),
        ["and", _entry("Rok", "2020", prev_op="and")],
    ]
    new_fd, changed = _remap(form_data, {500: 9001}, valid_rodzaj={"Standard"})
    assert changed is False
    assert new_fd == form_data


# --- Integracja z DB --------------------------------------------------------


@pytest.mark.django_db
def test_remap_saved_searches_end_to_end():
    from multiseek.models import SearchForm

    from bpp.models import Jednostka, RodzajJednostki, Uczelnia

    uczelnia = baker.make(Uczelnia)
    node = baker.make(
        Jednostka, uczelnia=uczelnia, parent=None, wydzial=None, legacy_wydzial_id=4242
    )
    RodzajJednostki.objects.get_or_create(nazwa="Standard")
    owner = baker.make("bpp.BppUser")

    data = {
        "form_data": [
            None,
            {
                "field": "Wydział",
                "operator": "equals",
                "value": "4242",
                "prev_op": None,
            },
            {
                "field": "Rodzaj jednostki",
                "operator": "equals",
                "value": "koło naukowe",
                "prev_op": "and",
            },
            {
                "field": "Wydział",
                "operator": "equals",
                "value": "999999",  # niemapowalny → drop
                "prev_op": "and",
            },
        ]
    }
    sf = SearchForm.objects.create(
        name="test-0463", owner=owner, public=False, data=json.dumps(data)
    )

    mod.remap_saved_searches(global_apps, None)

    sf.refresh_from_db()
    out = json.loads(sf.data)["form_data"]
    # niemapowalny wydział usunięty → zostają 2 wpisy (+ leading prev_op)
    assert len(out) == 3
    assert out[1] == {
        "field": "Wydział",
        "operator": "equals",
        "value": str(node.pk),
        "prev_op": None,
    }
    assert out[2]["field"] == "Rodzaj jednostki"
    assert out[2]["value"] == "Koło naukowe"

    # Idempotencja: drugi przebieg nic nie zmienia.
    before = sf.data
    mod.remap_saved_searches(global_apps, None)
    sf.refresh_from_db()
    assert sf.data == before


@pytest.mark.django_db
def test_remap_saved_searches_ignores_broken_json():
    from multiseek.models import SearchForm

    owner = baker.make("bpp.BppUser")
    sf = SearchForm.objects.create(
        name="broken-0463", owner=owner, public=False, data="{not json"
    )
    # Nie może rzucić — tylko log + skip.
    mod.remap_saved_searches(global_apps, None)
    sf.refresh_from_db()
    assert sf.data == "{not json"
