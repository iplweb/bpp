import pytest
from django.utils import timezone
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle
from bpp.models.zrodlo import Rodzaj_Zrodla, Zasieg_Zrodla, Zrodlo
from deduplikator_zrodel.models import (
    ScanZrodelForDuplicates,
    SourceDuplicateCandidate,
)


@pytest.fixture
def rodzaj():
    return Rodzaj_Zrodla.objects.create(nazwa="Czasopismo")


@pytest.fixture
def zasieg():
    return Zasieg_Zrodla.objects.create(nazwa="Krajowy")


@pytest.fixture
def make_zrodlo(rodzaj, zasieg):
    def _make(*, z_publikacja=True, **kw):
        kw.setdefault("rodzaj", rodzaj)
        kw.setdefault("zasieg", zasieg)
        z = baker.make(Zrodlo, **kw)
        if z_publikacja:
            baker.make(Wydawnictwo_Ciagle, zrodlo=z)
        return z

    return _make


@pytest.fixture
def completed_scan(admin_user):
    """Ukończony (FINISHED_OK) skan bez kandydatów — do dołożenia par w teście."""

    def _make(owner=None, **candidates_kw):
        op = ScanZrodelForDuplicates.objects.create(
            owner=owner or admin_user,
            started_on=timezone.now(),
            finished_on=timezone.now(),
            finished_successfully=True,
        )
        return op

    return _make


@pytest.fixture
def make_candidate():
    def _make(scan, main_zrodlo, duplicate_zrodlo, *, confidence_score=150, **kw):
        return SourceDuplicateCandidate.objects.create(
            scan=scan,
            main_zrodlo=main_zrodlo,
            duplicate_zrodlo=duplicate_zrodlo,
            confidence_score=confidence_score,
            main_nazwa=main_zrodlo.nazwa or "",
            duplicate_nazwa=duplicate_zrodlo.nazwa or "",
            **kw,
        )

    return _make
