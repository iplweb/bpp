"""Stronicowanie listy „Problemy PBN” (komparator udziałów, FD#514)."""

from datetime import timedelta

import pytest
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from model_bakery import baker

from bpp.models import Uczelnia
from komparator_pbn_udzialy.models import BrakAutoraWPublikacji, RozbieznoscDyscyplinPBN
from komparator_pbn_udzialy.views import ProblemyPBNListView

URL = "/komparator-pbn-udzialy/2026-2030/"
NA_STRONE = ProblemyPBNListView.paginate_by


def _oswiadczenie(tytul, naukowiec=None, rok=2027):
    return baker.make(
        "pbn_api.OswiadczenieInstytucji",
        personId=naukowiec or baker.make("pbn_api.Scientist"),
        publicationId=baker.make("pbn_api.Publication", year=rok, title=tytul),
    )


def _brak_autora(nr, typ=BrakAutoraWPublikacji.TYP_BRAK_AUTORA_W_BPP):
    naukowiec = baker.make("pbn_api.Scientist", name="Jan", lastName=f"Brak{nr:03}")
    return BrakAutoraWPublikacji.objects.create(
        pbn_scientist=naukowiec,
        oswiadczenie_instytucji=_oswiadczenie(f"Praca brak {nr:03}", naukowiec),
        typ=typ,
        dyscyplina_pbn=baker.make("bpp.Dyscyplina_Naukowa"),
    )


def _rozbieznosc(nr, model="bpp.Wydawnictwo_Ciagle"):
    rekord = baker.make(model, tytul_oryginalny=f"Praca rozb {nr:03}", rok=2027)
    # Jednostka jednej, wspólnej uczelni: bez tego ``baker`` zakłada do
    # każdej jednostki nową uczelnię, a w instalacji wielouczelnianej lista
    # pokazuje tylko oświadczenia bieżącej uczelni.
    uczelnia = Uczelnia.objects.first() or baker.make(Uczelnia)
    wa = baker.make(
        f"{model}_Autor",
        rekord=rekord,
        jednostka=baker.make("bpp.Jednostka", uczelnia=uczelnia),
        autor=baker.make(
            "bpp.Autor", nazwisko=f"Rozb{nr:03}", tytul=baker.make("bpp.Tytul")
        ),
    )
    return RozbieznoscDyscyplinPBN.objects.create(
        content_type=ContentType.objects.get_for_model(wa),
        object_id=wa.pk,
        oswiadczenie_instytucji=_oswiadczenie(f"Praca rozb {nr:03}"),
        dyscyplina_bpp=baker.make("bpp.Dyscyplina_Naukowa"),
        dyscyplina_pbn=baker.make("bpp.Dyscyplina_Naukowa"),
    )


def _postarz(obj, minuty):
    """Ustaw datę wykrycia ``minuty`` temu (``created_at`` jest auto)."""
    type(obj).objects.filter(pk=obj.pk).update(
        created_at=timezone.now() - timedelta(minutes=minuty)
    )


@pytest.fixture
def duzo_problemow(db):
    """``NA_STRONE + 10`` problemów obu rodzajów (na przemian), coraz starszych:
    nr 0 najnowszy."""
    problemy = []
    for nr in range(NA_STRONE + 10):
        if nr % 2:
            obj = _rozbieznosc(
                nr,
                "bpp.Wydawnictwo_Zwarte" if nr % 4 == 1 else "bpp.Wydawnictwo_Ciagle",
            )
        else:
            obj = _brak_autora(nr)
        _postarz(obj, nr)
        problemy.append(obj)
    return problemy


def _obiekty(response):
    return [p.obj for p in response.context["problemy"]]


def test_lista_jest_stronicowana_najnowsze_pierwsze(client_with_group, duzo_problemow):
    """Pierwsza strona: ``NA_STRONE`` najnowszych problemów obu rodzajów
    w kolejności od najnowszego; druga: reszta. Nic nie ginie ani się nie
    powtarza."""
    pierwsza = client_with_group.get(URL)
    druga = client_with_group.get(URL, {"page": 2})

    assert _obiekty(pierwsza) == duzo_problemow[:NA_STRONE]
    assert _obiekty(druga) == duzo_problemow[NA_STRONE:]
    assert pierwsza.context["paginator"].count == NA_STRONE + 10
    assert pierwsza.context["is_paginated"] is True
    tresc = pierwsza.content.decode()
    assert 'class="pagination' in tresc
    assert f"Znaleziono: <strong>{NA_STRONE + 10}</strong>" in tresc


def test_linki_stron_zachowuja_filtry(client_with_group, duzo_problemow):
    response = client_with_group.get(
        URL, {"search": "Praca", "rok_min": 2026, "rok_max": 2030}
    )

    tresc = response.content.decode()
    assert "search=Praca" in tresc and "page=2" in tresc
    assert "rok_min=2026" in tresc


def test_numer_strony_spoza_zakresu_nie_daje_bledu(client_with_group, duzo_problemow):
    """Zły numer strony (np. po zawężeniu filtrów) pokazuje ostatnią/pierwszą
    stronę zamiast błędu."""
    assert len(_obiekty(client_with_group.get(URL, {"page": 99}))) == 10
    assert len(_obiekty(client_with_group.get(URL, {"page": "x"}))) == NA_STRONE


def test_statystyki_i_szukaj_obejmuja_caly_zakres_nie_strone(
    client_with_group, duzo_problemow
):
    """Kafelki liczą wszystkie problemy z zakresu lat, a „Szukaj” znajduje
    rekord, który bez wyszukiwania jest dopiero na drugiej stronie."""
    response = client_with_group.get(URL, {"page": 2})
    assert response.context["total_count"] == NA_STRONE + 10
    assert response.context["brakujacy_total"] == (NA_STRONE + 10) // 2
    assert response.context["rozbieznosci_total"] == (NA_STRONE + 10) // 2

    ostatni = NA_STRONE + 8  # parzysty: brak autora, na drugiej stronie
    response = client_with_group.get(URL, {"search": f"Praca brak {ostatni:03}"})
    assert _obiekty(response) == [duzo_problemow[ostatni]]
    assert response.context["total_count"] == NA_STRONE + 10


def test_filtr_typu_dziala_w_bazie(client_with_group, duzo_problemow):
    """Strażnik: filtr typu nadal rozdziela rozbieżności i brakujących."""
    response = client_with_group.get(URL, {"filter": "both_present"})
    assert response.context["paginator"].count == (NA_STRONE + 10) // 2
    assert all(p.is_discrepancy for p in response.context["problemy"])

    response = client_with_group.get(
        URL, {"filter": BrakAutoraWPublikacji.TYP_BRAK_AUTORA_W_BPP}
    )
    assert response.context["paginator"].count == (NA_STRONE + 10) // 2
    assert not any(p.is_discrepancy for p in response.context["problemy"])


def test_liczba_zapytan_nie_rosnie_z_liczba_wierszy(
    client_with_group, duzo_problemow, django_assert_max_num_queries
):
    """Pełna strona (50 wierszy obu rodzajów, prace ciągłe i zwarte) to stała
    liczba zapytań — bez zapytań na wiersz."""
    client_with_group.get(URL)  # rozgrzanie cache (ContentType, uczelnia itd.)

    # Zmierzone: 41, z czego ~32 to obudowa strony (sesja, menu, pasek…),
    # a 9 to lista: liczba uczelni, liczba wyników, 2× statystyki, klucze
    # strony, po jednym zapytaniu na tabelę problemów i na typ pracy.
    # Zapytanie na wiersz dałoby tu co najmniej 50 więcej.
    with django_assert_max_num_queries(45):
        response = client_with_group.get(URL)

    assert len(response.context["problemy"]) == NA_STRONE
    tresc = response.content.decode()
    assert "Rozb001" in tresc and "Jan Brak000 [PBN]" in tresc
