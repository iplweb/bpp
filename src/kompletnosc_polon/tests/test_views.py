"""Testy warstwy prezentacji raportu kompletności danych POL-on.

Widoki są cienkie, ale niosą trzy rzeczy, których nie da się sprawdzić na
poziomie selektorów i które łatwo zepsuć po cichu:

1. **kontrolę dostępu** — to narzędzie redaktorskie, więc zalogowany autor
   *bez* uprawnień redaktorskich musi dostać odmowę (bazowy
   ``EwaluacjaRequiredMixin`` sam z siebie by go przepuścił);
2. **agregację po autorze** przez wszystkie cztery typy osiągnięć naraz;
3. **komunikaty stanów pustych** — pusta tabela bez kontekstu czyta się jak
   „wszystko w porządku”, co jest najgorszą możliwą odpowiedzią raportu.

Asercje sprawdzają TREŚĆ odpowiedzi, nie sam kod 200: szablon, który się
renderuje, ale niczego nie pokazuje, jest tak samo zepsuty jak wyjątek.
"""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker

from bpp.const import CHARAKTER_SLOTY_KSIAZKA, GR_WPROWADZANIE_DANYCH
from bpp.models.profile import BppUser
from ewaluacja_common.const import OKNO_EWALUACJI
from kompletnosc_polon.views import ListaKompletnosciView

from .test_selektory import (
    _artykul_z_autorem,
    _jednostka,
    _zwarte_z_autorem,
)

PIERWSZY_ROK, OSTATNI_ROK = OKNO_EWALUACJI

HASLO = "haslo-do-testow"


def _tresc(odpowiedz) -> str:
    return odpowiedz.content.decode("utf-8")


def _uzytkownik(nazwa, *, grupa=False, autor=None):
    user = baker.make(BppUser, username=nazwa, autor=autor)
    user.set_password(HASLO)
    if grupa:
        grupa_obiekt, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
        user.groups.add(grupa_obiekt)
    user.save()
    return user


def _zaloguj(client, user):
    assert client.login(username=user.username, password=HASLO)
    return client


def _zepsuj_doi(powiazanie):
    """Skasuj identyfikator cyfrowy rekordu — brak WYMAGANY (``*_DOI``)."""
    rekord = powiazanie.rekord
    rekord.doi = None
    rekord.www = ""
    rekord.public_www = ""
    rekord.save()
    return powiazanie


# --------------------------------------------------------------------------
# Kontrola dostępu
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_niezalogowany_jest_przekierowany_na_logowanie(client):
    odpowiedz = client.get(reverse("kompletnosc_polon:lista"))

    assert odpowiedz.status_code == 302


@pytest.mark.django_db
def test_uzytkownik_bez_uprawnien_dostaje_odmowe(client):
    _zaloguj(client, _uzytkownik("bez-uprawnien"))

    odpowiedz = client.get(reverse("kompletnosc_polon:lista"))

    assert odpowiedz.status_code == 403


@pytest.mark.django_db
def test_zalogowany_autor_bez_uprawnien_redaktorskich_dostaje_odmowe(client):
    """Kluczowe zawężenie wobec ``EwaluacjaRequiredMixin``.

    Bazowy mixin przepuszcza użytkownika powiązanego z autorem (widok „swoich”
    metryk). Raport kompletności pokazuje cudze rekordy i linkuje do panelu
    administracyjnego, więc dla takiego użytkownika musi być zamknięty.
    """
    autor = baker.make("bpp.Autor")
    _zaloguj(client, _uzytkownik("autor-bez-grupy", autor=autor))

    odpowiedz = client.get(reverse("kompletnosc_polon:lista"))

    assert odpowiedz.status_code == 403


@pytest.mark.django_db
def test_uzytkownik_z_grupa_wprowadzania_danych_wchodzi(client):
    _zaloguj(client, _uzytkownik("redaktor", grupa=True))

    odpowiedz = client.get(reverse("kompletnosc_polon:lista"))

    assert odpowiedz.status_code == 200


@pytest.mark.django_db
def test_superuser_wchodzi(admin_client):
    odpowiedz = admin_client.get(reverse("kompletnosc_polon:lista"))

    assert odpowiedz.status_code == 200


@pytest.mark.django_db
def test_szczegoly_tez_wymagaja_pelnych_uprawnien(client):
    autor = baker.make("bpp.Autor")
    _zaloguj(client, _uzytkownik("autor-bez-grupy", autor=autor))

    odpowiedz = client.get(
        reverse("kompletnosc_polon:szczegoly", kwargs={"autor_slug": autor.slug})
    )

    assert odpowiedz.status_code == 403


# --------------------------------------------------------------------------
# Widok zbiorczy: kto trafia na listę
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_autor_z_brakami_jest_na_liscie_a_kompletny_nie(admin_client):
    z_brakiem = _zepsuj_doi(_artykul_z_autorem())
    kompletny = _artykul_z_autorem()

    tresc = _tresc(admin_client.get(reverse("kompletnosc_polon:lista")))

    assert str(z_brakiem.autor) in tresc
    assert str(kompletny.autor) not in tresc, (
        "Autor bez żadnego braku nie ma czego robić w raporcie braków"
    )


@pytest.mark.django_db
def test_lista_zlicza_braki_z_wielu_typow_osiagniec_pod_jednym_autorem(admin_client):
    """Agregacja idzie po osobie, nie po typie publikacji.

    § 2 ust. 10 umieszcza osiągnięcia w wykazie *pracowników*, więc artykuł
    i monografia tego samego autora muszą zsumować się w jednym wierszu.
    """
    jednostka = _jednostka()
    artykul = _zepsuj_doi(_artykul_z_autorem(jednostka=jednostka))
    monografia = _zepsuj_doi(
        _zwarte_z_autorem(CHARAKTER_SLOTY_KSIAZKA, jednostka=jednostka)
    )

    odpowiedz = admin_client.get(reverse("kompletnosc_polon:lista"))
    wiersze = {wiersz["autor"].pk: wiersz for wiersz in odpowiedz.context["wiersze"]}

    assert set(wiersze) == {artykul.autor_id, monografia.autor_id}
    for wiersz in wiersze.values():
        assert wiersz["rekordow_z_brakami"] == 1
        assert wiersz["braki_wymagane"] >= 1


@pytest.mark.django_db
def test_lista_sortuje_malejaco_po_brakach_wymaganych(admin_client):
    jednostka = _jednostka()
    _zepsuj_doi(_artykul_z_autorem(jednostka=jednostka))

    # Drugi autor: brak DOI PLUS brak upoważnienia — dwa braki wymagane.
    gorszy = _zepsuj_doi(_artykul_z_autorem(jednostka=jednostka))
    gorszy.upowaznienie_pbn = False
    gorszy.save()

    wiersze = admin_client.get(reverse("kompletnosc_polon:lista")).context["wiersze"]

    assert [w["autor"].pk for w in wiersze][0] == gorszy.autor_id
    assert wiersze[0]["braki_wymagane"] > wiersze[1]["braki_wymagane"]


@pytest.mark.django_db
def test_lista_rozdziela_braki_wymagane_od_warunkowych(admin_client):
    """ORCID to wymóg warunkowy — nie może podbijać licznika krytycznego."""
    powiazanie = _artykul_z_autorem(orcid=False)

    (wiersz,) = admin_client.get(reverse("kompletnosc_polon:lista")).context["wiersze"]

    assert wiersz["autor"].pk == powiazanie.autor_id
    assert wiersz["braki_wymagane"] == 0
    assert wiersz["braki_warunkowe"] == 1


# --------------------------------------------------------------------------
# Widok zbiorczy: paginacja
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_lista_stronicuje_autorow(admin_client):
    """W realnej instalacji prawie każdy pracownik ma jakiś brak wymagany.

    Pola ``pbn_czy_*`` i ``opl_pub_*`` mają ``default=None``, a ``przypieta``
    domyślnie ``True``, więc bez paginacji tabela urosłaby do wiersza na
    każdego autora uczelni.
    """
    jednostka = _jednostka()
    ilu = ListaKompletnosciView.autorow_na_stronie + 3
    for _ in range(ilu):
        _zepsuj_doi(_artykul_z_autorem(jednostka=jednostka))

    odpowiedz = admin_client.get(reverse("kompletnosc_polon:lista"))

    assert odpowiedz.context["autorow"] == ilu
    assert odpowiedz.context["is_paginated"] is True
    assert len(odpowiedz.context["wiersze"]) == ListaKompletnosciView.autorow_na_stronie
    assert odpowiedz.context["paginator"].num_pages == 2

    druga = admin_client.get(reverse("kompletnosc_polon:lista"), {"page": 2})
    assert len(druga.context["wiersze"]) == 3
    assert druga.context["page_obj"].number == 2


@pytest.mark.django_db
def test_jedna_strona_nie_pokazuje_nawigacji(admin_client):
    _zepsuj_doi(_artykul_z_autorem())

    odpowiedz = admin_client.get(reverse("kompletnosc_polon:lista"))

    assert odpowiedz.context["is_paginated"] is False
    assert "pagination-next" not in _tresc(odpowiedz)


# --------------------------------------------------------------------------
# Widok zbiorczy: zawężenie do uczelni oglądającego (multi-tenant)
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_lista_pokazuje_wylacznie_autorow_uczelni_ogladajacego(admin_client):
    """Superuser wybiera uczelnię parametrem ``?uczelnia=`` (read-side).

    Przy dwóch uczelniach ``scope_autorzy_do_uczelni`` przestaje być no-opem,
    więc test faktycznie sprawdza izolację, a nie fast-track single-install.
    """
    nasza = baker.make("bpp.Uczelnia")
    obca = baker.make("bpp.Uczelnia")

    nasz = _zepsuj_doi(_artykul_z_autorem(uczelnia=nasza))
    obcy = _zepsuj_doi(_artykul_z_autorem(uczelnia=obca))

    odpowiedz = admin_client.get(
        reverse("kompletnosc_polon:lista"), {"uczelnia": nasza.pk}
    )
    tresc = _tresc(odpowiedz)

    assert [w["autor"].pk for w in odpowiedz.context["wiersze"]] == [nasz.autor_id]
    assert str(obcy.autor) not in tresc


@pytest.mark.django_db
def test_szczegoly_autora_z_obcej_uczelni_daja_404_a_nie_pusta_liste(admin_client):
    """Regresja wycieku: sam fakt istnienia pracownika jest daną chronioną.

    Widok zawężał wyłącznie *powiązania*, a autora wyciągał
    ``get_object_or_404(Autor, slug=…)`` z całej bazy. Slug jest przewidywalny
    („nazwisko-imie”), więc odpowiedź HTTP 200 z imieniem i nazwiskiem
    w ``<title>``, okruszkach i ``<h1>`` pozwalała enumerować kadrę OBCEJ
    uczelni. Pusta lista pozycji tego nie ratowała — nazwisko i tak wyciekało.
    """
    nasza = baker.make("bpp.Uczelnia")
    obca = baker.make("bpp.Uczelnia")

    obcy = _zepsuj_doi(_artykul_z_autorem(uczelnia=obca))

    odpowiedz = admin_client.get(
        reverse("kompletnosc_polon:szczegoly", kwargs={"autor_slug": obcy.autor.slug}),
        {"uczelnia": nasza.pk},
    )

    assert odpowiedz.status_code == 404
    assert str(obcy.autor) not in _tresc(odpowiedz)
    assert obcy.autor.nazwisko not in _tresc(odpowiedz)


@pytest.mark.django_db
def test_szczegoly_autora_wlasnej_uczelni_dzialaja_mimo_zawezenia(admin_client):
    """Zawężenie ma odsiewać obcych, a nie zamykać widok na własnych.

    Atrybucja ``scope_autor_do_uczelni`` idzie przez jednostkę autora
    (aktualną albo historyczną), więc test nadaje autorowi aktualną jednostkę
    naszej uczelni — tak jak wygląda to dla realnego pracownika.
    """
    nasza = baker.make("bpp.Uczelnia")
    baker.make("bpp.Uczelnia")

    jednostka = _jednostka(nasza)
    nasz = _zepsuj_doi(_artykul_z_autorem(jednostka=jednostka))
    nasz.autor.aktualna_jednostka = jednostka
    nasz.autor.save()

    odpowiedz = admin_client.get(
        reverse("kompletnosc_polon:szczegoly", kwargs={"autor_slug": nasz.autor.slug}),
        {"uczelnia": nasza.pk},
    )

    assert odpowiedz.status_code == 200
    assert [p["rekord"].pk for p in odpowiedz.context["pozycje"]] == [nasz.rekord_id]


# --------------------------------------------------------------------------
# Widok szczegółów
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_szczegoly_wypisuja_opis_i_paragraf_naruszonej_reguly(admin_client):
    powiazanie = _artykul_z_autorem()
    powiazanie.upowaznienie_pbn = False
    powiazanie.save()

    tresc = _tresc(
        admin_client.get(
            reverse(
                "kompletnosc_polon:szczegoly",
                kwargs={"autor_slug": powiazanie.autor.slug},
            )
        )
    )

    assert "ART_UPOWAZNIENIE" in tresc
    assert "Brak upoważnienia autora" in tresc
    assert "§ 2 ust. 10 pkt 4 lit. d" in tresc


@pytest.mark.django_db
def test_szczegoly_linkuja_do_formularza_edycji_w_adminie(admin_client):
    powiazanie = _zepsuj_doi(_artykul_z_autorem())
    oczekiwany = reverse(
        "admin:bpp_wydawnictwo_ciagle_change", args=[powiazanie.rekord_id]
    )

    tresc = _tresc(
        admin_client.get(
            reverse(
                "kompletnosc_polon:szczegoly",
                kwargs={"autor_slug": powiazanie.autor.slug},
            )
        )
    )

    assert oczekiwany in tresc
    assert powiazanie.rekord.tytul_oryginalny in tresc


@pytest.mark.django_db
def test_szczegoly_oddzielaja_braki_wymagane_od_warunkowych(admin_client):
    powiazanie = _zepsuj_doi(_artykul_z_autorem(orcid=False))

    odpowiedz = admin_client.get(
        reverse(
            "kompletnosc_polon:szczegoly",
            kwargs={"autor_slug": powiazanie.autor.slug},
        )
    )
    (pozycja,) = odpowiedz.context["pozycje"]

    assert [r.kod for r in pozycja["wymagane"]] == ["ART_DOI"]
    assert [r.kod for r in pozycja["warunkowe"]] == ["ART_ORCID"]

    tresc = _tresc(odpowiedz)
    assert "Braki wymagane" in tresc
    assert "Braki warunkowe (nieobowiązkowe)" in tresc


@pytest.mark.django_db
def test_szczegoly_nieznanego_autora_daja_404(admin_client):
    odpowiedz = admin_client.get(
        reverse("kompletnosc_polon:szczegoly", kwargs={"autor_slug": "nie-ma-takiego"})
    )

    assert odpowiedz.status_code == 404


# --------------------------------------------------------------------------
# Stany puste — komunikat zamiast pustej tabeli
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_pusta_baza_tlumaczy_ze_brakuje_przypietych_dyscyplin(admin_client):
    odpowiedz = admin_client.get(reverse("kompletnosc_polon:lista"))
    tresc = _tresc(odpowiedz)

    assert odpowiedz.context["brak_przypietych_dyscyplin"] is True
    assert "Raport nie ma czego sprawdzić" in tresc
    assert "przypiętą dyscyplinę" in tresc
    assert "nie znaczy, że dane są kompletne" in tresc


@pytest.mark.django_db
def test_komunikat_o_dyscyplinach_patrzy_tylko_na_wlasna_uczelnie(admin_client):
    """Boolean „są przypięte dyscypliny” nie może mówić o cudzych danych.

    Bez zawężenia redaktor uczelni, w której nikt nie przypiął dyscyplin,
    nie zobaczyłby wyjaśnienia — bo dyscypliny ma sąsiad. To i wprowadza go
    w błąd co do własnych danych, i wycieka jednym bitem stan obcej bazy.
    """
    nasza = baker.make("bpp.Uczelnia")
    obca = baker.make("bpp.Uczelnia")

    _artykul_z_autorem(uczelnia=obca)

    odpowiedz = admin_client.get(
        reverse("kompletnosc_polon:lista"), {"uczelnia": nasza.pk}
    )

    assert odpowiedz.context["sprawdzonych"] == 0
    assert odpowiedz.context["brak_przypietych_dyscyplin"] is True
    assert "Raport nie ma czego sprawdzić" in _tresc(odpowiedz)


@pytest.mark.django_db
def test_zero_brakow_daje_jawny_komunikat_z_liczba_i_zakresem_lat(admin_client):
    _artykul_z_autorem()

    odpowiedz = admin_client.get(reverse("kompletnosc_polon:lista"))
    tresc = _tresc(odpowiedz)

    assert odpowiedz.context["wiersze"] == []
    assert odpowiedz.context["sprawdzonych"] == 1
    assert odpowiedz.context["brak_przypietych_dyscyplin"] is False
    assert "Brak zastrzeżeń" in tresc
    assert f"{PIERWSZY_ROK}&ndash;{OSTATNI_ROK}" in tresc


@pytest.mark.django_db
def test_zakres_lat_jest_podany_takze_gdy_sa_braki(admin_client):
    _zepsuj_doi(_artykul_z_autorem())

    tresc = _tresc(admin_client.get(reverse("kompletnosc_polon:lista")))

    assert f"{PIERWSZY_ROK}&ndash;{OSTATNI_ROK}" in tresc


# --------------------------------------------------------------------------
# Nierozpoznany typ osiągnięcia — nie wolno mu zniknąć po cichu
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_lista_pokazuje_sekcje_nierozpoznanego_typu_osiagniecia(admin_client):
    nierozpoznane = _zwarte_z_autorem(None)

    odpowiedz = admin_client.get(reverse("kompletnosc_polon:lista"))
    tresc = _tresc(odpowiedz)

    assert [w["autor"].pk for w in odpowiedz.context["nierozpoznane"]] == [
        nierozpoznane.autor_id
    ]
    assert "Nierozpoznany typ osiągnięcia" in tresc
    assert "Raport ich nie sprawdził" in tresc
    assert str(nierozpoznane.autor) in tresc


@pytest.mark.django_db
def test_szczegoly_wypisuja_nierozpoznane_rekordy_autora(admin_client):
    nierozpoznane = _zwarte_z_autorem(None)
    oczekiwany = reverse(
        "admin:bpp_wydawnictwo_zwarte_change", args=[nierozpoznane.rekord_id]
    )

    odpowiedz = admin_client.get(
        reverse(
            "kompletnosc_polon:szczegoly",
            kwargs={"autor_slug": nierozpoznane.autor.slug},
        )
    )
    tresc = _tresc(odpowiedz)

    assert len(odpowiedz.context["nierozpoznane"]) == 1
    assert "Nierozpoznany typ osiągnięcia" in tresc
    assert oczekiwany in tresc


@pytest.mark.django_db
def test_artykul_bez_rodzaju_pbn_nie_znika_z_raportu_po_cichu(admin_client):
    """Artykuł, którego charakter nie ma ``rodzaj_pbn``, MUSI być widoczny.

    Bez tego użytkownik świeżej instalacji dostawał raport bez ani jednego
    artykułu i licznik „sprawdzono N powiązań”, który artykułów nie obejmował
    — czyli komunikat „artykuły są w porządku” o czymś, czego raport nawet
    nie obejrzał.
    """
    ciagle = _artykul_z_autorem(rodzaj_pbn=None)

    odpowiedz = admin_client.get(reverse("kompletnosc_polon:lista"))
    tresc = _tresc(odpowiedz)

    assert odpowiedz.context["sprawdzonych"] == 0
    assert [w["autor"].pk for w in odpowiedz.context["nierozpoznane"]] == [
        ciagle.autor_id
    ]
    assert "Nierozpoznany typ osiągnięcia" in tresc
    assert "Raport ich nie sprawdził" in tresc
    assert str(ciagle.autor) in tresc


@pytest.mark.django_db
def test_lista_laczy_nierozpoznane_zwarte_i_ciagle_w_jednej_sekcji(admin_client):
    zwarte = _zwarte_z_autorem(None)
    ciagle = _artykul_z_autorem(rodzaj_pbn=None)

    odpowiedz = admin_client.get(reverse("kompletnosc_polon:lista"))
    tresc = _tresc(odpowiedz)

    assert {w["autor"].pk for w in odpowiedz.context["nierozpoznane"]} == {
        zwarte.autor_id,
        ciagle.autor_id,
    }
    assert tresc.count("Nierozpoznany typ osiągnięcia") == 1, (
        "Sekcja ma być JEDNA, wspólna dla obu rodzajów wydawnictw"
    )
    assert str(zwarte.autor) in tresc
    assert str(ciagle.autor) in tresc


@pytest.mark.django_db
def test_szczegoly_wypisuja_nierozpoznane_obu_rodzajow(admin_client):
    """Sekcja szczegółów prowadzi do formularza edycji obu rodzajów rekordów."""
    przypadki = (
        (_zwarte_z_autorem(None), "admin:bpp_wydawnictwo_zwarte_change"),
        (_artykul_z_autorem(rodzaj_pbn=None), "admin:bpp_wydawnictwo_ciagle_change"),
    )

    for powiazanie, trasa_admina in przypadki:
        odpowiedz = admin_client.get(
            reverse(
                "kompletnosc_polon:szczegoly",
                kwargs={"autor_slug": powiazanie.autor.slug},
            )
        )
        tresc = _tresc(odpowiedz)

        assert len(odpowiedz.context["nierozpoznane"]) == 1
        assert "Nierozpoznany typ osiągnięcia" in tresc
        assert reverse(trasa_admina, args=[powiazanie.rekord_id]) in tresc


@pytest.mark.django_db
def test_komunikat_sekcji_nierozpoznanych_wskazuje_slownik_charakterow(admin_client):
    """Komunikat ma być prawdziwy dla OBU przypadków i wskazywać miejsce naprawy.

    Poprawka nie polega na edycji rekordu: dla zwartych trzeba ustawić
    „charakter dla slotów”, dla ciągłych „rodzaj dla PBN” — obie wartości
    siedzą w słowniku charakterów formalnych.
    """
    _artykul_z_autorem(rodzaj_pbn=None)

    tresc = _tresc(admin_client.get(reverse("kompletnosc_polon:lista")))

    assert "charakteru dla slotów" in tresc
    assert "rodzaju dla PBN" in tresc
    assert reverse("admin:bpp_charakter_formalny_changelist") in tresc
