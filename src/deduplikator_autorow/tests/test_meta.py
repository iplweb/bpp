"""Testy budowniczego meta-cache dla autorów."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from deduplikator_autorow.utils.meta import build_autor_meta, build_buckets


@pytest.mark.django_db
def test_meta_includes_basic_fields():
    autor = baker.make(
        "bpp.Autor",
        nazwisko="Kowalski",
        imiona="Jan",
        orcid="0000-0001-2345-6789",
    )
    meta = build_autor_meta()
    assert autor.pk in meta
    m = meta[autor.pk]
    assert m["nazwisko_norm"] == "kowalski"
    assert m["imiona_norm"] == ["jan"]
    assert m["ma_orcid"] is True
    assert m["orcid_value"] == "0000-0001-2345-6789"
    assert m["ma_pbn_uid"] is False
    assert m["ma_tytul"] is False
    assert m["publikacje_count"] == 0
    assert m["max_rok"] == 0
    assert m["lata_publikacji"] == set()


@pytest.mark.django_db
def test_meta_compound_lastname_parts():
    autor = baker.make("bpp.Autor", nazwisko="Gal-Cisoń", imiona="Anna")
    meta = build_autor_meta()
    parts = meta[autor.pk]["nazwisko_parts"]
    assert sorted(parts) == ["cisoń", "gal"]


@pytest.mark.django_db
def test_meta_ma_osoba_z_instytucji_true():
    # Scientist nie ma pola "rekord_w_bpp" — to cached_property po stronie
    # Scientist; związek jest definiowany przez Autor.pbn_uid → Scientist.
    scientist = baker.make("pbn_api.Scientist")
    autor = baker.make("bpp.Autor", nazwisko="Xtest", pbn_uid=scientist)
    baker.make("pbn_api.OsobaZInstytucji", personId=scientist)

    meta = build_autor_meta()
    assert meta[autor.pk]["ma_osoba_z_instytucji"] is True


@pytest.mark.django_db
def test_meta_constant_query_count():
    """Sanity: dodanie autorów nie zwiększa liczby zapytań (no N+1)."""
    baker.make("bpp.Autor", _quantity=5, nazwisko="A")
    with CaptureQueriesContext(connection) as ctx_small:
        build_autor_meta()
    n_small = len(ctx_small.captured_queries)

    baker.make("bpp.Autor", _quantity=20, nazwisko="B")
    with CaptureQueriesContext(connection) as ctx_big:
        build_autor_meta()
    n_big = len(ctx_big.captured_queries)

    assert n_small == n_big, (
        f"N+1 detected: small={n_small} queries, big={n_big} queries"
    )


@pytest.mark.django_db
def test_buckets_includes_lastname_and_parts():
    a1 = baker.make("bpp.Autor", nazwisko="Kowalski")
    a2 = baker.make("bpp.Autor", nazwisko="Gal-Cisoń")
    meta = build_autor_meta()
    buckets = build_buckets(meta)

    assert "kowalski" in buckets
    assert a1.pk in buckets["kowalski"]
    assert "gal" in buckets
    assert "cisoń" in buckets
    assert "gal-cisoń" in buckets
    # reversed compound:
    assert "cisoń-gal" in buckets
    assert a2.pk in buckets["gal-cisoń"]
    assert a2.pk in buckets["cisoń-gal"]
