import pytest
from model_bakery import baker

from import_sqlite.core.author_matching import aggregate_distinct, match_name
from import_sqlite.core.author_names import sort_key


@pytest.mark.django_db
def test_match_name_exact_prefill():
    a = baker.make("bpp.Autor", nazwisko="Wawruszak", imiona="Anna")
    da = match_name("Anna Wawruszak")
    assert da.status == "DOKLADNE"
    assert da.prefill_pk == a.pk
    assert da.candidates and da.candidates[0].pk == a.pk


@pytest.mark.django_db
def test_match_name_no_match_is_brak():
    da = match_name("Zdzisław Niedopasowany")
    assert da.status == "BRAK"
    assert da.candidates == []
    assert da.prefill_pk is None


@pytest.mark.django_db
def test_aggregate_distinct_counts_and_sorts():
    baker.make("bpp.Autor", nazwisko="Wawruszak", imiona="Anna")
    names = ["Anna Wawruszak", "Anna Wawruszak", "Zzz Ostatni", "Aaa Pierwszy"]
    out = aggregate_distinct(names)
    by_name = {d.nazwisko_zrodlowe: d for d in out}
    assert by_name["Anna Wawruszak"].wystapien == 2
    families = [d.family for d in out]
    assert families == sorted(families, key=sort_key)
