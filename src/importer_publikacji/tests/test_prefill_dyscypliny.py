import pytest
from model_bakery import baker

from importer_publikacji.models import ImportedAuthor, ImportSession
from importer_publikacji.views import (
    _find_matching_zgloszenie,
    _prefill_dyscypliny_z_zgloszen,
)


@pytest.fixture
def session(importer_user, db):
    """Sesja importu z DOI i tytułem."""
    return ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/test",
        raw_data={},
        normalized_data={
            "title": "Test Publication Title",
            "doi": "10.1234/test",
            "year": 2024,
            "authors": [],
        },
    )


@pytest.fixture
def dyscyplina(db):
    return baker.make("bpp.Dyscyplina_Naukowa")


@pytest.fixture
def autor(db):
    return baker.make("bpp.Autor")


@pytest.fixture
def jednostka(db):
    return baker.make("bpp.Jednostka")


def _make_zgloszenie(
    doi=None,
    title="Test Publication Title",
    status=0,
    **kwargs,
):
    """Utwórz Zgloszenie_Publikacji z podanymi parametrami."""
    return baker.make(
        "zglos_publikacje.Zgloszenie_Publikacji",
        doi=doi,
        tytul_oryginalny=title,
        status=status,
        rok=2024,
        rodzaj_zglaszanej_publikacji=1,
        **kwargs,
    )


def _make_zpa(zgloszenie, autor, dyscyplina=None, jednostka=None):
    """Utwórz Zgloszenie_Publikacji_Autor.

    Jeśli podano dyscyplinę, tworzy też Autor_Dyscyplina
    (wymagane przez clean() modelu).
    """
    if dyscyplina:
        from bpp.models import Autor_Dyscyplina

        Autor_Dyscyplina.objects.get_or_create(
            autor=autor,
            rok=2024,
            defaults={"dyscyplina_naukowa": dyscyplina},
        )

    return baker.make(
        "zglos_publikacje.Zgloszenie_Publikacji_Autor",
        rekord=zgloszenie,
        autor=autor,
        jednostka=jednostka or baker.make("bpp.Jednostka"),
        dyscyplina_naukowa=dyscyplina,
        rok=2024,
    )


def _make_imported_author(
    session,
    autor=None,
    dyscyplina=None,
    jednostka=None,
    order=0,
):
    return ImportedAuthor.objects.create(
        session=session,
        order=order,
        family_name="Test",
        given_name="Author",
        matched_autor=autor,
        matched_dyscyplina=dyscyplina,
        matched_jednostka=jednostka,
        match_status=(
            ImportedAuthor.MatchStatus.AUTO_EXACT
            if autor
            else ImportedAuthor.MatchStatus.UNMATCHED
        ),
    )


@pytest.mark.django_db
def test_prefill_by_doi(session, autor, dyscyplina):
    """Dopasowanie po DOI uzupełnia dyscyplinę."""
    zgl = _make_zgloszenie(doi="10.1234/test")
    _make_zpa(zgl, autor, dyscyplina=dyscyplina)

    imported = _make_imported_author(session, autor=autor)

    _prefill_dyscypliny_z_zgloszen(session)

    imported.refresh_from_db()
    assert imported.matched_dyscyplina == dyscyplina


@pytest.mark.django_db
def test_prefill_by_title(session, autor, dyscyplina):
    """Dopasowanie po tytule (bez DOI)."""
    session.normalized_data["doi"] = None
    session.save()

    zgl = _make_zgloszenie(doi=None, title="Test Publication Title")
    _make_zpa(zgl, autor, dyscyplina=dyscyplina)

    imported = _make_imported_author(session, autor=autor)

    _prefill_dyscypliny_z_zgloszen(session)

    imported.refresh_from_db()
    assert imported.matched_dyscyplina == dyscyplina


@pytest.mark.django_db
def test_does_not_overwrite_existing(session, autor, dyscyplina):
    """Istniejąca dyscyplina nie jest nadpisywana."""
    other_dyscyplina = baker.make("bpp.Dyscyplina_Naukowa")

    zgl = _make_zgloszenie(doi="10.1234/test")
    _make_zpa(zgl, autor, dyscyplina=other_dyscyplina)

    imported = _make_imported_author(session, autor=autor, dyscyplina=dyscyplina)

    _prefill_dyscypliny_z_zgloszen(session)

    imported.refresh_from_db()
    assert imported.matched_dyscyplina == dyscyplina


@pytest.mark.django_db
def test_skips_unmatched_authors(session, dyscyplina):
    """Autorzy bez matched_autor są pomijani."""
    zgl = _make_zgloszenie(doi="10.1234/test")
    some_autor = baker.make("bpp.Autor")
    _make_zpa(zgl, some_autor, dyscyplina=dyscyplina)

    imported = _make_imported_author(session, autor=None)

    _prefill_dyscypliny_z_zgloszen(session)

    imported.refresh_from_db()
    assert imported.matched_dyscyplina is None


@pytest.mark.django_db
def test_skips_rejected(session, autor, dyscyplina):
    """Status ODRZUCONO jest ignorowany."""
    zgl = _make_zgloszenie(doi="10.1234/test", status=4)
    _make_zpa(zgl, autor, dyscyplina=dyscyplina)

    imported = _make_imported_author(session, autor=autor)

    _prefill_dyscypliny_z_zgloszen(session)

    imported.refresh_from_db()
    assert imported.matched_dyscyplina is None


@pytest.mark.django_db
def test_skips_spam(session, autor, dyscyplina):
    """Status SPAM jest ignorowany."""
    zgl = _make_zgloszenie(doi="10.1234/test", status=5)
    _make_zpa(zgl, autor, dyscyplina=dyscyplina)

    imported = _make_imported_author(session, autor=autor)

    _prefill_dyscypliny_z_zgloszen(session)

    imported.refresh_from_db()
    assert imported.matched_dyscyplina is None


@pytest.mark.django_db
def test_no_matching_zgloszenie(session, autor):
    """Brak dopasowania = brak zmian."""
    imported = _make_imported_author(session, autor=autor)

    _prefill_dyscypliny_z_zgloszen(session)

    imported.refresh_from_db()
    assert imported.matched_dyscyplina is None


@pytest.mark.django_db
def test_fills_jednostka(session, autor, dyscyplina, jednostka):
    """Uzupełnia brakującą jednostkę z zgłoszenia."""
    zgl = _make_zgloszenie(doi="10.1234/test")
    _make_zpa(zgl, autor, dyscyplina=dyscyplina, jednostka=jednostka)

    imported = _make_imported_author(session, autor=autor)

    _prefill_dyscypliny_z_zgloszen(session)

    imported.refresh_from_db()
    assert imported.matched_dyscyplina == dyscyplina
    assert imported.matched_jednostka == jednostka


@pytest.mark.django_db
def test_doi_preferred_over_title(session, autor):
    """DOI ma priorytet nad tytułem."""
    from bpp.models import Autor_Dyscyplina

    dyscyplina_doi = baker.make("bpp.Dyscyplina_Naukowa")
    dyscyplina_title = baker.make("bpp.Dyscyplina_Naukowa")

    # Autor ma obie dyscypliny przypisane na rok 2024
    Autor_Dyscyplina.objects.create(
        autor=autor,
        rok=2024,
        dyscyplina_naukowa=dyscyplina_doi,
        subdyscyplina_naukowa=dyscyplina_title,
    )

    zgl_doi = _make_zgloszenie(
        doi="10.1234/test",
        title="Inny tytuł niż sesja",
    )
    # _make_zpa: Autor_Dyscyplina już istnieje (get_or_create)
    _make_zpa(zgl_doi, autor, dyscyplina=dyscyplina_doi)

    zgl_title = _make_zgloszenie(
        doi=None,
        title="Test Publication Title",
    )
    _make_zpa(zgl_title, autor, dyscyplina=dyscyplina_title)

    imported = _make_imported_author(session, autor=autor)

    _prefill_dyscypliny_z_zgloszen(session)

    imported.refresh_from_db()
    assert imported.matched_dyscyplina == dyscyplina_doi


@pytest.mark.django_db
def test_find_matching_zgloszenie_returns_none_for_short_title(
    session,
):
    """Tytuły krótsze niż 10 znaków nie są dopasowywane."""
    session.normalized_data = {
        "title": "Short",
        "doi": None,
        "year": 2024,
        "authors": [],
    }
    session.save()

    _make_zgloszenie(doi=None, title="Short")

    assert _find_matching_zgloszenie(session) is None
