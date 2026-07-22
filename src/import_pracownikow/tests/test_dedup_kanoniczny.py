"""Poz. 7: kierowanie zatrudnienia na rekord ORYGINALNY/GŁÓWNY.

``kanoniczny_autor`` mapuje trafiony rekord-duplikat na oryginał (z API
instytucjonalnego PBN) na podstawie zmaterializowanego skanu deduplikatora
(``DuplicateCandidate``). BEZ scalania rekordów. Integracja z pipeline sprawdza,
że ``_dopasuj_autora_i_status`` zwraca oryginał ze statusem ``STATUS_DEDUP``.
"""

import pytest
from model_bakery import baker

from bpp.models import Autor
from deduplikator_autorow.models import (
    DuplicateCandidate,
    DuplicateScanRun,
    NotADuplicate,
)
from import_pracownikow.dedup import PROG_KANONICZNY, kanoniczny_autor
from import_pracownikow.pewnosc import STATUS_DEDUP


def _kandydat(
    main,
    dup,
    *,
    percent,
    status=DuplicateCandidate.Status.PENDING,
    instytucjonalny=True,
):
    """Tworzy wpis skanu duplikat→oryginał. ``instytucjonalny`` steruje, czy
    oryginał ma powiązaną ``OsobaZInstytucji`` (wymóg przekierowania)."""
    from pbn_api.models import OsobaZInstytucji

    osoba = baker.make(OsobaZInstytucji) if instytucjonalny else None
    return baker.make(
        DuplicateCandidate,
        scan_run=baker.make(DuplicateScanRun),
        main_autor=main,
        duplicate_autor=dup,
        main_osoba_z_instytucji=osoba,
        confidence_percent=percent,
        confidence_score=int(percent * 100),
        status=status,
        main_autor_name=str(main),
        duplicate_autor_name=str(dup),
    )


@pytest.mark.django_db
def test_przekierowuje_duplikat_na_oryginal():
    main = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    dup = baker.make(Autor, nazwisko="Kowalskii", imiona="Jan")
    _kandydat(main, dup, percent=0.95)
    assert kanoniczny_autor(dup) == main


@pytest.mark.django_db
def test_ponizej_progu_nie_przekierowuje():
    main = baker.make(Autor)
    dup = baker.make(Autor)
    _kandydat(main, dup, percent=PROG_KANONICZNY - 0.05)
    assert kanoniczny_autor(dup) == dup


@pytest.mark.django_db
def test_status_not_duplicate_ignorowany():
    main = baker.make(Autor)
    dup = baker.make(Autor)
    _kandydat(main, dup, percent=0.99, status=DuplicateCandidate.Status.NOT_DUPLICATE)
    assert kanoniczny_autor(dup) == dup


@pytest.mark.django_db
def test_respektuje_weto_notaduplicate():
    main = baker.make(Autor)
    dup = baker.make(Autor)
    _kandydat(main, dup, percent=0.99)
    baker.make(NotADuplicate, autor=dup)
    assert kanoniczny_autor(dup) == dup


@pytest.mark.django_db
def test_wymaga_osoby_z_instytucji():
    """Oryginał bez odpowiednika w API instytucjonalnym PBN → brak
    przekierowania (wymóg „z odpowiedniego API")."""
    main = baker.make(Autor)
    dup = baker.make(Autor)
    _kandydat(main, dup, percent=0.99, instytucjonalny=False)
    assert kanoniczny_autor(dup) == dup


@pytest.mark.django_db
def test_bez_kandydata_zwraca_wejscie():
    a = baker.make(Autor)
    assert kanoniczny_autor(a) == a


@pytest.mark.django_db
def test_idempotentny_dla_oryginalu():
    """Rekord główny nie występuje jako ``duplicate_autor`` → no-op."""
    main = baker.make(Autor)
    dup = baker.make(Autor)
    _kandydat(main, dup, percent=0.99)
    assert kanoniczny_autor(main) == main


@pytest.mark.django_db
def test_none_zwraca_none():
    assert kanoniczny_autor(None) is None


@pytest.mark.django_db
def test_wybiera_najpewniejszego_oryginal():
    main_slabszy = baker.make(Autor)
    main_pewny = baker.make(Autor)
    dup = baker.make(Autor)
    _kandydat(main_slabszy, dup, percent=0.85)
    _kandydat(main_pewny, dup, percent=0.98)
    assert kanoniczny_autor(dup) == main_pewny


@pytest.mark.django_db
def test_pipeline_dopasowanie_zwraca_oryginal_ze_statusem_dedup():
    """Integracja: gdy nazwiskowy match trafia SAM duplikat (twardy), a istnieje
    para duplikat→oryginał, ``_dopasuj_autora_i_status`` zwraca oryginał +
    ``STATUS_DEDUP``."""
    from import_pracownikow.pipeline.analyze import _dopasuj_autora_i_status

    # Duplikat ma UNIKALNE nazwisko → jest jedynym kandydatem (twardy match),
    # więc autor≠None i przekierowanie się odpala. Oryginał ma inne nazwisko,
    # więc nie konkuruje jako kandydat.
    dup = baker.make(Autor, nazwisko="Zzzduplikatowy", imiona="Jan")
    main = baker.make(Autor, nazwisko="Zzzoryginalny", imiona="Jan")
    _kandydat(main, dup, percent=0.97)

    autor, status, _kandydaci = _dopasuj_autora_i_status(
        {"imię": "Jan", "nazwisko": "Zzzduplikatowy"}, None, None
    )
    assert autor == main
    assert status == STATUS_DEDUP
