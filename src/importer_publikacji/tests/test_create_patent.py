"""Testy tworzenia ``bpp.Patent`` z sesji importera (``_create_patent`` +
dispatch trójstronny w ``_create_publication``).

Patent nie ma ``typ_kbn`` (brak ``ModelTypowany``) i jego
``charakter_formalny``/``jezyk`` są zahardkodowanymi ``@cached_property``
(nie polami modelu) — przekazanie ich do ``Patent.objects.create()``
rzuciłoby ``TypeError``. Te testy pilnują, że ``_create_patent`` je
odfiltrowuje i że dispatch w ``_create_publication`` trafia do niego dla
sesji z ``rodzaj_rekordu == PATENT``, a istniejące ciągłe/zwarte zachowanie
(dispatch po ``jest_wydawnictwem_zwartym``) nie regresuje.
"""

from datetime import date

import pytest
from model_bakery import baker

from bpp.models import Patent, Rodzaj_Prawa_Patentowego, Status_Korekty, Typ_KBN
from importer_publikacji.models import ImportSession
from importer_publikacji.views import _create_patent, _create_publication


def _patent_normalized_data(**extra):
    nd = {
        "title": "Sposob wytwarzania widgetu",
        "doi": None,
        "year": 2024,
        "authors": [],
        "source_title": None,
        "source_abbreviation": None,
        "issn": None,
        "e_issn": None,
        "isbn": None,
        "e_isbn": None,
        "publisher": None,
        "publication_type": "patent",
        "language": None,
        "abstract": None,
        "volume": None,
        "issue": None,
        "pages": None,
        "url": None,
        "license_url": None,
        "keywords": [],
        "article_number": None,
        "original_title": None,
        "abstracts": [],
        "patent_number": "PL123456",
        "patent_grant_number": None,
        "filing_date": "2024-03-15",
        "grant_date": None,
        "patent_type": None,
        "patent_holder": "ACME Corp",
        "jurisdiction": "Poland",
    }
    nd.update(extra)
    return nd


def _make_patent_session(user, **nd_extra):
    return ImportSession.objects.create(
        created_by=user,
        provider_name="BibTeX",
        identifier="@patent{...}",
        raw_data={"bibtex_type": "patent"},
        normalized_data=_patent_normalized_data(**nd_extra),
        rodzaj_rekordu=ImportSession.RodzajRekordu.PATENT,
    )


def _common_fields(**overrides):
    """Minimalny ``common_fields`` jak zbudowany przez ``_create_publication``
    (patrz ``publikacja.py``), z dwoma polami trującymi dla ``Patent``."""
    fields = {
        "tytul_oryginalny": "Test",
        "rok": 2024,
        "doi": None,
        "tom": "",
        "strony": "",
        "www": "",
        "issn": "",
        "e_issn": "",
        "slowa_kluczowe": "",
        "adnotacje": "",
        "charakter_formalny": None,
        "typ_kbn": None,
        "jezyk": None,
        "status_korekty_id": Status_Korekty.objects.first().pk,
    }
    fields.update(overrides)
    return fields


@pytest.mark.django_db
def test_create_patent_creates_patent_record(importer_user, statusy_korekt):
    session = _make_patent_session(importer_user)
    common_fields = _common_fields(tytul_oryginalny="Sposob wytwarzania widgetu")

    record = _create_patent(session, common_fields, session.normalized_data)

    assert isinstance(record, Patent)
    assert record.tytul_oryginalny == "Sposob wytwarzania widgetu"
    assert record.rok == 2024
    assert record.numer_zgloszenia == "PL123456"
    assert record.data_zgloszenia == date(2024, 3, 15)


@pytest.mark.django_db
def test_create_patent_does_not_pass_typ_kbn_or_charakter_formalny(
    importer_user, statusy_korekt
):
    """Regresja: przekazanie typ_kbn/charakter_formalny/jezyk do
    Patent.objects.create rzuca TypeError, bo to nie sa pola modelu Patent
    (cached_property/brak ModelTypowany). _create_patent musi je odfiltrowac."""
    session = _make_patent_session(importer_user)
    common_fields = _common_fields(
        # Wartosci-pulapki: gdyby trafily do .objects.create(), TypeError.
        charakter_formalny=object(),
        typ_kbn=object(),
        jezyk=object(),
    )

    record = _create_patent(session, common_fields, session.normalized_data)
    assert isinstance(record, Patent)


@pytest.mark.django_db
def test_create_patent_resolves_rodzaj_prawa_by_name(importer_user, statusy_korekt):
    rodzaj = baker.make(Rodzaj_Prawa_Patentowego, nazwa="patent")
    session = _make_patent_session(importer_user, patent_type="patent")
    common_fields = _common_fields()

    record = _create_patent(session, common_fields, session.normalized_data)
    assert record.rodzaj_prawa == rodzaj


@pytest.mark.django_db
def test_create_patent_unresolvable_rodzaj_prawa_left_blank(
    importer_user, statusy_korekt
):
    session = _make_patent_session(importer_user, patent_type="nieznany-typ-xyz")
    common_fields = _common_fields()

    record = _create_patent(session, common_fields, session.normalized_data)
    assert record.rodzaj_prawa is None


@pytest.mark.django_db
def test_create_patent_holder_recorded_in_informacje(importer_user, statusy_korekt):
    session = _make_patent_session(importer_user)
    common_fields = _common_fields()

    record = _create_patent(session, common_fields, session.normalized_data)
    assert "ACME Corp" in record.informacje


@pytest.mark.django_db
def test_create_publication_dispatches_patent(
    importer_user,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
):
    """_create_publication trafia do _create_patent gdy
    rodzaj_rekordu == PATENT, niezaleznie od jest_wydawnictwem_zwartym."""
    session = _make_patent_session(importer_user)
    # Sprzeczny/nieustawiony stan jest_wydawnictwem_zwartym nie powinien
    # miec znaczenia — rodzaj_rekordu ma pierwszenstwo.
    session.jest_wydawnictwem_zwartym = True
    session.save()

    record = _create_publication(session)

    assert isinstance(record, Patent)


@pytest.mark.django_db
def test_create_publication_default_rodzaj_rekordu_unaffected(
    importer_user,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
):
    """Sesje bez ustawionego rodzaj_rekordu (domyslne 'ciagle', back-compat)
    nadal dispatchuja po jest_wydawnictwem_zwartym — brak regresji."""
    from bpp.models import Wydawnictwo_Ciagle

    nd = _patent_normalized_data(
        publication_type=None,
        patent_number=None,
        patent_holder=None,
        filing_date=None,
        jurisdiction=None,
    )

    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/test-ciagle",
        raw_data={},
        normalized_data=nd,
        charakter_formalny=charaktery_formalne["AC"],
        typ_kbn=Typ_KBN.objects.get(skrot="PO"),
        jezyk=jezyki["pol."],
    )

    record = _create_publication(session)

    assert isinstance(record, Wydawnictwo_Ciagle)
