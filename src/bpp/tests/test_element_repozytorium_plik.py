import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker


@pytest.mark.django_db
def test_plik_zapis_i_odczyt():
    from bpp.models import Element_Repozytorium

    rec = baker.make("bpp.Wydawnictwo_Ciagle")
    el = Element_Repozytorium(
        rekord=rec,
        rodzaj="pdf",
        nazwa_pliku="praca.pdf",
        tryb_dostepu=2,  # JAWNY
        plik=SimpleUploadedFile("praca.pdf", b"%PDF-1.4 tresc"),
    )
    el.save()

    el.refresh_from_db()
    assert el.plik
    with el.plik.open("rb") as f:
        assert f.read() == b"%PDF-1.4 tresc"
    # nazwa pliku na dysku jest UUID-owa (nie oryginalna)
    assert "protected/repozytorium/" in el.plik.name


@pytest.mark.django_db
def test_soft_delete_wypada_z_objects():
    from bpp.models import Element_Repozytorium

    rec = baker.make("bpp.Wydawnictwo_Ciagle")
    el = baker.make(Element_Repozytorium, rekord=rec, tryb_dostepu=2)

    pk = el.pk
    el.delete()  # soft

    assert not Element_Repozytorium.objects.filter(pk=pk).exists()
    # ale nadal istnieje globalnie (soft, nie hard)
    assert Element_Repozytorium.global_objects.filter(pk=pk).exists()
