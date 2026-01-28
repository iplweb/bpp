import pytest
from django.contrib.contenttypes.models import ContentType
from model_bakery import baker

from komparator_pbn_udzialy.models import (
    BrakAutoraWPublikacji,
    ProblemWrapper,
    RozbieznoscDyscyplinPBN,
)


@pytest.mark.django_db
def test_brak_autora_w_publikacji_create_typ_brak_publikacji():
    """Test tworzenia rekordu z typem brak publikacji."""
    pbn_scientist = baker.make("pbn_api.Scientist")
    oswiadczenie = baker.make(
        "pbn_api.OswiadczenieInstytucji",
        personId=pbn_scientist,
    )

    brak = BrakAutoraWPublikacji.objects.create(
        autor=None,
        pbn_scientist=pbn_scientist,
        content_type=None,
        object_id=None,
        oswiadczenie_instytucji=oswiadczenie,
        typ=BrakAutoraWPublikacji.TYP_BRAK_PUBLIKACJI,
        dyscyplina_pbn=None,
    )

    assert brak.pk is not None
    assert brak.typ == BrakAutoraWPublikacji.TYP_BRAK_PUBLIKACJI
    assert brak.autor is None
    assert brak.publikacja is None
    assert brak.get_typ_display() == "Publikacja nie istnieje w BPP"


@pytest.mark.django_db
def test_brak_autora_w_publikacji_create_typ_brak_autora():
    """Test tworzenia rekordu z typem brak autora."""
    pbn_scientist = baker.make("pbn_api.Scientist")
    wydawnictwo = baker.make("bpp.Wydawnictwo_Ciagle")
    oswiadczenie = baker.make(
        "pbn_api.OswiadczenieInstytucji",
        personId=pbn_scientist,
    )

    content_type = ContentType.objects.get_for_model(wydawnictwo)

    brak = BrakAutoraWPublikacji.objects.create(
        autor=None,
        pbn_scientist=pbn_scientist,
        content_type=content_type,
        object_id=wydawnictwo.pk,
        oswiadczenie_instytucji=oswiadczenie,
        typ=BrakAutoraWPublikacji.TYP_BRAK_AUTORA_W_BPP,
        dyscyplina_pbn=None,
    )

    assert brak.pk is not None
    assert brak.typ == BrakAutoraWPublikacji.TYP_BRAK_AUTORA_W_BPP
    assert brak.autor is None
    assert brak.publikacja == wydawnictwo
    assert brak.get_typ_display() == "Autor nie istnieje w BPP"


@pytest.mark.django_db
def test_brak_autora_w_publikacji_create_typ_brak_powiazania():
    """Test tworzenia rekordu z typem brak powiązania."""
    autor = baker.make("bpp.Autor")
    pbn_scientist = baker.make("pbn_api.Scientist")
    wydawnictwo = baker.make("bpp.Wydawnictwo_Ciagle")
    oswiadczenie = baker.make(
        "pbn_api.OswiadczenieInstytucji",
        personId=pbn_scientist,
    )

    content_type = ContentType.objects.get_for_model(wydawnictwo)

    brak = BrakAutoraWPublikacji.objects.create(
        autor=autor,
        pbn_scientist=pbn_scientist,
        content_type=content_type,
        object_id=wydawnictwo.pk,
        oswiadczenie_instytucji=oswiadczenie,
        typ=BrakAutoraWPublikacji.TYP_BRAK_POWIAZANIA,
        dyscyplina_pbn=None,
    )

    assert brak.pk is not None
    assert brak.typ == BrakAutoraWPublikacji.TYP_BRAK_POWIAZANIA
    assert brak.autor == autor
    assert brak.publikacja == wydawnictwo
    assert brak.get_typ_display() == "Autor nie jest powiązany z publikacją"


@pytest.mark.django_db
def test_brak_autora_w_publikacji_unique_oswiadczenie():
    """Test że jedno oświadczenie = jeden wpis."""
    pbn_scientist = baker.make("pbn_api.Scientist")
    oswiadczenie = baker.make(
        "pbn_api.OswiadczenieInstytucji",
        personId=pbn_scientist,
    )

    BrakAutoraWPublikacji.objects.create(
        autor=None,
        pbn_scientist=pbn_scientist,
        oswiadczenie_instytucji=oswiadczenie,
        typ=BrakAutoraWPublikacji.TYP_BRAK_PUBLIKACJI,
    )

    # Próba utworzenia drugiego rekordu z tym samym oświadczeniem
    # powinna zakończyć się błędem IntegrityError
    from django.db import IntegrityError

    with pytest.raises(IntegrityError):
        BrakAutoraWPublikacji.objects.create(
            autor=None,
            pbn_scientist=pbn_scientist,
            oswiadczenie_instytucji=oswiadczenie,
            typ=BrakAutoraWPublikacji.TYP_BRAK_AUTORA_W_BPP,
        )


@pytest.mark.django_db
def test_brak_autora_w_publikacji_str():
    """Test metody __str__."""
    pbn_scientist = baker.make("pbn_api.Scientist", name="Jan", lastName="Kowalski")
    oswiadczenie = baker.make(
        "pbn_api.OswiadczenieInstytucji",
        personId=pbn_scientist,
    )

    brak = BrakAutoraWPublikacji.objects.create(
        autor=None,
        pbn_scientist=pbn_scientist,
        oswiadczenie_instytucji=oswiadczenie,
        typ=BrakAutoraWPublikacji.TYP_BRAK_PUBLIKACJI,
    )

    str_repr = str(brak)
    assert "Publikacja nie istnieje w BPP" in str_repr


@pytest.mark.django_db
def test_problem_wrapper_for_rozbieznosc():
    """Test ProblemWrapper dla RozbieznoscDyscyplinPBN."""
    autor = baker.make("bpp.Autor")
    jednostka = baker.make("bpp.Jednostka")
    wydawnictwo = baker.make("bpp.Wydawnictwo_Ciagle")
    wydawnictwo_autor = baker.make(
        "bpp.Wydawnictwo_Ciagle_Autor",
        autor=autor,
        jednostka=jednostka,
        rekord=wydawnictwo,
    )
    dyscyplina_bpp = baker.make("bpp.Dyscyplina_Naukowa", nazwa="Informatyka")
    dyscyplina_pbn = baker.make("bpp.Dyscyplina_Naukowa", nazwa="Matematyka")
    publikacja_pbn = baker.make("pbn_api.Publication", year=2023)
    oswiadczenie = baker.make(
        "pbn_api.OswiadczenieInstytucji",
        publicationId=publikacja_pbn,
    )

    content_type = ContentType.objects.get_for_model(wydawnictwo_autor)

    rozbieznosc = RozbieznoscDyscyplinPBN.objects.create(
        content_type=content_type,
        object_id=wydawnictwo_autor.pk,
        oswiadczenie_instytucji=oswiadczenie,
        dyscyplina_bpp=dyscyplina_bpp,
        dyscyplina_pbn=dyscyplina_pbn,
    )

    wrapper = ProblemWrapper(rozbieznosc)

    assert wrapper.pk == rozbieznosc.pk
    assert wrapper.typ == ProblemWrapper.TYP_ROZNE_DYSCYPLINY
    assert wrapper.typ_display == "Różne dyscypliny"
    assert wrapper.typ_css_class == "info"
    assert wrapper.autor_display == str(autor)
    assert wrapper.dyscyplina_bpp == dyscyplina_bpp
    assert wrapper.dyscyplina_pbn == dyscyplina_pbn
    assert wrapper.rok == 2023
    assert wrapper.detail_url_name == "komparator_pbn_udzialy:detail"


@pytest.mark.django_db
def test_problem_wrapper_for_brak_autora():
    """Test ProblemWrapper dla BrakAutoraWPublikacji."""
    pbn_scientist = baker.make("pbn_api.Scientist", name="Jan", lastName="Kowalski")
    dyscyplina_pbn = baker.make("bpp.Dyscyplina_Naukowa", nazwa="Fizyka")
    publikacja_pbn = baker.make("pbn_api.Publication", year=2024, title="Test article")
    oswiadczenie = baker.make(
        "pbn_api.OswiadczenieInstytucji",
        personId=pbn_scientist,
        publicationId=publikacja_pbn,
    )

    brak = BrakAutoraWPublikacji.objects.create(
        autor=None,
        pbn_scientist=pbn_scientist,
        oswiadczenie_instytucji=oswiadczenie,
        typ=BrakAutoraWPublikacji.TYP_BRAK_AUTORA_W_BPP,
        dyscyplina_pbn=dyscyplina_pbn,
    )

    wrapper = ProblemWrapper(brak)

    assert wrapper.pk == brak.pk
    assert wrapper.typ == BrakAutoraWPublikacji.TYP_BRAK_AUTORA_W_BPP
    assert wrapper.typ_display == "Autor nie istnieje w BPP"
    assert wrapper.typ_css_class == "alert"
    assert wrapper.autor_display == "Jan Kowalski [PBN]"
    assert wrapper.dyscyplina_bpp is None
    assert wrapper.dyscyplina_pbn == dyscyplina_pbn
    assert wrapper.rok == 2024
    assert wrapper.detail_url_name == "komparator_pbn_udzialy:missing_autor_detail"


@pytest.mark.django_db
def test_problem_wrapper_typ_css_classes():
    """Test wszystkich klas CSS dla różnych typów problemów."""
    pbn_scientist = baker.make("pbn_api.Scientist")
    oswiadczenie = baker.make(
        "pbn_api.OswiadczenieInstytucji",
        personId=pbn_scientist,
    )

    # Brak powiązania
    brak_powiazania = BrakAutoraWPublikacji.objects.create(
        pbn_scientist=pbn_scientist,
        oswiadczenie_instytucji=oswiadczenie,
        typ=BrakAutoraWPublikacji.TYP_BRAK_POWIAZANIA,
    )
    wrapper = ProblemWrapper(brak_powiazania)
    assert wrapper.typ_css_class == "warning"

    # Usuń i utwórz nowy dla innego testu
    brak_powiazania.delete()

    # Brak publikacji
    brak_publikacji = BrakAutoraWPublikacji.objects.create(
        pbn_scientist=pbn_scientist,
        oswiadczenie_instytucji=oswiadczenie,
        typ=BrakAutoraWPublikacji.TYP_BRAK_PUBLIKACJI,
    )
    wrapper = ProblemWrapper(brak_publikacji)
    assert wrapper.typ_css_class == "secondary"
