import pytest
from django.contrib.contenttypes.models import ContentType
from model_bakery import baker

from komparator_pbn_udzialy.models import BrakAutoraWPublikacji, RozbieznoscDyscyplinPBN
from komparator_pbn_udzialy.utils import KomparatorDyscyplinPBN


@pytest.mark.django_db
def test_komparator_save_missing_record_brak_publikacji():
    """Test save_missing_record dla typu brak publikacji."""
    pbn_scientist = baker.make("pbn_api.Scientist")
    oswiadczenie = baker.make(
        "pbn_api.OswiadczenieInstytucji",
        personId=pbn_scientist,
        disciplines=None,
    )

    komparator = KomparatorDyscyplinPBN()
    komparator.save_missing_record(
        oswiadczenie=oswiadczenie,
        typ=BrakAutoraWPublikacji.TYP_BRAK_PUBLIKACJI,
        autor=None,
        publikacja=None,
    )

    assert BrakAutoraWPublikacji.objects.count() == 1
    brak = BrakAutoraWPublikacji.objects.first()
    assert brak.typ == BrakAutoraWPublikacji.TYP_BRAK_PUBLIKACJI
    assert brak.autor is None
    assert brak.publikacja is None
    assert brak.pbn_scientist == pbn_scientist


@pytest.mark.django_db
def test_komparator_save_missing_record_brak_autora():
    """Test save_missing_record dla typu brak autora."""
    pbn_scientist = baker.make("pbn_api.Scientist")
    wydawnictwo = baker.make("bpp.Wydawnictwo_Ciagle")
    oswiadczenie = baker.make(
        "pbn_api.OswiadczenieInstytucji",
        personId=pbn_scientist,
        disciplines=None,
    )

    komparator = KomparatorDyscyplinPBN()
    komparator.save_missing_record(
        oswiadczenie=oswiadczenie,
        typ=BrakAutoraWPublikacji.TYP_BRAK_AUTORA_W_BPP,
        autor=None,
        publikacja=wydawnictwo,
    )

    assert BrakAutoraWPublikacji.objects.count() == 1
    brak = BrakAutoraWPublikacji.objects.first()
    assert brak.typ == BrakAutoraWPublikacji.TYP_BRAK_AUTORA_W_BPP
    assert brak.autor is None
    assert brak.publikacja == wydawnictwo
    assert brak.pbn_scientist == pbn_scientist


@pytest.mark.django_db
def test_komparator_save_missing_record_brak_powiazania():
    """Test save_missing_record dla typu brak powiązania."""
    autor = baker.make("bpp.Autor")
    pbn_scientist = baker.make("pbn_api.Scientist")
    wydawnictwo = baker.make("bpp.Wydawnictwo_Ciagle")
    oswiadczenie = baker.make(
        "pbn_api.OswiadczenieInstytucji",
        personId=pbn_scientist,
        disciplines=None,
    )

    komparator = KomparatorDyscyplinPBN()
    komparator.save_missing_record(
        oswiadczenie=oswiadczenie,
        typ=BrakAutoraWPublikacji.TYP_BRAK_POWIAZANIA,
        autor=autor,
        publikacja=wydawnictwo,
    )

    assert BrakAutoraWPublikacji.objects.count() == 1
    brak = BrakAutoraWPublikacji.objects.first()
    assert brak.typ == BrakAutoraWPublikacji.TYP_BRAK_POWIAZANIA
    assert brak.autor == autor
    assert brak.publikacja == wydawnictwo
    assert brak.pbn_scientist == pbn_scientist


@pytest.mark.django_db
def test_komparator_save_missing_record_update_or_create():
    """Test że save_missing_record używa update_or_create."""
    pbn_scientist = baker.make("pbn_api.Scientist")
    oswiadczenie = baker.make(
        "pbn_api.OswiadczenieInstytucji",
        personId=pbn_scientist,
        disciplines=None,
    )

    komparator = KomparatorDyscyplinPBN()

    # Pierwszy zapis
    komparator.save_missing_record(
        oswiadczenie=oswiadczenie,
        typ=BrakAutoraWPublikacji.TYP_BRAK_PUBLIKACJI,
        autor=None,
        publikacja=None,
    )
    assert BrakAutoraWPublikacji.objects.count() == 1

    # Drugi zapis z tym samym oświadczeniem - powinien zaktualizować
    wydawnictwo = baker.make("bpp.Wydawnictwo_Ciagle")
    komparator.save_missing_record(
        oswiadczenie=oswiadczenie,
        typ=BrakAutoraWPublikacji.TYP_BRAK_AUTORA_W_BPP,
        autor=None,
        publikacja=wydawnictwo,
    )
    assert BrakAutoraWPublikacji.objects.count() == 1

    brak = BrakAutoraWPublikacji.objects.first()
    assert brak.typ == BrakAutoraWPublikacji.TYP_BRAK_AUTORA_W_BPP
    assert brak.publikacja == wydawnictwo


@pytest.mark.django_db
def test_komparator_clear_discrepancies_clears_both_models():
    """Test że clear_discrepancies czyści oba modele."""
    # Utwórz rozbieżność
    wydawnictwo_autor = baker.make("bpp.Wydawnictwo_Ciagle_Autor")
    content_type = ContentType.objects.get_for_model(wydawnictwo_autor)
    oswiadczenie = baker.make("pbn_api.OswiadczenieInstytucji")

    RozbieznoscDyscyplinPBN.objects.create(
        content_type=content_type,
        object_id=wydawnictwo_autor.pk,
        oswiadczenie_instytucji=oswiadczenie,
    )

    # Utwórz brakującego autora
    pbn_scientist = baker.make("pbn_api.Scientist")
    oswiadczenie2 = baker.make(
        "pbn_api.OswiadczenieInstytucji",
        personId=pbn_scientist,
    )
    BrakAutoraWPublikacji.objects.create(
        pbn_scientist=pbn_scientist,
        oswiadczenie_instytucji=oswiadczenie2,
        typ=BrakAutoraWPublikacji.TYP_BRAK_PUBLIKACJI,
    )

    assert RozbieznoscDyscyplinPBN.objects.count() == 1
    assert BrakAutoraWPublikacji.objects.count() == 1

    # Wyczyść
    komparator = KomparatorDyscyplinPBN()
    komparator.clear_discrepancies()

    assert RozbieznoscDyscyplinPBN.objects.count() == 0
    assert BrakAutoraWPublikacji.objects.count() == 0


@pytest.mark.django_db
def test_komparator_stats_include_missing_counts():
    """Test że statystyki zawierają liczniki brakujących."""
    komparator = KomparatorDyscyplinPBN()

    assert "missing_publication" in komparator.stats
    assert "missing_autor" in komparator.stats
    assert "missing_link" in komparator.stats
    assert komparator.stats["missing_publication"] == 0
    assert komparator.stats["missing_autor"] == 0
    assert komparator.stats["missing_link"] == 0
