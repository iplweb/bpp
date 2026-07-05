"""Tests for statement integration logic.

This module contains tests for:
- integruj_oswiadczenia_z_instytucji_pojedyncza_praca function
- data_oswiadczenia field population from statedTimestamp
"""

from datetime import date
from decimal import Decimal

import pytest
from model_bakery import baker

from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Dyscyplina_Naukowa,
    Typ_Odpowiedzialnosci,
)
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


@pytest.mark.django_db
def test_konflikt_dyscyplin_nie_wywala_importu(
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina,
    pbn_institution,
    typ_odpowiedzialnosci_autor,
):
    """Dwa sloty zajęte + trzecia dyscyplina z PBN => raport, nie wyjątek."""
    pub = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    autor_rec = pub.autorzy_set.first()
    autor = autor_rec.autor
    rok = pub.rok

    disc_X = baker.make(Dyscyplina_Naukowa, nazwa="medycyna-X", kod="3.21")
    disc_Y = baker.make(Dyscyplina_Naukowa, nazwa="psychologia-Y", kod="5.111")
    disc_Z = baker.make(Dyscyplina_Naukowa, nazwa="bezpieczenstwo-Z", kod="5.3")

    # Autor ma na ten rok dwa sloty zajęte (X + Y)
    Autor_Dyscyplina.objects.filter(autor=autor, rok=rok).delete()
    Autor_Dyscyplina.objects.create(
        autor=autor,
        rok=rok,
        dyscyplina_naukowa=disc_X,
        subdyscyplina_naukowa=disc_Y,
    )

    pbn_pub = baker.make(Publication, mongoId="konflikt-pub-1")
    pub.pbn_uid = pbn_pub
    pub.save()

    oswiadczenie = OswiadczenieInstytucji.objects.create(
        addedTimestamp=date(2024, 1, 1),
        inOrcid=False,
        institutionId=pbn_institution,
        personId=autor.pbn_uid,
        publicationId=pbn_pub,
        type="AUTHOR",
        disciplines={"name": disc_Z.nazwa},
    )

    zgloszenia = []

    def callback(**kwargs):
        zgloszenia.append(kwargs)

    # NIE powinno podnieść wyjątku
    integruj_oswiadczenia_z_instytucji_pojedyncza_praca(
        oswiadczenie, set(), set(), inconsistency_callback=callback
    )

    typy = [z["inconsistency_type"] for z in zgloszenia]
    assert "discipline_conflict_no_room" in typy

    # Sloty autora bez zmian — Z nie dopisane
    ad = Autor_Dyscyplina.objects.get(autor=autor, rok=rok)
    assert ad.dyscyplina_naukowa == disc_X
    assert ad.subdyscyplina_naukowa == disc_Y


@pytest.mark.django_db
def test_pbn_zglasza_subdyscypline_autora_ustawia_rec_bez_konfliktu(
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina,
    pbn_institution,
    typ_odpowiedzialnosci_autor,
):
    """PBN zgłasza dyscyplinę, którą autor ma jako SUB: rekord pracy dostaje tę
    dyscyplinę, brak wyjątku, brak raportu konfliktu, Autor_Dyscyplina bez zmian."""
    pub = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    autor_rec = pub.autorzy_set.first()
    autor = autor_rec.autor
    rok = pub.rok

    disc_main = baker.make(Dyscyplina_Naukowa, nazwa="glowna-A", kod="1.1")
    disc_sub = baker.make(Dyscyplina_Naukowa, nazwa="poboczna-B", kod="2.2")

    # Autor: glowna = A, sub = B; rekord pracy początkowo kredytowany pod A
    Autor_Dyscyplina.objects.filter(autor=autor, rok=rok).delete()
    Autor_Dyscyplina.objects.create(
        autor=autor,
        rok=rok,
        dyscyplina_naukowa=disc_main,
        subdyscyplina_naukowa=disc_sub,
    )
    autor_rec.dyscyplina_naukowa = disc_main
    autor_rec.save()

    pbn_pub = baker.make(Publication, mongoId="sub-match-pub-1")
    pub.pbn_uid = pbn_pub
    pub.save()

    # PBN zgłasza B (subdyscyplinę autora)
    oswiadczenie = OswiadczenieInstytucji.objects.create(
        addedTimestamp=date(2024, 1, 1),
        inOrcid=False,
        institutionId=pbn_institution,
        personId=autor.pbn_uid,
        publicationId=pbn_pub,
        type="AUTHOR",
        disciplines={"name": disc_sub.nazwa},
    )

    zgloszenia = []

    def callback(**kwargs):
        zgloszenia.append(kwargs)

    integruj_oswiadczenia_z_instytucji_pojedyncza_praca(
        oswiadczenie, set(), set(), inconsistency_callback=callback
    )

    typy = [z["inconsistency_type"] for z in zgloszenia]
    assert "discipline_conflict_no_room" not in typy

    # Rekord pracy kredytowany teraz pod B (sub) — bo PBN tak zgłosił
    autor_rec.refresh_from_db()
    assert autor_rec.dyscyplina_naukowa == disc_sub

    # Autor_Dyscyplina autora niezmienione (B już było subdyscypliną)
    ad = Autor_Dyscyplina.objects.get(autor=autor, rok=rok)
    assert ad.dyscyplina_naukowa == disc_main
    assert ad.subdyscyplina_naukowa == disc_sub


@pytest.mark.django_db
def test_dopasowanie_po_nazwisku_zamiast_author_not_found(
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina,
    pbn_institution,
    typ_odpowiedzialnosci_autor,
):
    """Współautor o tym samym imieniu/nazwisku (inne ID) => match by name,
    NIE author_not_found."""
    pub = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    autor_rec = pub.autorzy_set.first()
    autor_B = autor_rec.autor  # współautor faktycznie na pracy

    # Autor A: ten sam imię/nazwisko, INNE ID; to on dostaje pbn_uid z oświadczenia
    scientist = baker.make(Scientist, lastName=autor_B.nazwisko, name=autor_B.imiona)
    autor_A = baker.make(
        Autor,
        nazwisko=autor_B.nazwisko,
        imiona=autor_B.imiona,
        pbn_uid=scientist,
    )
    assert autor_A.pk != autor_B.pk

    pbn_pub = baker.make(Publication, mongoId="match-name-pub-1")
    pub.pbn_uid = pbn_pub
    pub.save()

    oswiadczenie = OswiadczenieInstytucji.objects.create(
        addedTimestamp=date(2024, 1, 1),
        inOrcid=False,
        institutionId=pbn_institution,
        personId=scientist,
        publicationId=pbn_pub,
        type="AUTHOR",
        disciplines={"name": autor_rec.dyscyplina_naukowa.nazwa},
    )

    zgloszenia = []

    def callback(**kwargs):
        zgloszenia.append(kwargs)

    integruj_oswiadczenia_z_instytucji_pojedyncza_praca(
        oswiadczenie, set(), set(), inconsistency_callback=callback
    )

    typy = [z["inconsistency_type"] for z in zgloszenia]
    assert "author_matched_by_name" in typy
    assert "author_not_found" not in typy

    # Autor pracy NIE został podmieniony (B zostaje, brak swapu na A)
    autor_rec.refresh_from_db()
    assert autor_rec.autor == autor_B


@pytest.mark.django_db
def test_autor_spoza_pracy_wymaga_recznej_korekty(
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina,
    pbn_institution,
    typ_odpowiedzialnosci_autor,
):
    """Autor o tym samym imieniu/nazwisku istnieje w BPP, ale NIE jest
    współautorem tej pracy => manual_fix, autor NIE dopisany."""
    pub = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    liczba_autorow_przed = pub.autorzy_set.count()

    scientist = baker.make(Scientist, lastName="Bałdys-Waligórska", name="Agata")
    baker.make(Autor, nazwisko="Bałdys-Waligórska", imiona="Agata", pbn_uid=scientist)

    pbn_pub = baker.make(Publication, mongoId="manual-fix-pub-1")
    pub.pbn_uid = pbn_pub
    pub.save()

    oswiadczenie = OswiadczenieInstytucji.objects.create(
        addedTimestamp=date(2024, 1, 1),
        inOrcid=False,
        institutionId=pbn_institution,
        personId=scientist,
        publicationId=pbn_pub,
        type="AUTHOR",
        disciplines={"name": pub.autorzy_set.first().dyscyplina_naukowa.nazwa},
    )

    zgloszenia = []

    def callback(**kwargs):
        zgloszenia.append(kwargs)

    integruj_oswiadczenia_z_instytucji_pojedyncza_praca(
        oswiadczenie, set(), set(), inconsistency_callback=callback
    )

    typy = [z["inconsistency_type"] for z in zgloszenia]
    assert "author_needs_manual_fix" in typy
    # Autor NIE został dopisany do publikacji
    assert pub.autorzy_set.count() == liczba_autorow_przed


@pytest.mark.django_db
def test_auto_przypisanie_dyscypliny_z_pbn_bez_crasha(
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina,
    pbn_institution,
    typ_odpowiedzialnosci_autor,
):
    """Autor bez przypisania dyscyplin: PBN nadaje dyscyplinę => auto-utworzenie
    (100%), raport discipline_auto_assigned, brak crasha na walidującym save()."""
    pub = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    autor_rec = pub.autorzy_set.first()
    autor = autor_rec.autor
    rok = pub.rok

    disc_new = baker.make(Dyscyplina_Naukowa, nazwa="nowa-dyscyplina", kod="9.9")

    # Autor nie ma żadnego przypisania dyscyplin na ten rok; rekord bez dyscypliny
    Autor_Dyscyplina.objects.filter(autor=autor, rok=rok).delete()
    autor_rec.dyscyplina_naukowa = None
    autor_rec.save()

    pbn_pub = baker.make(Publication, mongoId="auto-assign-pub-1")
    pub.pbn_uid = pbn_pub
    pub.save()

    oswiadczenie = OswiadczenieInstytucji.objects.create(
        addedTimestamp=date(2024, 1, 1),
        inOrcid=False,
        institutionId=pbn_institution,
        personId=autor.pbn_uid,
        publicationId=pbn_pub,
        type="AUTHOR",
        disciplines={"name": disc_new.nazwa},
    )

    zgloszenia = []

    def callback(**kwargs):
        zgloszenia.append(kwargs)

    integruj_oswiadczenia_z_instytucji_pojedyncza_praca(
        oswiadczenie, set(), set(), inconsistency_callback=callback
    )

    typy = [z["inconsistency_type"] for z in zgloszenia]
    assert "discipline_auto_assigned" in typy

    ad = Autor_Dyscyplina.objects.get(autor=autor, rok=rok)
    assert ad.dyscyplina_naukowa == disc_new
    assert ad.procent_dyscypliny == Decimal("100.00")

    autor_rec.refresh_from_db()
    assert autor_rec.dyscyplina_naukowa == disc_new


@pytest.mark.django_db
def test_tier4_znormalizowane_dopasowanie_bez_swapu(
    pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina,
    pbn_institution,
    typ_odpowiedzialnosci_autor,
):
    """Dopasowanie po znormalizowanym nazwisku (różnica w diakrytykach) NIE
    podmienia autora pracy: author_matched_by_name, NIE author_replaced,
    brak crasha na walidującym save()."""
    pub = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    autor_rec = pub.autorzy_set.first()
    autor_B = autor_rec.autor

    # B na pracy: wersja bez diakrytyków
    autor_B.nazwisko = "Letowska"
    autor_B.imiona = "Anna"
    autor_B.save()

    # A (osoba z PBN): wersja z diakrytykami, inne ID, ma pbn_uid z oświadczenia
    scientist = baker.make(Scientist, lastName="Łętowska", name="Anna")
    autor_A = baker.make(Autor, nazwisko="Łętowska", imiona="Anna", pbn_uid=scientist)
    assert autor_A.pk != autor_B.pk

    pbn_pub = baker.make(Publication, mongoId="tier4-pub-1")
    pub.pbn_uid = pbn_pub
    pub.save()

    oswiadczenie = OswiadczenieInstytucji.objects.create(
        addedTimestamp=date(2024, 1, 1),
        inOrcid=False,
        institutionId=pbn_institution,
        personId=scientist,
        publicationId=pbn_pub,
        type="AUTHOR",
        disciplines={"name": autor_rec.dyscyplina_naukowa.nazwa},
    )

    zgloszenia = []

    def callback(**kwargs):
        zgloszenia.append(kwargs)

    integruj_oswiadczenia_z_instytucji_pojedyncza_praca(
        oswiadczenie, set(), set(), inconsistency_callback=callback
    )

    typy = [z["inconsistency_type"] for z in zgloszenia]
    assert "author_matched_by_name" in typy
    assert "author_replaced" not in typy

    # Autor pracy NIE został podmieniony (B zostaje)
    autor_rec.refresh_from_db()
    assert autor_rec.autor == autor_B
