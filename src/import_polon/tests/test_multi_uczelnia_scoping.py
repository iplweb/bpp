"""Testy zawężenia importu POLON do bieżącej uczelni (multi-hosted).

W instalacji multi-hosted wiele uczelni współistnieje w jednej bazie. Import
POLON dla uczelni X nie może „widzieć" ani dotykać autorów uczelni Y:

- Finding 1: raport „autorzy z dyscyplinami, których nie było w pliku"
  (``ImportPlikuPolon.autorzy_niezmatchowani``) musi pokazywać wyłącznie
  aktualnie zatrudnionych w uczelni importu.
- Finding 2: walidacja pola ZATRUDNIENIE musi sprawdzać nazwę uczelni importu,
  nie dowolnej uczelni w systemie.
- Finding 3: import nie może modyfikować danych autora zatrudnionego w innej
  uczelni (mutacja cudzych danych).
"""

import pandas as pd
import pytest
from model_bakery import baker

from bpp.models import Autor, Jednostka, Uczelnia, Wydzial
from bpp.models.struktura_konwersja import znajdz_lub_utworz_wezel_wydzialu
from import_polon.core import analyze_file_import_polon
from import_polon.models import ImportPlikuPolon

ROK = 2020


def _autor_zatrudniony(uczelnia, nazwisko, imiona="Jan"):
    """Autor aktualnie zatrudniony w ``uczelnia`` (realna jednostka)."""
    wydzial = baker.make(Wydzial, uczelnia=uczelnia)
    jednostka = baker.make(
        Jednostka,
        uczelnia=uczelnia,
        parent=znajdz_lub_utworz_wezel_wydzialu(wydzial)[0],
        skupia_pracownikow=True,
    )
    return baker.make(
        Autor, nazwisko=nazwisko, imiona=imiona, aktualna_jednostka=jednostka
    )


# --- Finding 1: raport niezmatchowanych zawężony do uczelni importu ---------


@pytest.mark.django_db
def test_autorzy_niezmatchowani_zawezeni_do_uczelni_importu(
    rodzaj_autora_n, dyscyplina1
):
    uczelnia_x = baker.make(Uczelnia, nazwa="Uczelnia X", skrot="UX")
    uczelnia_y = baker.make(Uczelnia, nazwa="Uczelnia Y", skrot="UY")

    autor_x = _autor_zatrudniony(uczelnia_x, "IksinskiX")
    autor_x.autor_dyscyplina_set.create(
        rok=ROK, dyscyplina_naukowa=dyscyplina1, rodzaj_autora=rodzaj_autora_n
    )

    autor_y = _autor_zatrudniony(uczelnia_y, "IgrekY")
    autor_y.autor_dyscyplina_set.create(
        rok=ROK, dyscyplina_naukowa=dyscyplina1, rodzaj_autora=rodzaj_autora_n
    )

    import_object = baker.make(ImportPlikuPolon, rok=ROK, uczelnia=uczelnia_x)

    autor_ids = {ad.autor_id for ad in import_object.autorzy_niezmatchowani()}

    assert autor_x.pk in autor_ids, "autor uczelni importu musi być na liście"
    assert autor_y.pk not in autor_ids, (
        "autor INNEJ uczelni nie może wyciekać do raportu niezmatchowanych"
    )


@pytest.mark.django_db
def test_autorzy_niezmatchowani_bez_uczelni_bez_zawezenia(rodzaj_autora_n, dyscyplina1):
    """uczelnia=None (stare importy / brak rozstrzygnięcia) → zgodność wstecz:
    bez zawężenia, wszyscy z dyscypliną dla roku."""
    uczelnia_x = baker.make(Uczelnia, nazwa="Uczelnia X", skrot="UX")
    uczelnia_y = baker.make(Uczelnia, nazwa="Uczelnia Y", skrot="UY")

    autor_x = _autor_zatrudniony(uczelnia_x, "IksinskiX")
    autor_x.autor_dyscyplina_set.create(
        rok=ROK, dyscyplina_naukowa=dyscyplina1, rodzaj_autora=rodzaj_autora_n
    )
    autor_y = _autor_zatrudniony(uczelnia_y, "IgrekY")
    autor_y.autor_dyscyplina_set.create(
        rok=ROK, dyscyplina_naukowa=dyscyplina1, rodzaj_autora=rodzaj_autora_n
    )

    import_object = baker.make(ImportPlikuPolon, rok=ROK, uczelnia=None)

    autor_ids = {ad.autor_id for ad in import_object.autorzy_niezmatchowani()}

    assert autor_x.pk in autor_ids
    assert autor_y.pk in autor_ids


# --- Finding 2: walidacja ZATRUDNIENIE zawężona do nazwy uczelni importu -----


@pytest.mark.django_db
def test_walidacja_zatrudnienia_zawezona_do_uczelni_importu(tmp_path):
    uczelnia_x = baker.make(Uczelnia, nazwa="Uniwersytet X", skrot="UX")
    baker.make(Uczelnia, nazwa="Uniwersytet Y", skrot="UY")

    test_data = {
        "IMIE": ["Jan", "Anna"],
        "NAZWISKO": ["Iksinski", "Igrekowa"],
        "ZATRUDNIENIE": [
            "Uniwersytet X (Pracownik badawczo-dydaktyczny)",
            "Uniwersytet Y (Pracownik badawczo-dydaktyczny)",
        ],
        "ORCID": ["", ""],
        "OSWIADCZENIE_N": ["nie", "nie"],
        "OSWIADCZENIE_O_DYSCYPLINACH": ["nie", "nie"],
    }
    test_file = tmp_path / "z.xlsx"
    pd.DataFrame(test_data).to_excel(test_file, index=False)

    import_model = baker.make(
        ImportPlikuPolon,
        rok=2023,
        uczelnia=uczelnia_x,
        zapisz_zmiany_do_bazy=False,
        ukryj_niezmatchowanych_autorow=False,
    )
    analyze_file_import_polon(str(test_file), import_model)

    wiersze = {w.dane_z_xls["NAZWISKO"]: w for w in import_model.get_details_set()}
    assert "REKORD ZIGNOROWANY" not in wiersze["Iksinski"].rezultat, (
        "wiersz pracownika uczelni importu nie może być ignorowany"
    )
    assert "REKORD ZIGNOROWANY" in wiersze["Igrekowa"].rezultat, (
        "wiersz pracownika INNEJ uczelni musi zostać zignorowany"
    )


# --- Finding 3: import nie modyfikuje danych autora innej uczelni -----------


@pytest.mark.django_db
def test_import_nie_modyfikuje_autora_innej_uczelni(tmp_path):
    uczelnia_x = baker.make(Uczelnia, nazwa="Uniwersytet X", skrot="UX")
    uczelnia_y = baker.make(Uczelnia, nazwa="Uniwersytet Y", skrot="UY")

    _autor_zatrudniony(uczelnia_x, "Iksinski", imiona="Jan")
    autor_y = _autor_zatrudniony(uczelnia_y, "Igrekowa", imiona="Anna")

    # ignoruj_miejsce_pracy=True → walidacja ZATRUDNIENIE (Finding 2) NIE
    # filtruje; to guard po dopasowaniu autora (Finding 3) musi zatrzymać zapis
    # na autorze obcej uczelni.
    test_data = {
        "IMIE": ["Jan", "Anna"],
        "DRUGIE": ["", ""],
        "NAZWISKO": ["Iksinski", "Igrekowa"],
        "ZATRUDNIENIE": ["", ""],
        "ORCID": ["", ""],
        "OSWIADCZENIE_N": ["nie", "nie"],
        "OSWIADCZENIE_O_DYSCYPLINACH": ["nie", "nie"],
        "WIELKOSC_ETATU_PREZENTACJA_DZIESIETNA": ["1.0", "1.0"],
        "GRUPA_STANOWISK": ["", ""],
    }
    test_file = tmp_path / "z.xlsx"
    pd.DataFrame(test_data).to_excel(test_file, index=False)

    import_model = baker.make(
        ImportPlikuPolon,
        rok=ROK,
        uczelnia=uczelnia_x,
        zapisz_zmiany_do_bazy=True,
        ignoruj_miejsce_pracy=True,
        ukryj_niezmatchowanych_autorow=False,
    )
    analyze_file_import_polon(str(test_file), import_model)

    wiersze = {w.dane_z_xls["NAZWISKO"]: w for w in import_model.get_details_set()}
    assert "innej uczelni" in wiersze["Igrekowa"].rezultat.lower(), (
        "autor obcej uczelni musi być oznaczony jako pominięty"
    )
    assert "innej uczelni" not in wiersze["Iksinski"].rezultat.lower(), (
        "autor uczelni importu nie może być traktowany jako obcy"
    )
    assert not autor_y.autor_dyscyplina_set.filter(rok=ROK).exists(), (
        "import nie może utworzyć/zmienić Autor_Dyscyplina autora obcej uczelni"
    )


# --- Wiring: widok tworzący przypina uczelnię z requestu --------------------


@pytest.mark.django_db
def test_widok_tworzacy_przypina_uczelnie_z_requestu(
    uczelnia, fn_test_import_polon, client, django_user_model
):
    """POST na formularz nowego importu (host=testserver → Site → uczelnia)
    zapisuje ImportPlikuPolon z ustawioną ``uczelnia`` z requestu."""
    from django.contrib.auth.models import Group
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.urls import reverse

    user = django_user_model.objects.create_user(username="wprow", password="x")
    user.groups.add(Group.objects.get_or_create(name="wprowadzanie danych")[0])
    client.force_login(user)

    with open(fn_test_import_polon, "rb") as f:
        plik = SimpleUploadedFile(
            "test_import_polon.xlsx",
            f.read(),
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )

    resp = client.post(
        reverse("import_polon:utworz-import"),
        data={"plik": plik, "rok": 2023},
    )

    assert resp.status_code == 302, resp.content[:500]
    import_object = ImportPlikuPolon.objects.get()
    assert import_object.uczelnia_id == uczelnia.pk
