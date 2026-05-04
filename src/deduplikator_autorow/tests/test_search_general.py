"""Testy generowania par kandydatów w fazie general."""

import pytest
from model_bakery import baker

from deduplikator_autorow.utils.meta import build_autor_meta, build_buckets
from deduplikator_autorow.utils.search_general import (
    BUCKET_MAX_SIZE,
    generate_pairs,
)


@pytest.mark.django_db
def test_simple_lastname_pair():
    a1 = baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    a2 = baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    meta = build_autor_meta()
    buckets = build_buckets(meta)
    pairs = list(generate_pairs(buckets, meta, ignored_pks=set(), notadup_pks=set()))
    pks = {(min(p, q), max(p, q)) for p, q, _, _ in pairs}
    assert (min(a1.pk, a2.pk), max(a1.pk, a2.pk)) in pks


@pytest.mark.django_db
def test_compound_lastname_pair():
    a1 = baker.make("bpp.Autor", nazwisko="Gal-Cisoń", imiona="Anna")
    a2 = baker.make("bpp.Autor", nazwisko="Cisoń-Gal", imiona="Anna")
    meta = build_autor_meta()
    buckets = build_buckets(meta)
    pairs = list(generate_pairs(buckets, meta, ignored_pks=set(), notadup_pks=set()))
    pks = {(min(p, q), max(p, q)) for p, q, _, _ in pairs}
    assert (min(a1.pk, a2.pk), max(a1.pk, a2.pk)) in pks


@pytest.mark.django_db
def test_pair_dedup():
    """Para (a, b) emitowana tylko raz, niezależnie od ile bucketów ją łączy."""
    baker.make("bpp.Autor", nazwisko="Smith", imiona="John")
    baker.make("bpp.Autor", nazwisko="Smith", imiona="John")
    meta = build_autor_meta()
    buckets = build_buckets(meta)
    pairs = list(generate_pairs(buckets, meta, ignored_pks=set(), notadup_pks=set()))
    pair_set = [(p, q) for p, q, _, _ in pairs]
    assert len(pair_set) == len(set(pair_set))


@pytest.mark.django_db
def test_ignored_excluded():
    a1 = baker.make("bpp.Autor", nazwisko="Brown", imiona="Bob")
    baker.make("bpp.Autor", nazwisko="Brown", imiona="Bob")
    meta = build_autor_meta()
    buckets = build_buckets(meta)
    pairs = list(generate_pairs(buckets, meta, ignored_pks={a1.pk}, notadup_pks=set()))
    assert pairs == []


@pytest.mark.django_db
def test_notadup_excluded():
    a1 = baker.make("bpp.Autor", nazwisko="Wilson", imiona="Tim")
    baker.make("bpp.Autor", nazwisko="Wilson", imiona="Tim")
    meta = build_autor_meta()
    buckets = build_buckets(meta)
    pairs = list(generate_pairs(buckets, meta, ignored_pks=set(), notadup_pks={a1.pk}))
    assert pairs == []


@pytest.mark.django_db
def test_oversized_bucket_skipped():
    """Bucket > BUCKET_MAX_SIZE jest pomijany."""
    baker.make(
        "bpp.Autor",
        nazwisko="PopularName",
        _quantity=BUCKET_MAX_SIZE + 1,
    )
    meta = build_autor_meta()
    buckets = build_buckets(meta)
    pairs = list(generate_pairs(buckets, meta, ignored_pks=set(), notadup_pks=set()))
    # Dla tego bucketu (PopularName) — żadne pary nie powinny zostać wyemitowane
    assert pairs == []
