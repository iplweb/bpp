"""FD#603: the publication deduplicator must find duplicates of the same type
(article-article, book-book), keep "not a duplicate" decisions across rescans
and never report the same pair twice."""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from deduplikator_publikacji.models import (
    PublicationDuplicateCandidate,
    PublicationDuplicateScanRun,
)
from deduplikator_publikacji.tasks import (
    MAX_MATCHES_PER_MODEL,
    MAX_TITLE_MATCHES_PER_MODEL,
    _find_duplicates_for_publication,
    scan_for_duplicates,
)
from import_common.core import matchuj_publikacje

YEAR = 2024

# Measured query counts per publication (see the query count tests below).
QUERIES_NO_DUPLICATE = 6
QUERIES_WORST_CASE = 10

TITLE = (
    "Wpływ długotrwałej suplementacji witaminą D na gęstość mineralną kości "
    "u kobiet po menopauzie w populacji wielkopolskiej"
)
# Same title, one word differs ("wielkopolskiej" -> "małopolskiej").
TITLE_ONE_WORD_DIFFERENT = (
    "Wpływ długotrwałej suplementacji witaminą D na gęstość mineralną kości "
    "u kobiet po menopauzie w populacji małopolskiej"
)
# Same title, one word added.
TITLE_ONE_WORD_ADDED = (
    "Wpływ długotrwałej suplementacji witaminą D na gęstość mineralną kości "
    "u kobiet po menopauzie w populacji wielkopolskiej wsi"
)

BOOK_TITLE = (
    "Podstawy nowoczesnej chirurgii małoinwazyjnej jamy brzusznej. "
    "Podręcznik dla lekarzy rezydentów"
)
# One word differs ("lekarzy" -> "młodych").
BOOK_TITLE_ONE_WORD_DIFFERENT = (
    "Podstawy nowoczesnej chirurgii małoinwazyjnej jamy brzusznej. "
    "Podręcznik dla młodych rezydentów"
)

OTHER_TITLE = (
    "Analiza kosztów hospitalizacji pacjentów z niewydolnością serca "
    "w szpitalach powiatowych"
)


def _run_scan(**kw):
    kw.setdefault("year_from", YEAR)
    kw.setdefault("year_to", YEAR)
    result = scan_for_duplicates.apply(kwargs=kw).get()
    assert result["status"] == "success", result
    return PublicationDuplicateScanRun.objects.get(pk=result["scan_run_id"])


def _pairs(scan_run):
    """Direction-independent set of pairs found in a scan."""
    return {
        frozenset(
            [
                (c.original_type, c.original_object_id),
                (c.duplicate_type, c.duplicate_object_id),
            ]
        )
        for c in scan_run.candidates.all()
    }


def _pair(a, b):
    return frozenset(
        [(a._meta.model_name, a.pk), (b._meta.model_name, b.pk)],
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "other_title", [TITLE_ONE_WORD_DIFFERENT, TITLE_ONE_WORD_ADDED]
)
def test_dwa_artykuly_z_tytulem_rozniacym_sie_slowem_sa_para(other_title):
    a = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=TITLE, rok=YEAR)
    b = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=other_title, rok=YEAR)

    scan = _run_scan()

    assert _pair(a, b) in _pairs(scan)
    assert scan.candidates.count() == 1


@pytest.mark.django_db
def test_dwie_ksiazki_z_tytulem_rozniacym_sie_slowem_sa_para():
    a = baker.make(Wydawnictwo_Zwarte, tytul_oryginalny=BOOK_TITLE, rok=YEAR)
    b = baker.make(
        Wydawnictwo_Zwarte, tytul_oryginalny=BOOK_TITLE_ONE_WORD_DIFFERENT, rok=YEAR
    )

    scan = _run_scan()

    assert _pair(a, b) in _pairs(scan)


@pytest.mark.django_db
def test_trzy_kopie_artykulu_daja_trzy_pary_bez_odwrotnych():
    a = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=TITLE, rok=YEAR)
    b = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=TITLE, rok=YEAR)
    c = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=TITLE_ONE_WORD_ADDED, rok=YEAR)

    scan = _run_scan()

    assert _pairs(scan) == {_pair(a, b), _pair(a, c), _pair(b, c)}
    # No (A, B) + (B, A): one row per pair.
    assert scan.candidates.count() == 3


@pytest.mark.django_db
def test_inny_rok_ani_inny_tytul_nie_daja_pary():
    baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=TITLE, rok=YEAR)
    baker.make(
        Wydawnictwo_Ciagle, tytul_oryginalny=TITLE_ONE_WORD_DIFFERENT, rok=YEAR - 1
    )
    baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=OTHER_TITLE, rok=YEAR)

    scan = _run_scan(year_from=YEAR - 1, year_to=YEAR)

    assert scan.candidates.count() == 0


@pytest.mark.django_db
def test_doi_zapisany_inaczej_nadal_daje_pare():
    a = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny=TITLE,
        rok=YEAR,
        doi="10.1234/ABC.2024.1",
    )
    b = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny=TITLE,
        rok=YEAR,
        doi="https://doi.org/10.1234/abc.2024.1",
    )

    scan = _run_scan()

    assert _pairs(scan) == {_pair(a, b)}
    candidate = scan.candidates.get()
    assert "DOI" in candidate.match_reasons
    assert candidate.similarity_score == 1.0


@pytest.mark.django_db
def test_artykul_i_rozdzial_nadal_sa_para():
    article = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=TITLE, rok=YEAR)
    chapter = baker.make(
        Wydawnictwo_Zwarte, tytul_oryginalny=TITLE_ONE_WORD_ADDED, rok=YEAR
    )

    scan = _run_scan()

    assert _pairs(scan) == {_pair(article, chapter)}


@pytest.mark.django_db
def test_nie_jest_duplikatem_przetrwa_ponowne_skanowanie():
    a = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=TITLE, rok=YEAR)
    b = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=TITLE_ONE_WORD_ADDED, rok=YEAR)
    c = baker.make(Wydawnictwo_Zwarte, tytul_oryginalny=TITLE, rok=YEAR)

    first = _run_scan()
    assert _pairs(first) == {_pair(a, b), _pair(a, c), _pair(b, c)}
    rejected = next(
        cand
        for cand in first.candidates.all()
        if {cand.original_object_id, cand.duplicate_object_id} == {a.pk, b.pk}
        and cand.original_type == cand.duplicate_type
    )
    rejected.status = PublicationDuplicateCandidate.Status.NOT_DUPLICATE
    rejected.save()

    second = _run_scan()

    # The rejected pair does not come back; the other pairs are found again.
    assert _pairs(second) == {_pair(a, c), _pair(b, c)}
    # The decision itself is kept.
    rejected.refresh_from_db()
    assert rejected.status == PublicationDuplicateCandidate.Status.NOT_DUPLICATE
    # Pending pairs of the earlier scan are replaced, as before.
    assert not first.candidates.exclude(pk=rejected.pk).exists()


@pytest.mark.django_db
def test_decyzja_o_usunietym_rekordzie_jest_kasowana():
    a = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=TITLE, rok=YEAR)
    b = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=TITLE_ONE_WORD_ADDED, rok=YEAR)
    first = _run_scan()
    rejected = first.candidates.get()
    rejected.status = PublicationDuplicateCandidate.Status.NOT_DUPLICATE
    rejected.save()

    b.delete()
    _run_scan()

    assert not PublicationDuplicateCandidate.objects.filter(pk=rejected.pk).exists()
    assert Wydawnictwo_Ciagle.objects.filter(pk=a.pk).exists()


def _setup_query_count_db():
    baker.make(Wydawnictwo_Ciagle, _quantity=20, rok=YEAR)
    baker.make(Wydawnictwo_Zwarte, _quantity=20, rok=YEAR)
    scan_run = baker.make(PublicationDuplicateScanRun)
    ct = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)
    ContentType.objects.get_for_model(Wydawnictwo_Zwarte)  # warm the cache
    return scan_run, ct


@pytest.mark.django_db
def test_liczba_zapytan_dla_publikacji_bez_duplikatu(django_assert_max_num_queries):
    """The common case: a publication without any duplicate costs one lookup
    chain plus one title query per publication model."""
    scan_run, ct = _setup_query_count_db()
    pub = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny=TITLE,
        rok=YEAR,
        doi="10.1234/abc.2024.1",
        www="https://example.com/a",
    )

    with django_assert_max_num_queries(QUERIES_NO_DUPLICATE):
        candidates = _find_duplicates_for_publication(pub, ct, scan_run, set())

    assert candidates == []


@pytest.mark.django_db
def test_liczba_zapytan_na_publikacje_jest_ograniczona(django_assert_max_num_queries):
    """Worst case (many copies of the same title): the number of queries
    and of reported pairs is capped, whatever the size of the database."""
    scan_run, ct = _setup_query_count_db()
    pub = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny=TITLE,
        rok=YEAR,
        doi="10.1234/abc.2024.1",
        www="https://example.com/a",
    )
    baker.make(
        Wydawnictwo_Ciagle,
        _quantity=10,
        tytul_oryginalny=TITLE,
        rok=YEAR,
        doi="10.1234/abc.2024.1",
    )

    with django_assert_max_num_queries(QUERIES_WORST_CASE):
        candidates = _find_duplicates_for_publication(pub, ct, scan_run, set())

    assert len(candidates) == MAX_MATCHES_PER_MODEL + MAX_TITLE_MATCHES_PER_MODEL


@pytest.mark.django_db
def test_matchuj_publikacje_bez_exclude_dziala_jak_dotad():
    """Other callers (importers) do not pass ``exclude_pks`` -- for them the
    best match is still returned, including the record itself."""
    a = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=TITLE, rok=YEAR)
    baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=TITLE_ONE_WORD_ADDED, rok=YEAR)

    assert matchuj_publikacje(Wydawnictwo_Ciagle, title=TITLE, year=YEAR) == a
    assert (
        matchuj_publikacje(
            Wydawnictwo_Ciagle, title=TITLE, year=YEAR, exclude_pks={a.pk}
        )
        is not None
    )


@pytest.mark.django_db
def test_matchuj_publikacje_bez_dopasowania_po_tytule():
    """``matchuj_po_tytule=False`` (used by the deduplicator) skips only the
    title-similarity step; the default keeps it."""
    baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=TITLE, rok=YEAR)

    assert matchuj_publikacje(Wydawnictwo_Ciagle, title=TITLE, year=YEAR)
    assert (
        matchuj_publikacje(
            Wydawnictwo_Ciagle, title=TITLE, year=YEAR, matchuj_po_tytule=False
        )
        is None
    )


@pytest.mark.django_db
def test_odrzucenie_w_trakcie_skanowania_nie_wraca(monkeypatch):
    """A pair marked "not a duplicate" (in the list of an earlier scan) while
    a scan is running does not come back as pending in that scan."""
    from deduplikator_publikacji import tasks

    a = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=TITLE, rok=YEAR)
    b = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=TITLE_ONE_WORD_ADDED, rok=YEAR)
    ct = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)
    old_scan = baker.make(PublicationDuplicateScanRun, year_from=2000, year_to=2000)

    original = tasks._find_duplicates_for_publication
    calls = []

    def find_and_reject_meanwhile(*args, **kw):
        if not calls:
            baker.make(
                PublicationDuplicateCandidate,
                scan_run=old_scan,
                original_content_type=ct,
                original_object_id=b.pk,
                duplicate_content_type=ct,
                duplicate_object_id=a.pk,
                similarity_score=0.9,
                status=PublicationDuplicateCandidate.Status.NOT_DUPLICATE,
            )
        calls.append(1)
        return original(*args, **kw)

    monkeypatch.setattr(
        tasks, "_find_duplicates_for_publication", find_and_reject_meanwhile
    )

    scan = _run_scan()

    assert not scan.candidates.exists()
    assert scan.duplicates_found == 0


@pytest.mark.django_db
def test_numery_czesci_nie_zaslaniaja_duplikatu():
    """Other parts of a series ("cz. 3" ... "cz. 8") are more similar than the
    real duplicate of "cz. 2", but are filtered out by the part-number check
    -- they must not use up the title-query limit."""
    a = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=f"{TITLE} cz. 2", rok=YEAR)
    for part in range(3, 9):
        baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=f"{TITLE} cz. {part}", rok=YEAR)
    b = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny=f"{TITLE_ONE_WORD_DIFFERENT} cz. 2",
        rok=YEAR,
    )

    scan_run = baker.make(PublicationDuplicateScanRun)
    ct = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)

    candidates = _find_duplicates_for_publication(a, ct, scan_run, set())

    assert [c.duplicate_object_id for c in candidates] == [b.pk]


@pytest.mark.django_db
def test_admin_nie_usuwa_skanowania_z_decyzjami(admin_client):
    with_decision = baker.make(PublicationDuplicateScanRun)
    baker.make(
        PublicationDuplicateCandidate,
        scan_run=with_decision,
        similarity_score=0.9,
        status=PublicationDuplicateCandidate.Status.NOT_DUPLICATE,
    )
    without_decision = baker.make(PublicationDuplicateScanRun)

    def delete_url(obj):
        return reverse(
            "admin:deduplikator_publikacji_publicationduplicatescanrun_delete",
            args=[obj.pk],
        )

    assert admin_client.get(delete_url(with_decision)).status_code == 403
    assert admin_client.get(delete_url(without_decision)).status_code == 200

    changelist = admin_client.get(
        reverse("admin:deduplikator_publikacji_publicationduplicatescanrun_changelist")
    )
    assert "delete_selected" not in changelist.content.decode()
