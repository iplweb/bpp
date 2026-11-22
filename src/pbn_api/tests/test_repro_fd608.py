"""FD#608: pusty „Dyscyplina w PBN 2022-2023” po imporcie słowników z PBN.

Słowniki PBN mają daty graniczne w trakcie roku (jak na produkcji, np. APOŻ):

- 2018-01-01 – 2022-11-10,
- 2022-11-11 – 2023-10-05,
- od 2023-10-06 bez końca.

Synchronizacja szukała słownika 2022-2023 warunkiem „od 2023 do 2024”, więc
``pbn_2022_2023`` zostawał pusty i wysyłka publikacji z lat 2022-2023 rzucała
``TlumaczDyscyplinException``.
"""

import copy
import importlib
import uuid
from datetime import date
from pathlib import Path

import pytest
from django.apps import apps as django_apps
from pbn_client.const import PBN_GET_DISCIPLINES_URL

from bpp.decorators import json
from bpp.models import Dyscyplina_Naukowa
from import_common.core import matchuj_dyscypline_pbn_na_dzien
from pbn_api.models import TlumaczDyscyplin
from pbn_api.models.discipline import Discipline, DisciplineGroup


def _trzy_slowniki_jak_w_pbn():
    """Słowniki z fikstury, przycięte i uzupełnione do realnych zakresów PBN."""
    fixture_path = Path(__file__).parent / "fixture_test_get_disciplines.json"
    with open(fixture_path, "rb") as f:
        slownik_2018, slownik_2022 = json.loads(f.read())

    assert slownik_2018["validityDateFrom"] == "2018-01-01"
    assert slownik_2018["validityDateTo"] == "2022-11-10"

    slownik_2022 = copy.deepcopy(slownik_2022)
    slownik_2022["validityDateFrom"] = "2022-11-11"
    slownik_2022["validityDateTo"] = "2023-10-05"

    slownik_2023 = copy.deepcopy(slownik_2022)
    slownik_2023["uuid"] = str(uuid.uuid4())
    slownik_2023["validityDateFrom"] = "2023-10-06"
    slownik_2023["validityDateTo"] = None
    for d in slownik_2023["disciplines"]:
        d["uuid"] = str(uuid.uuid4())

    return [slownik_2018, slownik_2022, slownik_2023]


@pytest.fixture
def pbn_client_trzy_slowniki(pbn_client):
    pbn_client.transport.return_values[PBN_GET_DISCIPLINES_URL] = (
        _trzy_slowniki_jak_w_pbn()
    )
    return pbn_client


def _grupa(od):
    return DisciplineGroup.objects.get(validityDateFrom=od)


@pytest.mark.django_db
def test_fd608_sync_wypelnia_wszystkie_okresy(pbn_client_trzy_slowniki):
    ekonomia = Dyscyplina_Naukowa.objects.create(kod="5.1", nazwa="ekonomia i finanse")
    inz_bezp = Dyscyplina_Naukowa.objects.create(
        kod="2.10", nazwa="inżynieria bezpieczeństwa"
    )

    pbn_client_trzy_slowniki.sync_disciplines()

    td = TlumaczDyscyplin.objects.get(dyscyplina_w_bpp=ekonomia)
    assert td.pbn_2017_2021.parent_group == _grupa(date(2018, 1, 1))
    assert td.pbn_2022_2023 is not None
    assert td.pbn_2022_2023.parent_group == _grupa(date(2022, 11, 11))
    assert td.pbn_2024_now.parent_group == _grupa(date(2023, 10, 6))

    for rok in (2022, 2023):
        assert (
            TlumaczDyscyplin.objects.przetlumacz_dyscypline(ekonomia, rok).code
            == "501"
        )
        # Dyscyplina dodana w słowniku 2022 (brak w słowniku 2018).
        assert (
            TlumaczDyscyplin.objects.przetlumacz_dyscypline(inz_bezp, rok).code
            == "210"
        )

    # Strażnik: inżynierii bezpieczeństwa nie było w słowniku 2018.
    assert (
        TlumaczDyscyplin.objects.get(dyscyplina_w_bpp=inz_bezp).pbn_2017_2021 is None
    )


@pytest.mark.django_db
def test_fd608_sync_nie_kasuje_recznego_wpisu(pbn_client_trzy_slowniki):
    """Brak dopasowania w słowniku historycznym nie zeruje ręcznego wpisu."""
    pbn_client_trzy_slowniki.download_disciplines()
    inna = Dyscyplina_Naukowa.objects.create(kod="99.99", nazwa="nie ma w PBN")
    reczna = Discipline.objects.filter(
        parent_group=_grupa(date(2022, 11, 11))
    ).first()
    TlumaczDyscyplin.objects.create(dyscyplina_w_bpp=inna, pbn_2022_2023=reczna)

    pbn_client_trzy_slowniki._sync_discipline_translations()

    assert TlumaczDyscyplin.objects.get(dyscyplina_w_bpp=inna).pbn_2022_2023 == (
        reczna
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "dzien,od",
    [
        (date(2018, 1, 1), date(2018, 1, 1)),
        (date(2022, 11, 10), date(2018, 1, 1)),
        (date(2022, 11, 11), date(2022, 11, 11)),
        (date(2023, 10, 5), date(2022, 11, 11)),
        (date(2023, 10, 6), date(2023, 10, 6)),
        (date(2030, 1, 1), date(2023, 10, 6)),
    ],
)
def test_fd608_slownik_na_dzien_granice(pbn_client_trzy_slowniki, dzien, od):
    pbn_client_trzy_slowniki.download_disciplines()
    d = matchuj_dyscypline_pbn_na_dzien("5.1", "ekonomia i finanse", dzien)
    assert d.parent_group == _grupa(od)


@pytest.mark.django_db
def test_fd608_slownik_na_dzien_brak_slownika(pbn_client_trzy_slowniki):
    pbn_client_trzy_slowniki.download_disciplines()
    assert matchuj_dyscypline_pbn_na_dzien("5.1", "x", date(2010, 1, 1)) is None


# --- migracja danych 0081 ---------------------------------------------------

_migracja = importlib.import_module(
    "pbn_api.migrations.0081_uzupelnij_tlumacza_dyscyplin_fd608"
)


@pytest.mark.django_db
def test_fd608_migracja_uzupelnia_puste_i_zostawia_istniejace(
    pbn_client_trzy_slowniki,
):
    pbn_client_trzy_slowniki.download_disciplines()
    ekonomia = Dyscyplina_Naukowa.objects.create(kod="5.1", nazwa="ekonomia i finanse")
    stosunki = Dyscyplina_Naukowa.objects.create(
        kod="5.12", nazwa="stosunki międzynarodowe"
    )
    reczna = Discipline.objects.get(
        parent_group=_grupa(date(2023, 10, 6)), code="501"
    )
    # Stan jak na produkcji po imporcie: 2022-2023 puste.
    TlumaczDyscyplin.objects.create(dyscyplina_w_bpp=ekonomia, pbn_2024_now=reczna)
    TlumaczDyscyplin.objects.create(dyscyplina_w_bpp=stosunki)

    _migracja.uzupelnij_tlumacza(django_apps, None)
    _migracja.uzupelnij_tlumacza(django_apps, None)  # idempotentna

    td = TlumaczDyscyplin.objects.get(dyscyplina_w_bpp=ekonomia)
    assert td.pbn_2017_2021.parent_group == _grupa(date(2018, 1, 1))
    assert td.pbn_2022_2023.parent_group == _grupa(date(2022, 11, 11))
    assert td.pbn_2022_2023.code == "501"
    assert td.pbn_2024_now == reczna  # istniejący wpis nietknięty

    td = TlumaczDyscyplin.objects.get(dyscyplina_w_bpp=stosunki)
    assert td.pbn_2017_2021 is None  # brak w słowniku 2018
    assert td.pbn_2022_2023.code == "512"
    assert td.pbn_2024_now.parent_group == _grupa(date(2023, 10, 6))

    assert TlumaczDyscyplin.objects.przetlumacz_dyscypline(stosunki, 2023)


@pytest.mark.django_db
def test_fd608_migracja_bez_slownikow_nic_nie_robi():
    dyscyplina = Dyscyplina_Naukowa.objects.create(kod="5.1", nazwa="ekonomia")
    TlumaczDyscyplin.objects.create(dyscyplina_w_bpp=dyscyplina)

    _migracja.uzupelnij_tlumacza(django_apps, None)

    td = TlumaczDyscyplin.objects.get(dyscyplina_w_bpp=dyscyplina)
    assert td.pbn_2017_2021 is None
    assert td.pbn_2022_2023 is None
    assert td.pbn_2024_now is None
