import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker


def _el(rec, tryb, z_plikiem=True):
    from bpp.models import Element_Repozytorium

    plik = SimpleUploadedFile("f.pdf", b"%PDF tresc") if z_plikiem else None
    tryb = getattr(tryb, "value", tryb)
    return Element_Repozytorium.objects.create(
        rekord=rec, rodzaj="pdf", nazwa_pliku="f.pdf", tryb_dostepu=tryb, plik=plik
    )


@pytest.mark.django_db
def test_jawne_pliki_filtruje_dostep_i_brak_pliku():
    from bpp.const import TRYB_DOSTEPU
    from dspace_api.selectors import jawne_pliki_rekordu

    rec = baker.make("bpp.Wydawnictwo_Ciagle")
    jawny = _el(rec, TRYB_DOSTEPU.JAWNY)
    _el(rec, TRYB_DOSTEPU.NIEJAWNY)  # niejawny — pominięty
    _el(rec, TRYB_DOSTEPU.JAWNY, z_plikiem=False)  # jawny bez pliku — pominięty

    wynik = jawne_pliki_rekordu(rec)
    assert [e.pk for e in wynik] == [jawny.pk]


@pytest.mark.django_db
def test_jawne_pliki_pomija_soft_deleted():
    from bpp.const import TRYB_DOSTEPU
    from dspace_api.selectors import jawne_pliki_rekordu

    rec = baker.make("bpp.Wydawnictwo_Ciagle")
    jawny = _el(rec, TRYB_DOSTEPU.JAWNY)
    usuniety = _el(rec, TRYB_DOSTEPU.JAWNY)
    usuniety.delete()  # soft

    wynik = jawne_pliki_rekordu(rec)
    assert [e.pk for e in wynik] == [jawny.pk]
