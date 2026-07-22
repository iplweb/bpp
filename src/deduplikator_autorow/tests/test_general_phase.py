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
from deduplikator_autorow.utils.cluster import find_clusters


@pytest.mark.django_db
def test_general_finds_simple_pair():
    """Dwóch autorów o tym samym nazwisku/imieniu, żaden bez OsobaZInstytucji."""
    a = baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    b = baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    scan = DuplicateScanRun.objects.create()
    _run_general_phase(scan, min_confidence=50)

    # UWAGA (flake pod xdist/shardingiem): faza general skanuje CAŁĄ tabelę
    # autorów, więc ambient autorzy „Kowalski Jan" scommitowani przez sąsiednie
    # testy (na współdzielonym workerze) wpadają do wspólnego bucketu
    # „kowalski", doczepiają się do klastra i — mając niższy pk — przejmują
    # rolę `main`. Wtedy zamiast dokładnie jednej pary {a, b} emitowane są np.
    # (ambient, a) + (ambient, b) i asercja na globalnym `count() == 1` pękała
    # (obserwowane w CI: 4 zamiast 1). Testujemy więc WŁASNĄ inwariantę: a i b
    # lądują w jednym klastrze duplikatów — odporne na ambient szum (identyczny
    # wzorzec co ``test_general_finds_pair_with_unicode_hyphen_variant``).
    cands = DuplicateCandidate.objects.filter(scan_run=scan, scan_mode="general")
    edges = [(c.main_autor_id, c.duplicate_autor_id) for c in cands]
    clusters = find_clusters(edges)
    assert any({a.pk, b.pk} <= cluster for cluster in clusters), (
        f"Dwóch autorów o identycznym nazwisku/imieniu powinno trafić do "
        f"jednego klastra duplikatów; klastry={clusters}"
    )


@pytest.mark.django_db
def test_general_finds_pair_with_unicode_hyphen_variant():
    """Nazwiska z różnymi Unicode'owymi myślnikami trafiają do jednego bucketu."""
    a = baker.make("bpp.Autor", nazwisko="Kowalski-Nowak", imiona="Dorota")
    b = baker.make("bpp.Autor", nazwisko="Kowalski\u2011Nowak", imiona="Dorota")

    scan = DuplicateScanRun.objects.create()
    _run_general_phase(scan, min_confidence=50)

    # UWAGA (flake pod xdist/shardingiem): faza general skanuje CAŁĄ tabelę
    # autorów, więc ambient autorzy scommitowani przez sąsiednie testy
    # (transactional / live-server) o pospolitych polskich nazwiskach
    # ("Nowak", "Kowalski") wpadają do wspólnych bucketów "kowalski"/"nowak",
    # doczepiają się do klastra i — mając niższy pk — przejmują rolę `main`.
    # Wtedy zamiast bezpośredniej pary {a, b} emitowane są (ambient, a) +
    # (ambient, b), przez co asercja na dokładnej liczbie/tożsamości pary
    # pękała. Testujemy więc WYŁĄCZNIE własną inwariantę: dzięki normalizacji
    # myślnika Unicode a i b lądują w tym samym klastrze duplikatów (bez
    # normalizacji trafiłyby do rozłącznych bucketów i różnych klastrów).
    cands = DuplicateCandidate.objects.filter(scan_run=scan, scan_mode="general")
    edges = [(c.main_autor_id, c.duplicate_autor_id) for c in cands]
    clusters = find_clusters(edges)
    assert any({a.pk, b.pk} <= cluster for cluster in clusters), (
        f"Autorzy różniący się tylko wariantem myślnika Unicode powinni "
        f"trafić do jednego klastra duplikatów; klastry={clusters}"
    )


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
def test_general_phase_no_sql_per_candidate():
    """_run_general_phase nie robi SQL per candidate (meta-cache)."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    # 5 par z dwoma autorami każda → 5 candidates
    for nazwisko in ["Aaa", "Bbb", "Ccc", "Ddd", "Eee"]:
        baker.make("bpp.Autor", nazwisko=nazwisko, imiona="Jan")
        baker.make("bpp.Autor", nazwisko=nazwisko, imiona="Jan")

    scan = DuplicateScanRun.objects.create()
    with CaptureQueriesContext(connection) as ctx:
        _run_general_phase(scan, min_confidence=50)
    n5 = len(ctx.captured_queries)

    # Drugi run z 10 par
    for nazwisko in ["Fff", "Ggg", "Hhh", "Iii", "Jjj"]:
        baker.make("bpp.Autor", nazwisko=nazwisko, imiona="Jan")
        baker.make("bpp.Autor", nazwisko=nazwisko, imiona="Jan")

    scan2 = DuplicateScanRun.objects.create()
    with CaptureQueriesContext(connection) as ctx:
        _run_general_phase(scan2, min_confidence=50)
    n10 = len(ctx.captured_queries)

    # Liczba zapytań nie powinna rosnąć liniowo z liczbą candidates.
    # Bulk_create może tworzyć 1-2 dodatkowych SAVEPOINT/INSERT, ale
    # nie 5+ per candidate.
    diff = n10 - n5
    assert diff <= 5, (
        f"Per-candidate SQL detected: 5 candidates → {n5} queries, "
        f"10 candidates → {n10} queries (diff={diff})"
    )


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
