"""FD#460: tytuł czasopisma różniący się tylko diakrytykami nie był dopasowany.

CrossRef podaje „Vedelem Tudomany", a w BPP źródło nazywa się
„Védelem Tudomány". Importer nie dopasowywał źródła, a porównanie
z CrossRef pokazywało tytuły jako różne. Dopasowanie po tytule ma ignorować
wielkość liter i znaki diakrytyczne; dopasowanie po ISSN (FD#451) dalej ma
pierwszeństwo.
"""

import pytest
from model_bakery import baker

from bpp.models import Zrodlo
from crossref_bpp.core import Komparator, StatusPorownania
from import_common.core import matchuj_zrodlo
from importer_publikacji.views.steps import _source_initial_auto_match


class _Sesja:
    def __init__(self, normalized_data):
        self.normalized_data = normalized_data


@pytest.mark.django_db
@pytest.mark.parametrize(
    "w_bazie,z_importu",
    [
        ("Védelem Tudomány", "Vedelem Tudomany"),
        ("Vedelem Tudomany", "Védelem Tudomány"),
        ("Védelem Tudomány", "VEDELEM TUDOMANY"),
        ("Przegląd Służby Zdrowia", "Przeglad Sluzby Zdrowia"),
    ],
)
def test_fd460_matchuj_zrodlo_bez_diakrytykow(w_bazie, z_importu):
    zrodlo = baker.make(Zrodlo, nazwa=w_bazie, skrot="", issn="", e_issn="")
    assert matchuj_zrodlo(z_importu) == zrodlo


@pytest.mark.django_db
def test_fd460_scisle_dopasowanie_bez_luznego_tytulu():
    """Importy hurtowe (``disable_fuzzy=True``) chcą ścisłego dopasowania."""
    baker.make(Zrodlo, nazwa="Védelem Tudomány", skrot="", issn="", e_issn="")
    assert matchuj_zrodlo("Vedelem Tudomany", disable_fuzzy=True) is None


@pytest.mark.django_db
def test_fd460_matchuj_zrodlo_skrot_bez_diakrytykow():
    zrodlo = baker.make(
        Zrodlo, nazwa="Coś innego", skrot="Véd. Tud.", issn="", e_issn=""
    )
    assert matchuj_zrodlo("Ved. Tud.") == zrodlo
    assert matchuj_zrodlo("Ved. Tud.", disable_skrot=True) is None


@pytest.mark.django_db
def test_fd460_matchuj_zrodlo_niejednoznaczne_nie_zgaduje():
    """Dwa źródła pasujące tylko bez diakrytyków — bez ISSN nie zgadujemy."""
    baker.make(Zrodlo, nazwa="Védelem Tudomány", issn="1111-1111", e_issn="")
    b = baker.make(Zrodlo, nazwa="Vedelem Tudomány", issn="2222-2222", e_issn="")

    assert matchuj_zrodlo("Vedelem Tudomany") is None
    assert matchuj_zrodlo("Vedelem Tudomany", issn="2222-2222") == b


@pytest.mark.django_db
def test_fd460_issn_nadal_wygrywa_z_tytulem():
    baker.make(Zrodlo, nazwa="Védelem Tudomány", issn="", e_issn="")
    po_issn = baker.make(Zrodlo, nazwa="Inne czasopismo", issn="1234-5678")

    assert matchuj_zrodlo("Vedelem Tudomany", issn="1234-5678") == po_issn

    wynik = Komparator.porownaj_zrodlo("Vedelem Tudomany", issn="1234-5678")
    assert wynik.status == StatusPorownania.DOKLADNE
    assert wynik.rekord_po_stronie_bpp == po_issn


@pytest.mark.django_db
@pytest.mark.parametrize(
    "w_bazie,z_importu",
    [
        ("Védelem Tudomány", "Vedelem Tudomany"),
        ("Vedelem Tudomany", "Védelem Tudomány"),
    ],
)
def test_fd460_komparator_tytul_bez_diakrytykow(w_bazie, z_importu):
    zrodlo = baker.make(Zrodlo, nazwa=w_bazie, issn="", e_issn="")
    # Podobne, ale inne czasopismo nie może przeszkodzić w dopasowaniu.
    baker.make(Zrodlo, nazwa="Vedelem Tudomany Review", issn="", e_issn="")

    wynik = Komparator.porownaj_container_title(z_importu)

    assert wynik.status == StatusPorownania.LUZNE
    assert "diakrytycznych" in wynik.opis
    assert wynik.rekord_po_stronie_bpp == zrodlo


@pytest.mark.django_db
def test_fd460_komparator_duplikat_bez_akcentow_scalony():
    """Duplikat bez akcentów (np. z wcześniejszego nieudanego importu) nie
    blokuje dopasowania: wygrywa rekord z większą liczbą prac."""
    from bpp.models import Wydawnictwo_Ciagle

    uzywane = baker.make(Zrodlo, nazwa="Védelem Tudomány", issn="", e_issn="")
    baker.make(Zrodlo, nazwa="Vedelem Tudomany", issn="", e_issn="")
    baker.make(Wydawnictwo_Ciagle, zrodlo=uzywane)

    wynik = Komparator.porownaj_container_title("Vedelem Tudomany")

    assert wynik.rekord_po_stronie_bpp == uzywane
    assert not wynik.zduplikowane_zrodla


@pytest.mark.django_db
def test_fd460_komparator_duplikat_bez_akcentow_rozne_issn_blokuje():
    baker.make(Zrodlo, nazwa="Védelem Tudomány", issn="1111-1111", e_issn="")
    baker.make(Zrodlo, nazwa="Vedelem Tudomany", issn="2222-2222", e_issn="")

    wynik = Komparator.porownaj_container_title("Vedelem Tudomany")

    assert wynik.rekord_po_stronie_bpp is None
    assert len(wynik.zduplikowane_zrodla) == 2


@pytest.mark.django_db
def test_fd460_importer_auto_match_zrodla():
    zrodlo = baker.make(Zrodlo, nazwa="Védelem Tudomány", issn="", e_issn="")
    initial = _source_initial_auto_match(_Sesja({"source_title": "Vedelem Tudomany"}))
    assert initial["zrodlo"] == zrodlo.pk
