"""TDD dla skanu duplikatów źródeł w tle (perform_scan + ScanZrodelForDuplicates).

Skan iteruje źródła-seedy (pub_count > 0 AND pbn_uid.mniswId not null), dla
każdego znajduje kandydatów przez utils.znajdz_podobne_zrodla i zapisuje pary
o dodatnim score jako SourceDuplicateCandidate — raz na nieuporządkowaną parę.
"""

import pytest
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle
from bpp.models.zrodlo import Rodzaj_Zrodla, Zasieg_Zrodla, Zrodlo
from deduplikator_zrodel.models import (
    ScanZrodelForDuplicates,
    SourceDuplicateCandidate,
)
from deduplikator_zrodel.operations import perform_scan
from pbn_api.models import Journal

try:
    from liveops.progress import TextProgress
except ImportError:  # pragma: no cover - liveops zawsze zainstalowany
    TextProgress = None


@pytest.fixture
def rodzaj():
    return Rodzaj_Zrodla.objects.create(nazwa="Czasopismo")


@pytest.fixture
def zasieg():
    return Zasieg_Zrodla.objects.create(nazwa="Krajowy")


def _zrodlo(rodzaj, zasieg, *, z_publikacja=True, **kw):
    """Źródło z powiązanym wydawnictwem ciągłym (pub_count > 0)."""
    kw.setdefault("rodzaj", rodzaj)
    kw.setdefault("zasieg", zasieg)
    z = baker.make(Zrodlo, **kw)
    if z_publikacja:
        baker.make(Wydawnictwo_Ciagle, zrodlo=z)
    return z


def _para_duplikatow(rodzaj, zasieg, mniswId=111):
    """Zwraca (seed, dup): identyczny ISSN + nazwa; seed ma pbn_uid z mniswId
    (kwalifikuje jako seed), dup bez pbn_uid (kandydat, nie wykluczony)."""
    seed = _zrodlo(
        rodzaj,
        zasieg,
        nazwa="Acta Testica",
        skrot="AT",
        issn="1234-5678",
        pbn_uid=baker.make(Journal, mniswId=mniswId),
    )
    dup = _zrodlo(rodzaj, zasieg, nazwa="Acta Testica", skrot="AT", issn="1234-5678")
    return seed, dup


@pytest.mark.django_db
def test_perform_scan_finds_duplicate_pair(rodzaj, zasieg, admin_user):
    seed, dup = _para_duplikatow(rodzaj, zasieg)

    op = ScanZrodelForDuplicates.objects.create(owner=admin_user)
    perform_scan(op, TextProgress(op))

    cands = SourceDuplicateCandidate.objects.filter(scan=op)
    assert cands.count() == 1
    c = cands.get()
    assert {c.main_zrodlo_id, c.duplicate_zrodlo_id} == {seed.id, dup.id}
    assert c.confidence_score > 0
    op.refresh_from_db()
    assert op.duplicates_found == 1
    assert op.total_sources >= 1


@pytest.mark.django_db
def test_mirror_pair_recorded_once(rodzaj, zasieg, admin_user):
    """Dwa wzajemne duplikaty (oba seedy, ten sam Journal) → JEDEN wiersz.

    Bez seen-set drugi kierunek próbowałby zapisać lustrzaną parę i wpadł na
    unikalny constraint. Test pinuje, że skan nie wywala się i tworzy 1 parę.
    """
    journal = baker.make(Journal, mniswId=111)
    a = _zrodlo(rodzaj, zasieg, nazwa="Acta Testica", skrot="AT", pbn_uid=journal)
    b = _zrodlo(rodzaj, zasieg, nazwa="Inna Nazwa", skrot="IN", pbn_uid=journal)

    op = ScanZrodelForDuplicates.objects.create(owner=admin_user)
    perform_scan(op, TextProgress(op))

    cands = SourceDuplicateCandidate.objects.filter(scan=op)
    assert cands.count() == 1
    assert {cands.get().main_zrodlo_id, cands.get().duplicate_zrodlo_id} == {a.id, b.id}


@pytest.mark.django_db
def test_canonical_main_is_higher_pubcount(rodzaj, zasieg, admin_user):
    """main_zrodlo = źródło o większej liczbie publikacji."""
    seed = _zrodlo(
        rodzaj,
        zasieg,
        nazwa="Acta Testica",
        skrot="AT",
        issn="1234-5678",
        pbn_uid=baker.make(Journal, mniswId=111),
    )
    # seed dostaje 2 dodatkowe publikacje (razem 3 vs 1 u duplikatu)
    baker.make(Wydawnictwo_Ciagle, zrodlo=seed, _quantity=2)
    dup = _zrodlo(rodzaj, zasieg, nazwa="Acta Testica", skrot="AT", issn="1234-5678")

    op = ScanZrodelForDuplicates.objects.create(owner=admin_user)
    perform_scan(op, TextProgress(op))

    c = SourceDuplicateCandidate.objects.get(scan=op)
    assert c.main_zrodlo_id == seed.id
    assert c.duplicate_zrodlo_id == dup.id
    assert c.main_pub_count == 3
    assert c.duplicate_pub_count == 1


@pytest.mark.django_db
def test_canonical_ministerial_is_main_even_with_fewer_pubs(rodzaj, zasieg, admin_user):
    """Źródło z (efektywnym) MNiSW ID MUSI być stroną docelową (`main`),
    nawet gdy ma MNIEJ publikacji niż duplikat.

    Przepięcie źródła ministerialnego na cel bez tego samego MNiSW ID jest
    odrzucane przez walidację przemapowania — więc deduplikator nie może
    proponować takiego kierunku. Orientacja po mniswId ma priorytet nad
    liczbą publikacji.
    """
    # Ministerialne, ale z MNIEJSZĄ liczbą publikacji (1).
    seed = _zrodlo(
        rodzaj,
        zasieg,
        nazwa="Acta Testica",
        skrot="AT",
        issn="1234-5678",
        pbn_uid=baker.make(Journal, mniswId=111),
    )
    # Nieministerialne, ale z WIĘKSZĄ liczbą publikacji (3).
    dup = _zrodlo(rodzaj, zasieg, nazwa="Acta Testica", skrot="AT", issn="1234-5678")
    baker.make(Wydawnictwo_Ciagle, zrodlo=dup, _quantity=2)

    op = ScanZrodelForDuplicates.objects.create(owner=admin_user)
    perform_scan(op, TextProgress(op))

    c = SourceDuplicateCandidate.objects.get(scan=op)
    assert c.main_zrodlo_id == seed.id  # ministerialne = cel
    assert c.duplicate_zrodlo_id == dup.id  # nieministerialne = przepinane
    assert c.main_pub_count == 1
    assert c.duplicate_pub_count == 3


@pytest.mark.django_db
def test_canonical_prefers_ministerial_over_pubcount(rodzaj, zasieg):
    """Bezpośredni test `_canonical`: mniswId bije liczbę publikacji, niezależnie
    od kolejności argumentów."""
    from deduplikator_zrodel.operations import _canonical

    minz = _zrodlo(
        rodzaj, zasieg, z_publikacja=False, pbn_uid=baker.make(Journal, mniswId=5)
    )
    nonmin = _zrodlo(rodzaj, zasieg, z_publikacja=False)
    minz.pub_count = 1
    nonmin.pub_count = 99

    for a, b in [(nonmin, minz), (minz, nonmin)]:
        main, dup = _canonical(a, b)
        assert main.pk == minz.pk
        assert dup.pk == nonmin.pk


@pytest.mark.django_db
def test_canonical_deleted_mnisw_not_ministerial(rodzaj, zasieg):
    """Źródło z mniswId ale statusem DELETED nie jest „ministerialne" (zgodnie
    z regułą walidacji) — orientacja spada z powrotem do liczby publikacji."""
    from deduplikator_zrodel.operations import _canonical

    delz = _zrodlo(
        rodzaj,
        zasieg,
        z_publikacja=False,
        pbn_uid=baker.make(Journal, mniswId=5, status="DELETED"),
    )
    other = _zrodlo(rodzaj, zasieg, z_publikacja=False)
    delz.pub_count = 1
    other.pub_count = 99

    main, dup = _canonical(delz, other)
    assert main.pk == other.pk  # DELETED nie liczy się jako ministerialne
    assert dup.pk == delz.pk


@pytest.mark.django_db
def test_notaduplicate_pair_excluded(rodzaj, zasieg, admin_user):
    """Para oznaczona NotADuplicate nie trafia do wyników."""
    from deduplikator_zrodel.models import NotADuplicate

    seed, dup = _para_duplikatow(rodzaj, zasieg)
    NotADuplicate.objects.create(zrodlo=seed, duplikat=dup)
    NotADuplicate.objects.create(zrodlo=dup, duplikat=seed)

    op = ScanZrodelForDuplicates.objects.create(owner=admin_user)
    perform_scan(op, TextProgress(op))

    assert SourceDuplicateCandidate.objects.filter(scan=op).count() == 0
    op.refresh_from_db()
    assert op.duplicates_found == 0


@pytest.mark.django_db
def test_ignored_source_excluded(rodzaj, zasieg, admin_user):
    """Źródło w IgnoredSource nie jest kandydatem."""
    from deduplikator_zrodel.models import IgnoredSource

    seed, dup = _para_duplikatow(rodzaj, zasieg)
    IgnoredSource.objects.create(zrodlo=dup)

    op = ScanZrodelForDuplicates.objects.create(owner=admin_user)
    perform_scan(op, TextProgress(op))

    assert SourceDuplicateCandidate.objects.filter(scan=op).count() == 0


# --- format_progress_status (czysty helper ETA/liczników) --------------------

from datetime import datetime, timedelta  # noqa: E402
from datetime import timezone as _dt_tz  # noqa: E402

from deduplikator_zrodel.operations import format_progress_status  # noqa: E402


def test_format_progress_status_without_eta_when_nothing_scanned():
    s = format_progress_status(0, 500, 0)
    assert "0/500" in s
    assert "pozostało" not in s  # brak danych do ETA


def test_format_progress_status_with_counts_and_eta():
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=_dt_tz.utc)
    now = t0 + timedelta(seconds=60)  # 60 s, 50/100 → ~60 s pozostało
    s = format_progress_status(50, 100, 7, started_on=t0, now=now)
    assert "50/100" in s
    assert "7" in s
    assert "pozostało" in s
    assert "zakończenie" in s
