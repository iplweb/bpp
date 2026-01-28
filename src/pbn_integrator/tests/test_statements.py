"""Tests for statement integration logic.

This module contains tests for:
- integruj_oswiadczenia_z_instytucji_pojedyncza_praca function
- data_oswiadczenia field population from statedTimestamp
"""

from datetime import date

import pytest
from model_bakery import baker

from bpp.models import Typ_Odpowiedzialnosci
from pbn_api.models import Institution, OswiadczenieInstytucji, Publication, Scientist
from pbn_integrator.utils.statements import (
    integruj_oswiadczenia_z_instytucji_pojedyncza_praca,
)


@pytest.fixture
def pbn_institution(db):
    return baker.make(Institution)


@pytest.fixture
def pbn_scientist(db):
    return baker.make(Scientist)


@pytest.fixture
def pbn_publication_for_statement(db):
    return baker.make(Publication, mongoId="test-pub-123")


@pytest.fixture
def typ_odpowiedzialnosci_autor(db):
    typ, _ = Typ_Odpowiedzialnosci.objects.get_or_create(nazwa="autor")
    return typ


@pytest.mark.django_db
def test_integruj_oswiadczenia_ustawia_data_oswiadczenia_z_statedTimestamp(
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina,
    pbn_institution,
    typ_odpowiedzialnosci_autor,
):
    """Test that data_oswiadczenia is set from statedTimestamp when available."""
    pub = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    autor_rec = pub.autorzy_set.first()
    autor = autor_rec.autor
    dyscyplina = autor_rec.dyscyplina_naukowa

    # Utwórz Publication w PBN i zmatchuj z BPP
    pbn_pub = baker.make(Publication, mongoId="test-pub-456")
    pub.pbn_uid = pbn_pub
    pub.save()

    # Utwórz oświadczenie z statedTimestamp
    stated_date = date(2024, 6, 15)
    oswiadczenie = OswiadczenieInstytucji.objects.create(
        addedTimestamp=date(2024, 1, 1),
        statedTimestamp=stated_date,
        inOrcid=False,
        institutionId=pbn_institution,
        personId=autor.pbn_uid,
        publicationId=pbn_pub,
        type="AUTHOR",
        disciplines={"name": dyscyplina.nazwa},
    )

    # Upewnij się, że data_oswiadczenia jest pusta przed integracją
    autor_rec.refresh_from_db()
    assert autor_rec.data_oswiadczenia is None

    # Uruchom integrację
    noted_pub = set()
    noted_aut = set()
    integruj_oswiadczenia_z_instytucji_pojedyncza_praca(
        oswiadczenie, noted_pub, noted_aut
    )

    # Sprawdź, czy data_oswiadczenia została ustawiona
    autor_rec.refresh_from_db()
    assert autor_rec.data_oswiadczenia == stated_date


@pytest.mark.django_db
def test_integruj_oswiadczenia_nie_nadpisuje_gdy_statedTimestamp_jest_None(
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina,
    pbn_institution,
    typ_odpowiedzialnosci_autor,
):
    """Test that data_oswiadczenia remains unchanged when statedTimestamp is None."""
    pub = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    autor_rec = pub.autorzy_set.first()
    autor = autor_rec.autor
    dyscyplina = autor_rec.dyscyplina_naukowa

    # Ustaw istniejącą datę oświadczenia
    existing_date = date(2023, 5, 10)
    autor_rec.data_oswiadczenia = existing_date
    autor_rec.save()

    # Utwórz Publication w PBN i zmatchuj z BPP
    pbn_pub = baker.make(Publication, mongoId="test-pub-789")
    pub.pbn_uid = pbn_pub
    pub.save()

    # Utwórz oświadczenie BEZ statedTimestamp
    oswiadczenie = OswiadczenieInstytucji.objects.create(
        addedTimestamp=date(2024, 1, 1),
        statedTimestamp=None,
        inOrcid=False,
        institutionId=pbn_institution,
        personId=autor.pbn_uid,
        publicationId=pbn_pub,
        type="AUTHOR",
        disciplines={"name": dyscyplina.nazwa},
    )

    # Uruchom integrację
    noted_pub = set()
    noted_aut = set()
    integruj_oswiadczenia_z_instytucji_pojedyncza_praca(
        oswiadczenie, noted_pub, noted_aut
    )

    # Sprawdź, że data_oswiadczenia NIE została nadpisana
    autor_rec.refresh_from_db()
    assert autor_rec.data_oswiadczenia == existing_date


@pytest.mark.django_db
def test_integruj_oswiadczenia_nadpisuje_istniejaca_date_gdy_statedTimestamp_dostepne(
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina,
    pbn_institution,
    typ_odpowiedzialnosci_autor,
):
    """Test that data_oswiadczenia is overwritten when statedTimestamp is provided."""
    pub = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    autor_rec = pub.autorzy_set.first()
    autor = autor_rec.autor
    dyscyplina = autor_rec.dyscyplina_naukowa

    # Ustaw istniejącą datę oświadczenia
    existing_date = date(2023, 5, 10)
    autor_rec.data_oswiadczenia = existing_date
    autor_rec.save()

    # Utwórz Publication w PBN i zmatchuj z BPP
    pbn_pub = baker.make(Publication, mongoId="test-pub-101")
    pub.pbn_uid = pbn_pub
    pub.save()

    # Utwórz oświadczenie z nowym statedTimestamp
    new_stated_date = date(2024, 7, 20)
    oswiadczenie = OswiadczenieInstytucji.objects.create(
        addedTimestamp=date(2024, 1, 1),
        statedTimestamp=new_stated_date,
        inOrcid=False,
        institutionId=pbn_institution,
        personId=autor.pbn_uid,
        publicationId=pbn_pub,
        type="AUTHOR",
        disciplines={"name": dyscyplina.nazwa},
    )

    # Uruchom integrację
    noted_pub = set()
    noted_aut = set()
    integruj_oswiadczenia_z_instytucji_pojedyncza_praca(
        oswiadczenie, noted_pub, noted_aut
    )

    # Sprawdź, że data_oswiadczenia została nadpisana nową datą
    autor_rec.refresh_from_db()
    assert autor_rec.data_oswiadczenia == new_stated_date
