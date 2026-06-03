"""Testy metody ``autorzy_dla_opisu_skrocony`` — skrócony widok listy
autorów na stronie rekordu (pierwszych N + nasi autorzy z pozycją)."""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor


def _browse_praca(client, wydawnictwo_ciagle):
    return client.get(
        reverse(
            "bpp:browse_praca",
            args=(
                ContentType.objects.get(
                    app_label="bpp", model="wydawnictwo_ciagle"
                ).pk,
                wydawnictwo_ciagle.pk,
            ),
        ),
        follow=True,
    )


def _dodaj_autorow(wydawnictwo_ciagle, jednostki):
    """Dodaje autorów do pracy; ``jednostki`` to lista jednostek (po jednej
    na autora), kolejność = indeks na liście."""
    for i, jednostka in enumerate(jednostki):
        autor = baker.make(Autor, nazwisko=f"Nazwisko{i:03d}", imiona="Imię")
        wydawnictwo_ciagle.dodaj_autora(
            autor,
            jednostka,
            zapisany_jako=f"Nazwisko{i:03d} Imię",
            kolejnosc=i,
            # autor w obcej jednostce nie może afiliować (walidacja modelu)
            afiliuje=jednostka.skupia_pracownikow,
        )


@pytest.mark.django_db
def test_skrocony_pierwszych_piec_plus_nasi(
    wydawnictwo_ciagle, jednostka, obca_jednostka
):
    # 30 autorów; nasi (jednostka skupiająca pracowników) na pozycjach 4 i 28
    jednostki = [obca_jednostka] * 30
    jednostki[3] = jednostka  # pozycja 4
    jednostki[27] = jednostka  # pozycja 28
    _dodaj_autorow(wydawnictwo_ciagle, jednostki)

    box = wydawnictwo_ciagle.autorzy_dla_opisu_skrocony()

    assert box["skrocony"] is True
    assert box["liczba"] == 30
    assert len(box["pierwsi"]) == 5

    # nasz autor wśród pierwszej piątki: pozycja 4, oflagowany, NIE dublowany
    assert box["pierwsi"][3].pozycja == 4
    assert box["pierwsi"][3].czy_nasz is True
    assert box["pierwsi"][0].czy_nasz is False

    # nasi spoza pierwszej piątki: tylko pozycja 28
    assert [a.pozycja for a in box["nasi_dalej"]] == [28]
    assert box["nasi_dalej"][0].czy_nasz is True


@pytest.mark.django_db
def test_ponizej_progu_nie_skraca(wydawnictwo_ciagle, obca_jednostka):
    _dodaj_autorow(wydawnictwo_ciagle, [obca_jednostka] * 10)

    box = wydawnictwo_ciagle.autorzy_dla_opisu_skrocony()

    assert box["skrocony"] is False
    assert box["liczba"] == 10


@pytest.mark.django_db
def test_brak_naszych_nasi_dalej_pusty(wydawnictwo_ciagle, obca_jednostka):
    _dodaj_autorow(wydawnictwo_ciagle, [obca_jednostka] * 30)

    box = wydawnictwo_ciagle.autorzy_dla_opisu_skrocony()

    assert box["skrocony"] is True
    assert box["nasi_dalej"] == []
    assert all(a.czy_nasz is False for a in box["pierwsi"])


@pytest.mark.django_db
def test_nasz_tylko_w_pierwszej_piatce(
    wydawnictwo_ciagle, jednostka, obca_jednostka
):
    jednostki = [obca_jednostka] * 30
    jednostki[2] = jednostka  # pozycja 3
    _dodaj_autorow(wydawnictwo_ciagle, jednostki)

    box = wydawnictwo_ciagle.autorzy_dla_opisu_skrocony()

    assert box["nasi_dalej"] == []
    assert box["pierwsi"][2].czy_nasz is True
    assert box["pierwsi"][2].pozycja == 3


@pytest.mark.django_db
def test_pozycja_jest_1_based_niezaleznie_od_kolejnosci(
    wydawnictwo_ciagle, obca_jednostka
):
    # nieciągłe wartości pola kolejnosc — pozycja ma być 1,2,3
    autorzy = []
    for i, kol in enumerate((0, 10, 20)):
        autor = baker.make(Autor, nazwisko=f"K{i}", imiona="I")
        wydawnictwo_ciagle.dodaj_autora(
            autor,
            obca_jednostka,
            zapisany_jako=f"K{i} I",
            kolejnosc=kol,
            afiliuje=False,
        )
        autorzy.append(autor)

    box = wydawnictwo_ciagle.autorzy_dla_opisu_skrocony()

    assert [a.pozycja for a in box["wszyscy"]] == [1, 2, 3]


@pytest.mark.django_db
def test_render_skrocony_na_stronie_rekordu(
    client, wydawnictwo_ciagle, jednostka, obca_jednostka, denorms
):
    jednostki = [obca_jednostka] * 30
    jednostki[3] = jednostka  # pozycja 4
    jednostki[27] = jednostka  # pozycja 28
    _dodaj_autorow(wydawnictwo_ciagle, jednostki)
    denorms.flush()

    res = _browse_praca(client, wydawnictwo_ciagle)
    assert res.status_code == 200
    tresc = res.content.decode("utf-8")

    # przycisk z liczbą autorów (renderowany tylko w widoku skróconym)
    assert "Pokaż wszystkich (30)" in tresc
    # div widoku skróconego (klasa renderowana tylko gdy skrocony)
    assert "praca-mono__authors-collapsed" in tresc
    # przycisk zwijania na pełnej liście (tylko gdy skrocony)
    assert "Zwiń listę autorów" in tresc
    assert "praca-mono__author-name--nasz" in tresc  # nasz autor podświetlony
    assert "(28.)" in tresc  # pozycja naszego autora spoza pierwszej piątki


@pytest.mark.django_db
def test_render_krotka_lista_bez_skracania(
    client, wydawnictwo_ciagle, obca_jednostka, denorms
):
    _dodaj_autorow(wydawnictwo_ciagle, [obca_jednostka] * 10)
    denorms.flush()

    res = _browse_praca(client, wydawnictwo_ciagle)
    assert res.status_code == 200
    tresc = res.content.decode("utf-8")

    assert "Pokaż wszystkich" not in tresc
    # div widoku skróconego nie powinien się wyrenderować
    assert "praca-mono__authors-collapsed" not in tresc


@pytest.mark.django_db
def test_render_doktorat_nie_wybucha(client, doktorat, denorms):
    # Praca_Doktorska dziedziczy autorzy_dla_opisu_skrocony, ale jej
    # autorzy_set to FakeSet z 1 (fałszywym) autorem — strona rekordu musi
    # się renderować bez błędu (regresja na ścieżce doktorat/habilitacja).
    denorms.flush()
    res = client.get(
        reverse(
            "bpp:browse_praca",
            args=(
                ContentType.objects.get(
                    app_label="bpp", model="praca_doktorska"
                ).pk,
                doktorat.pk,
            ),
        ),
        follow=True,
    )
    assert res.status_code == 200
    assert "Pokaż wszystkich" not in res.content.decode("utf-8")
