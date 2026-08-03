"""Testy liczników importu POLON pokazywanych na liście ``/import_polon/dane/``.

Liczniki powstają w locie, w pętli importu, bo część z nich NIE JEST odtwarzalna
z bazy po fakcie: wiersze z niedopasowanym autorem przy
``ukryj_niezmatchowanych_autorow`` nie trafiają do ``WierszImportuPlikuPolon``
w ogóle (pilnuje tego ``test_ukryci_niedopasowani_nie_trafiaja_do_bazy``).
"""

import pandas as pd
import pytest
from django.contrib.auth.models import Group
from django.core.files import File
from django.urls import reverse
from django.utils import timezone
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor
from import_polon.core.import_polon import (
    KLUCZE_PARTYCJI,
    KOMUNIKAT_BEZ_ZMIAN,
    KOMUNIKAT_BEZ_ZMIAN_BRAK_DYSCYPLIN,
    analyze_file_import_polon,
)
from import_polon.models import ImportPlikuPolon, WierszImportuPlikuPolon


def _wiersz(uczelnia, **nadpisania):
    """Minimalny wiersz POLON przechodzący walidację dla danej uczelni.

    Bez dyscyplin (``OSWIADCZENIE_* = nie``), więc dopasowany autor wpada w
    gałąź „brak danych o dyscyplinach" — czyli w komunikat bez zmian z sufiksem.
    """
    dane = {
        "IMIE": "Jan",
        "NAZWISKO": "Kowalski",
        "ZATRUDNIENIE": f"{uczelnia.nazwa} (Nauczyciel akademicki)",
        "ORCID": "",
        "OSWIADCZENIE_N": "nie",
        "OSWIADCZENIE_O_DYSCYPLINACH": "nie",
        "WIELKOSC_ETATU_PREZENTACJA_DZIESIETNA": "1.0",
    }
    dane.update(nadpisania)
    return dane


def _uruchom(tmp_path, wiersze, **kwargs_importu):
    """Zapisuje wiersze do xlsx-a i puszcza import. Zwraca (import, statystyki)."""
    plik = tmp_path / "polon.xlsx"
    pd.DataFrame(wiersze).to_excel(plik, index=False)

    kwargs_importu.setdefault("zapisz_zmiany_do_bazy", False)
    imp = baker.make(ImportPlikuPolon, rok=2023, **kwargs_importu)
    with open(plik, "rb") as f:
        imp.plik.save("polon.xlsx", File(f))

    wynik = analyze_file_import_polon(str(plik), imp, MockProgress(imp))
    return imp, wynik["statystyki"]


@pytest.mark.django_db
def test_partycja_sie_domyka(tmp_path, uczelnia):
    """Suma sześciu koszyków == liczba wierszy pliku.

    To asercja strukturalna, nie kosmetyczna: gdy ktoś doda w pętli kolejną
    gałąź ``continue`` bez inkrementacji licznika, wiersze przestaną się
    bilansować i ten test zapali się na czerwono.
    """
    wiersze = [
        _wiersz(uczelnia),  # autor niedopasowany → ukryty
        _wiersz(uczelnia, ZATRUDNIENIE="Zupełnie Inna Uczelnia"),  # odrzucony
    ]
    _, statystyki = _uruchom(tmp_path, wiersze)

    assert statystyki["wierszy_w_pliku"] == 2
    assert sum(statystyki[k] or 0 for k in KLUCZE_PARTYCJI) == 2


@pytest.mark.django_db
def test_odrzucenie_zatrudnienia_nie_jest_bledem(tmp_path, uczelnia):
    """Wiersz obcej uczelni to nie „błąd importu" — to wiersz spoza zakresu."""
    _, statystyki = _uruchom(
        tmp_path, [_wiersz(uczelnia, ZATRUDNIENIE="Zupełnie Inna Uczelnia")]
    )

    assert statystyki["odrzuconych_zatrudnienie"] == 1
    assert statystyki["z_bledem"] == 0
    assert statystyki["dopasowanych"] == 0


@pytest.mark.django_db
def test_ignoruj_miejsce_pracy_daje_none_a_nie_zero(tmp_path, uczelnia):
    """Wyłączona walidacja to „nie mierzono", nie „nikt nie odpadł"."""
    _, statystyki = _uruchom(
        tmp_path,
        [_wiersz(uczelnia, ZATRUDNIENIE="Zupełnie Inna Uczelnia")],
        ignoruj_miejsce_pracy=True,
    )

    assert statystyki["odrzuconych_zatrudnienie"] is None


@pytest.mark.django_db
def test_ukryci_niedopasowani_nie_trafiaja_do_bazy(tmp_path, uczelnia):
    """Uzasadnienie całego projektu: tych wierszy NIE DA SIĘ policzyć po fakcie."""
    imp, statystyki = _uruchom(tmp_path, [_wiersz(uczelnia)])

    assert statystyki["wierszy_w_pliku"] == 1
    assert statystyki["ukrytych_niedopasowanych"] == 1
    assert WierszImportuPlikuPolon.objects.filter(parent=imp).count() == 0


@pytest.mark.django_db
def test_brak_dyscyplin_liczy_sie_jako_bez_zmian(tmp_path, uczelnia):
    """REGRESJA: sentinel ma wariant z sufiksem.

    ``"W BPP jest identycznie jak w XLSX (brak danych o dyscyplinach)."`` też
    znaczy „nic się nie zmieniło". Porównanie ``op != KOMUNIKAT_BEZ_ZMIAN``
    policzyłoby ten wiersz jako zmianę i zawyżało metrykę przy każdym imporcie.
    """
    baker.make(Autor, imiona="Jan", nazwisko="Kowalski")

    imp, statystyki = _uruchom(
        tmp_path, [_wiersz(uczelnia)], ukryj_niezmatchowanych_autorow=False
    )

    wiersz = WierszImportuPlikuPolon.objects.get(parent=imp)
    assert wiersz.rezultat == KOMUNIKAT_BEZ_ZMIAN_BRAK_DYSCYPLIN
    assert statystyki["bez_zmian"] == 1
    assert statystyki["ze_zmianami"] == 0
    assert statystyki["dopasowanych"] == 1


@pytest.mark.django_db
def test_sam_orcid_liczy_sie_jako_zmiana(tmp_path, uczelnia):
    """REGRESJA: operacja ORCID jest doklejana PO sentinelu.

    ``rezultat`` takiego wiersza zaczyna się od „W BPP jest identycznie…",
    choć autorowi realnie ustawiono ORCID. Klasyfikowanie po sklejonym tekście
    (``startswith``) zgubiłoby tę zmianę — dlatego liczymy po strukturze ``ops``.
    """
    baker.make(Autor, imiona="Jan", nazwisko="Kowalski", orcid=None)

    imp, statystyki = _uruchom(
        tmp_path,
        [_wiersz(uczelnia, ORCID="0000-0002-1825-0097")],
        ukryj_niezmatchowanych_autorow=False,
    )

    wiersz = WierszImportuPlikuPolon.objects.get(parent=imp)
    assert wiersz.rezultat.startswith(KOMUNIKAT_BEZ_ZMIAN), (
        "warunek wstępny testu: bez tego test nie pilnuje opisanej pułapki"
    )
    assert statystyki["ze_zmianami"] == 1
    assert statystyki["bez_zmian"] == 0


@pytest.mark.django_db
def test_dopasowany_z_bledem_wchodzi_do_obu_licznikow(tmp_path, uczelnia):
    """``dopasowanych`` jest ORTOGONALNY do partycji — kolumny się nie sumują."""
    baker.make(Autor, imiona="Jan", nazwisko="Kowalski")

    _, statystyki = _uruchom(
        tmp_path,
        [_wiersz(uczelnia, WIELKOSC_ETATU_PREZENTACJA_DZIESIETNA=None)],
        ukryj_niezmatchowanych_autorow=False,
    )

    assert statystyki["dopasowanych"] == 1
    assert statystyki["z_bledem"] == 1
    assert statystyki["ze_zmianami"] == 0


@pytest.mark.django_db
def test_pusty_plik_daje_same_zera(tmp_path, uczelnia):
    plik = tmp_path / "pusty.xlsx"
    pd.DataFrame(columns=list(_wiersz(uczelnia).keys())).to_excel(plik, index=False)

    imp = baker.make(ImportPlikuPolon, rok=2023, zapisz_zmiany_do_bazy=False)
    wynik = analyze_file_import_polon(str(plik), imp, MockProgress(imp))
    statystyki = wynik["statystyki"]

    assert statystyki["wierszy_w_pliku"] == 0
    assert all(statystyki[k] == 0 for k in KLUCZE_PARTYCJI)
    assert statystyki["do_odpiecia"] == 0


@pytest.mark.django_db
def test_nieczytelny_plik_nie_zostawia_statystyk(tmp_path, uczelnia):
    """Wyjątek leci PRZED pętlą, więc ``p.result`` się nie woła — lista pokaże „—"."""
    plik = tmp_path / "zly.txt"
    plik.write_text("to nie jest arkusz")

    imp = baker.make(ImportPlikuPolon, rok=2023, zapisz_zmiany_do_bazy=False)

    with pytest.raises(ValueError):
        analyze_file_import_polon(str(plik), imp, MockProgress(imp))

    assert imp.statystyki is None


# --- lista importów: renderowanie tabeli -------------------------------------

NAZWA_POLON = (
    "protected/import_polon/rozszerzone_zestawienie_pracownikow_podmiotu_"
    "na_dzien_wygenerowania_raportu_2026-01-15.xlsx"
)


@pytest.fixture
def klient_wprowadzajacy(client, django_user_model):
    """Zalogowany użytkownik w grupie wymaganej przez ``PokazImporty``."""
    user = django_user_model.objects.create_user(username="wprowadzajacy", password="x")
    user.groups.add(Group.objects.get_or_create(name="wprowadzanie danych")[0])
    client.force_login(user)
    return client, user


def _import_na_liscie(owner, statystyki=None, **nadpisania):
    kontekst = None if statystyki is None else {"total": 1, "statystyki": statystyki}
    # ``finished_on`` OBOWIĄZKOWE: badge statusu kluczuje po nim, a nie po
    # ``finished_successfully``. Liveops zawsze ustawia oba naraz — samo
    # ``finished_successfully=True`` dałoby nierealny obiekt „ukończony, ale
    # bez daty ukończenia" i test renderowałby badge „w trakcie".
    nadpisania.setdefault("finished_on", timezone.now())
    nadpisania.setdefault("finished_successfully", True)
    return baker.make(
        ImportPlikuPolon,
        owner=owner,
        rok=2023,
        plik=NAZWA_POLON,
        result_context=kontekst,
        **nadpisania,
    )


@pytest.mark.django_db
def test_lista_pokazuje_statystyki(klient_wprowadzajacy):
    client, user = klient_wprowadzajacy
    _import_na_liscie(
        user,
        {
            "wierszy_w_pliku": 41,
            "odrzuconych_zatrudnienie": 4,
            "odrzuconych_obca_uczelnia": 0,
            "ukrytych_niedopasowanych": 0,
            "z_bledem": 7,
            "ze_zmianami": 13,
            "bez_zmian": 17,
            "dopasowanych": 37,
            "do_odpiecia": 5,
        },
    )

    tresc = client.get(reverse("import_polon:index")).content.decode()

    assert ">41<" in tresc, "liczba wierszy w pliku"
    assert ">37<" in tresc, "dopasowanych"
    assert ">13<" in tresc, "ze zmianami"
    assert ">5<" in tresc, "do odpięcia"
    # z_uczelni jest pochodną: 41 − 4
    assert ">37<" in tresc


@pytest.mark.django_db
def test_lista_bez_statystyk_nie_sypie(klient_wprowadzajacy):
    """Import sprzed wprowadzenia statystyk — tabela ma się wyrenderować."""
    client, user = klient_wprowadzajacy
    _import_na_liscie(user, statystyki=None)

    response = client.get(reverse("import_polon:index"))

    assert response.status_code == 200
    assert "brak statystyk" in response.content.decode()


@pytest.mark.django_db
def test_lista_skraca_nazwe_pliku_zachowujac_pelna_w_tytule(klient_wprowadzajacy):
    client, user = klient_wprowadzajacy
    _import_na_liscie(user, statystyki=None)

    tresc = client.get(reverse("import_polon:index")).content.decode()

    assert "protected/import_polon" not in tresc.split('title="')[0]
    assert f'title="{NAZWA_POLON}"' in tresc, "pełna ścieżka zostaje w tooltipie"
    assert "…" in tresc, "nazwa skrócona wielokropkiem"


@pytest.mark.django_db
def test_lista_pokazuje_nd_gdy_walidacja_wylaczona(klient_wprowadzajacy):
    client, user = klient_wprowadzajacy
    _import_na_liscie(
        user,
        {
            "wierszy_w_pliku": 41,
            "odrzuconych_zatrudnienie": None,
            "odrzuconych_obca_uczelnia": 0,
            "ukrytych_niedopasowanych": 4,
            "z_bledem": 0,
            "ze_zmianami": 20,
            "bez_zmian": 17,
            "dopasowanych": 37,
            "do_odpiecia": 5,
        },
    )

    tresc = client.get(reverse("import_polon:index")).content.decode()

    # ">n/d<" celuje w KOMÓRKĘ; samo "n/d" trafiłoby też w tooltip nagłówka.
    assert ">n/d<" in tresc


@pytest.mark.django_db
def test_lista_pokazuje_zero_a_nie_nd(klient_wprowadzajacy):
    """``default_if_none``, nie ``default`` — zero to pomiar, nie brak danych."""
    client, user = klient_wprowadzajacy
    _import_na_liscie(
        user,
        {
            "wierszy_w_pliku": 41,
            "odrzuconych_zatrudnienie": 41,
            "odrzuconych_obca_uczelnia": 0,
            "ukrytych_niedopasowanych": 0,
            "z_bledem": 0,
            "ze_zmianami": 0,
            "bez_zmian": 0,
            "dopasowanych": 0,
            "do_odpiecia": 5,
        },
    )

    tresc = client.get(reverse("import_polon:index")).content.decode()

    assert ">n/d<" not in tresc, "z_uczelni == 0 musi się pokazać jako 0"
    assert ">0<" in tresc


@pytest.mark.django_db
@pytest.mark.parametrize(
    "pola,oczekiwany_badge",
    [
        ({"finished_on": None, "finished_successfully": False}, "w trakcie"),
        ({"finished_successfully": True}, "pomyślnie"),
        ({"finished_successfully": False}, "błąd"),
    ],
)
def test_lista_pokazuje_badge_statusu(klient_wprowadzajacy, pola, oczekiwany_badge):
    """Badge kluczuje po ``finished_on``, nie po ``finished_successfully``.

    Bez ``finished_on`` operacja jest „w trakcie" — nawet gdy flaga sukcesu
    jest podniesiona. Ten test pilnuje obu wymiarów naraz.
    """
    client, user = klient_wprowadzajacy
    _import_na_liscie(user, statystyki=None, **pola)

    tresc = client.get(reverse("import_polon:index")).content.decode()

    assert oczekiwany_badge in tresc


@pytest.mark.django_db
@pytest.mark.parametrize(
    "zapisz,oczekiwany_tryb",
    [(True, "zapisany do bazy"), (False, "podgląd")],
)
def test_lista_pokazuje_tryb_importu(klient_wprowadzajacy, zapisz, oczekiwany_tryb):
    """Tryb rozstrzyga, czy „zmian" znaczy „wprowadzono", czy „wprowadzono by"."""
    client, user = klient_wprowadzajacy
    _import_na_liscie(user, statystyki=None, zapisz_zmiany_do_bazy=zapisz)

    assert oczekiwany_tryb in client.get(reverse("import_polon:index")).content.decode()
