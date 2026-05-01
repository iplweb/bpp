"""Testy fazy general w skanowaniu duplikatów."""

import pytest
from model_bakery import baker

from deduplikator_autorow.models import (
    DuplicateCandidate,
    DuplicateScanRun,
    IgnoredAuthor,
    NotADuplicate,
)
from deduplikator_autorow.tasks import _run_general_phase


@pytest.mark.django_db
def test_general_finds_simple_pair():
    """Dwóch autorów o tym samym nazwisku/imieniu, żaden bez OsobaZInstytucji."""
    baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    scan = DuplicateScanRun.objects.create()
    _run_general_phase(scan, min_confidence=50)
    cands = DuplicateCandidate.objects.filter(scan_run=scan, scan_mode="general")
    assert cands.count() == 1


@pytest.mark.django_db
def test_general_skips_cluster_with_osoba_instytucji():
    """Klaster {A, B, C} gdzie B ma OsobaZInstytucji → klaster pominięty."""
    baker.make("bpp.Autor", nazwisko="Nowak", imiona="Anna")
    b = baker.make("bpp.Autor", nazwisko="Nowak", imiona="Anna")
    baker.make("bpp.Autor", nazwisko="Nowak", imiona="Anna")
    scientist = baker.make("pbn_api.Scientist")
    b.pbn_uid = scientist
    b.save()
    baker.make("pbn_api.OsobaZInstytucji", personId=scientist)

    scan = DuplicateScanRun.objects.create()
    _run_general_phase(scan, min_confidence=50)
    cands = DuplicateCandidate.objects.filter(scan_run=scan, scan_mode="general")
    assert cands.count() == 0


@pytest.mark.django_db
def test_general_main_chosen_by_orcid():
    """Z dwóch autorów ORCID-owany wygrywa jako main."""
    a = baker.make("bpp.Autor", nazwisko="Adams", imiona="Eve", orcid=None)
    b = baker.make(
        "bpp.Autor",
        nazwisko="Adams",
        imiona="Eve",
        orcid="0000-0001-2345-6789",
    )
    scan = DuplicateScanRun.objects.create()
    _run_general_phase(scan, min_confidence=50)
    cand = DuplicateCandidate.objects.get(scan_run=scan, scan_mode="general")
    assert cand.main_autor_id == b.pk
    assert cand.duplicate_autor_id == a.pk


@pytest.mark.django_db
def test_general_pk_tiebreaker():
    """Wszystko równe → niższy pk wygrywa jako main."""
    a = baker.make("bpp.Autor", nazwisko="Black", imiona="Carl")
    b = baker.make("bpp.Autor", nazwisko="Black", imiona="Carl")
    lower_pk = min(a.pk, b.pk)
    higher_pk = max(a.pk, b.pk)

    scan = DuplicateScanRun.objects.create()
    _run_general_phase(scan, min_confidence=50)
    cand = DuplicateCandidate.objects.get(scan_run=scan, scan_mode="general")
    assert cand.main_autor_id == lower_pk
    assert cand.duplicate_autor_id == higher_pk


@pytest.mark.django_db
def test_general_respects_ignored_author():
    a = baker.make("bpp.Autor", nazwisko="Yellow", imiona="Sun")
    baker.make("bpp.Autor", nazwisko="Yellow", imiona="Sun")
    user = baker.make("bpp.BppUser")
    IgnoredAuthor.objects.create(autor=a, created_by=user)

    scan = DuplicateScanRun.objects.create()
    _run_general_phase(scan, min_confidence=50)
    assert DuplicateCandidate.objects.filter(scan_run=scan).count() == 0


@pytest.mark.django_db
def test_general_respects_not_a_duplicate():
    a = baker.make("bpp.Autor", nazwisko="Green", imiona="Mike")
    baker.make("bpp.Autor", nazwisko="Green", imiona="Mike")
    user = baker.make("bpp.BppUser")
    NotADuplicate.objects.create(autor=a, created_by=user)

    scan = DuplicateScanRun.objects.create()
    _run_general_phase(scan, min_confidence=50)
    assert DuplicateCandidate.objects.filter(scan_run=scan).count() == 0


@pytest.mark.django_db
def test_general_transitive_cluster():
    """Trzech 'Linker Jan' tworzy klaster {A,B,C} → 2 pary z jednym main."""
    a = baker.make("bpp.Autor", nazwisko="Linker", imiona="Jan")
    b = baker.make("bpp.Autor", nazwisko="Linker", imiona="Jan")
    c = baker.make("bpp.Autor", nazwisko="Linker", imiona="Jan")
    scan = DuplicateScanRun.objects.create()
    _run_general_phase(scan, min_confidence=50)
    cands = DuplicateCandidate.objects.filter(scan_run=scan, scan_mode="general")
    assert cands.count() == 2
    main_pks = {c.main_autor_id for c in cands}
    assert len(main_pks) == 1
    assert main_pks == {min(a.pk, b.pk, c.pk)}
