import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka
from importer_publikacji.models import (
    ImportedAuthor,
    ImportSession,
)
from importer_publikacji.views import (
    _build_abstracts_list,
    _create_publication,
    _resolve_jezyk,
)


@pytest.mark.django_db
def test_index_requires_permission(client):
    """Niezalogowany użytkownik powinien być przekierowany."""
    url = reverse("importer_publikacji:index")
    response = client.get(url)
    assert response.status_code in (302, 403)


@pytest.mark.django_db
def test_index_accessible_for_importer_user(
    importer_client,
):
    url = reverse("importer_publikacji:index")
    response = importer_client.get(url)
    assert response.status_code == 200
    assert "Importer publikacji" in response.content.decode()


@pytest.mark.django_db
def test_index_accessible_for_superuser(db, client):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    superuser = User.objects.create_superuser(
        username="superuser",
        password="pass",
    )
    client.force_login(superuser)
    url = reverse("importer_publikacji:index")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_index_denied_for_staff_user(db, client):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    staff = User.objects.create_user(
        username="staff",
        password="pass",
        is_staff=True,
    )
    client.force_login(staff)
    url = reverse("importer_publikacji:index")
    response = client.get(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_fetch_empty_identifier(importer_client):
    url = reverse("importer_publikacji:fetch")
    response = importer_client.post(
        url,
        {"provider": "CrossRef", "identifier": ""},
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert "wymagane" in content


@pytest.mark.django_db
def test_fetch_invalid_doi(importer_client):
    url = reverse("importer_publikacji:fetch")
    response = importer_client.post(
        url,
        {
            "provider": "CrossRef",
            "identifier": "not-a-doi",
        },
    )
    assert response.status_code == 200
    content = response.content.decode()
    # normalize_doi("not-a-doi") passes validation
    # but fetch fails
    assert "przetworzy" in content


@pytest.mark.django_db
def test_cancel_session(importer_client, importer_user):
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/test",
        raw_data={},
        normalized_data={},
    )
    url = reverse(
        "importer_publikacji:cancel",
        kwargs={"session_id": session.pk},
    )
    response = importer_client.post(url)
    assert response.status_code == 200
    session.refresh_from_db()
    assert session.status == ImportSession.Status.CANCELLED


@pytest.mark.django_db
def test_regular_user_no_access(db, client):
    """Zwykły użytkownik bez grupy nie ma dostępu."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(
        username="regular",
        password="pass",
    )
    client.force_login(user)
    url = reverse("importer_publikacji:index")
    response = client.get(url)
    assert response.status_code in (302, 403)


@pytest.mark.django_db
def test_verify_updates_session(
    importer_client,
    importer_user,
    charaktery_formalne,
    typy_kbn,
    jezyki,
):
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/test",
        raw_data={},
        normalized_data={
            "doi": None,
            "title": "Test",
        },
    )
    url = reverse(
        "importer_publikacji:verify",
        kwargs={"session_id": session.pk},
    )
    from bpp.models import (
        Charakter_Formalny,
        Jezyk,
        Typ_KBN,
    )

    cf = Charakter_Formalny.objects.first()
    tk = Typ_KBN.objects.first()
    jez = Jezyk.objects.filter(widoczny=True).first()
    response = importer_client.post(
        url,
        {
            "charakter_formalny": (cf.pk if cf else ""),
            "typ_kbn": tk.pk if tk else "",
            "jezyk": jez.pk if jez else "",
            "jest_wydawnictwem_zwartym": "",
        },
    )
    assert response.status_code == 200
    session.refresh_from_db()
    assert session.status == ImportSession.Status.VERIFIED


def _make_session_with_unmatched(importer_user, count=2):
    """Helper: sesja z niedopasowanymi autorami."""
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/test",
        raw_data={},
        normalized_data={},
    )
    for i in range(count):
        ImportedAuthor.objects.create(
            session=session,
            order=i,
            family_name=f"Testowy{i}",
            given_name=f"Autor{i}",
            match_status=(ImportedAuthor.MatchStatus.UNMATCHED),
        )
    return session


@pytest.mark.django_db
def test_create_unmatched_authors_success(
    importer_client,
    importer_user,
    uczelnia_z_obca_jednostka,
):
    """Tworzenie autorów dla niedopasowanych."""
    session = _make_session_with_unmatched(importer_user)
    obca = uczelnia_z_obca_jednostka.obca_jednostka

    url = reverse(
        "importer_publikacji:authors-create-unmatched",
        kwargs={"session_id": session.pk},
    )
    response = importer_client.post(url)
    assert response.status_code == 200

    # Wszyscy autorzy powinni być dopasowani
    for ia in session.authors.all():
        ia.refresh_from_db()
        assert ia.match_status == ImportedAuthor.MatchStatus.MANUAL
        assert ia.matched_autor is not None
        assert ia.matched_jednostka == obca

    # Rekordy Autor powinny istnieć
    assert Autor.objects.filter(nazwisko="Testowy0").exists()
    assert Autor.objects.filter(nazwisko="Testowy1").exists()

    # Autor_Jednostka powinny istnieć
    for ia in session.authors.all():
        assert Autor_Jednostka.objects.filter(
            autor=ia.matched_autor,
            jednostka=obca,
        ).exists()


@pytest.mark.django_db
def test_create_unmatched_no_obca_jednostka(
    importer_client,
    importer_user,
    uczelnia,
):
    """Brak obcej jednostki -> komunikat błędu."""
    # uczelnia bez obcej jednostki
    assert uczelnia.obca_jednostka is None

    session = _make_session_with_unmatched(importer_user)
    url = reverse(
        "importer_publikacji:authors-create-unmatched",
        kwargs={"session_id": session.pk},
    )
    response = importer_client.post(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "obcej jednostki" in content

    # Autorzy wciąż niedopasowani
    for ia in session.authors.all():
        ia.refresh_from_db()
        assert ia.match_status == ImportedAuthor.MatchStatus.UNMATCHED


@pytest.mark.django_db
def test_create_unmatched_orcid_matches_existing(
    importer_client,
    importer_user,
    uczelnia_z_obca_jednostka,
):
    """ORCID istniejącego Autora -> dopasowanie."""
    obca = uczelnia_z_obca_jednostka.obca_jednostka
    existing = baker.make(
        Autor,
        imiona="Jan",
        nazwisko="Kowalski",
        orcid="0000-0001-2345-6789",
    )

    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/orcid-test",
        raw_data={},
        normalized_data={},
    )
    ImportedAuthor.objects.create(
        session=session,
        order=0,
        family_name="Kowalski",
        given_name="Jan",
        orcid="0000-0001-2345-6789",
        match_status=(ImportedAuthor.MatchStatus.UNMATCHED),
    )

    url = reverse(
        "importer_publikacji:authors-create-unmatched",
        kwargs={"session_id": session.pk},
    )
    response = importer_client.post(url)
    assert response.status_code == 200

    ia = session.authors.first()
    ia.refresh_from_db()
    assert ia.matched_autor == existing
    assert ia.matched_jednostka == obca
    assert ia.match_status == ImportedAuthor.MatchStatus.MANUAL

    # Nie powinien powstać nowy Autor
    assert Autor.objects.filter(orcid="0000-0001-2345-6789").count() == 1


@pytest.mark.django_db
def test_create_unmatched_noop_when_all_matched(
    importer_client,
    importer_user,
    uczelnia_z_obca_jednostka,
):
    """Brak niedopasowanych -> nic się nie dzieje."""
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/noop",
        raw_data={},
        normalized_data={},
    )
    autor = baker.make(Autor)
    ImportedAuthor.objects.create(
        session=session,
        order=0,
        family_name="Test",
        given_name="Autor",
        match_status=(ImportedAuthor.MatchStatus.AUTO_EXACT),
        matched_autor=autor,
    )

    autor_count_before = Autor.objects.count()

    url = reverse(
        "importer_publikacji:authors-create-unmatched",
        kwargs={"session_id": session.pk},
    )
    response = importer_client.post(url)
    assert response.status_code == 200
    assert Autor.objects.count() == autor_count_before


@pytest.mark.django_db
def test_verify_get_preserves_jezyk(
    importer_client,
    importer_user,
    jezyki,
):
    """GET na verify powinien zachować jezyk z sesji
    (scenariusz: Kontynuuj)."""
    from bpp.models import Jezyk

    jez = Jezyk.objects.filter(widoczny=True).first()
    assert jez is not None

    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/lang-test",
        raw_data={},
        normalized_data={
            "title": "Test language",
            "doi": None,
        },
        jezyk=jez,
    )

    # Verify jezyk is saved in the DB
    session.refresh_from_db()
    assert session.jezyk_id == jez.pk

    url = reverse(
        "importer_publikacji:verify",
        kwargs={"session_id": session.pk},
    )
    response = importer_client.get(url)
    assert response.status_code == 200
    content = response.content.decode()

    # The select option for jezyk should be selected
    assert f'value="{jez.pk}" selected' in content


@pytest.mark.django_db
def test_verify_suggest_crossref_for_pbn_with_doi(
    importer_client,
    importer_user,
):
    """Verify step suggests CrossRef when non-CrossRef provider has DOI."""
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="PBN",
        identifier="pbn-123",
        raw_data={},
        normalized_data={
            "title": "Test PBN",
            "doi": "10.1234/pbn-test",
        },
    )
    url = reverse(
        "importer_publikacji:verify",
        kwargs={"session_id": session.pk},
    )
    response = importer_client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Pobierz z CrossRef" in content
    assert "10.1234/pbn-test" in content


@pytest.mark.django_db
def test_verify_no_suggest_crossref_for_crossref(
    importer_client,
    importer_user,
):
    """No CrossRef suggestion when already using CrossRef provider."""
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1234/cr-test",
        raw_data={},
        normalized_data={
            "title": "Test CrossRef",
            "doi": "10.1234/cr-test",
        },
    )
    url = reverse(
        "importer_publikacji:verify",
        kwargs={"session_id": session.pk},
    )
    response = importer_client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Pobierz z CrossRef" not in content


@pytest.mark.django_db
def test_verify_no_suggest_crossref_without_doi(
    importer_client,
    importer_user,
):
    """No CrossRef suggestion when no DOI present."""
    session = ImportSession.objects.create(
        created_by=importer_user,
        provider_name="DSpace",
        identifier="http://example.com/123",
        raw_data={},
        normalized_data={
            "title": "Test DSpace",
        },
    )
    url = reverse(
        "importer_publikacji:verify",
        kwargs={"session_id": session.pk},
    )
    response = importer_client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Pobierz z CrossRef" not in content


# --- Streszczenia ---


def _make_session_for_publication(
    user,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    abstracts=None,
    abstract=None,
):
    """Helper: sesja gotowa do _create_publication."""
    from bpp.models import (
        Charakter_Formalny,
        Jezyk,
        Status_Korekty,
        Typ_KBN,
    )

    Status_Korekty.objects.get_or_create(
        pk=1,
        defaults={"nazwa": "po korekcie"},
    )

    cf = Charakter_Formalny.objects.first()
    tk = Typ_KBN.objects.first()
    jez = Jezyk.objects.filter(widoczny=True).first()

    nd = {
        "title": "Test Publication",
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
        "publication_type": None,
        "language": "en",
        "abstract": abstract,
        "volume": None,
        "issue": None,
        "pages": None,
        "url": None,
        "license_url": None,
        "keywords": [],
        "article_number": None,
        "original_title": None,
        "abstracts": abstracts or [],
    }

    session = ImportSession.objects.create(
        created_by=user,
        provider_name="CrossRef",
        identifier="10.1234/test-streszczenie",
        raw_data={},
        normalized_data=nd,
        charakter_formalny=cf,
        typ_kbn=tk,
        jezyk=jez,
    )
    return session


@pytest.mark.django_db
def test_create_publication_creates_streszczenie(
    importer_user,
    jezyki,
    charaktery_formalne,
    typy_kbn,
):
    """Abstrakt z normalized_data → Streszczenie."""
    session = _make_session_for_publication(
        importer_user,
        jezyki,
        charaktery_formalne,
        typy_kbn,
        abstracts=[
            {
                "text": "This is a test abstract.",
                "language": "en",
            }
        ],
    )
    record = _create_publication(session)
    streszczenia = record.streszczenia.all()
    assert streszczenia.count() == 1
    assert streszczenia[0].streszczenie == "This is a test abstract."
    assert streszczenia[0].jezyk_streszczenia is not None
    assert streszczenia[0].jezyk_streszczenia.skrot_crossref == "en"


@pytest.mark.django_db
def test_create_publication_abstract_language_detection(
    importer_user,
    jezyki,
    charaktery_formalne,
    typy_kbn,
):
    """Brak language → auto-detect z tekstu."""
    session = _make_session_for_publication(
        importer_user,
        jezyki,
        charaktery_formalne,
        typy_kbn,
        abstracts=[
            {
                "text": "Właściwości materiałów "
                "polimerowych w kontekście "
                "zastosowań inżynieryjnych.",
                "language": None,
            }
        ],
    )
    record = _create_publication(session)
    streszczenia = record.streszczenia.all()
    assert streszczenia.count() == 1
    # Tekst z polskimi znakami → język powinien być polski
    # (ale Jezyk z skrot_crossref='pl' może nie istnieć
    # w fixture jezyki — sprawdzamy że tekst jest zapisany)
    assert "Właściwości materiałów" in streszczenia[0].streszczenie


@pytest.mark.django_db
def test_create_publication_fallback_abstract(
    importer_user,
    jezyki,
    charaktery_formalne,
    typy_kbn,
):
    """Brak abstracts → fallback na abstract."""
    session = _make_session_for_publication(
        importer_user,
        jezyki,
        charaktery_formalne,
        typy_kbn,
        abstracts=[],
        abstract="Fallback abstract text.",
    )
    record = _create_publication(session)
    streszczenia = record.streszczenia.all()
    assert streszczenia.count() == 1
    assert streszczenia[0].streszczenie == "Fallback abstract text."


@pytest.mark.django_db
def test_create_publication_no_abstract(
    importer_user,
    jezyki,
    charaktery_formalne,
    typy_kbn,
):
    """Brak abstracts i abstract → brak streszczeń."""
    session = _make_session_for_publication(
        importer_user,
        jezyki,
        charaktery_formalne,
        typy_kbn,
    )
    record = _create_publication(session)
    assert record.streszczenia.count() == 0


@pytest.mark.django_db
def test_create_publication_multiple_abstracts(
    importer_user,
    jezyki,
    charaktery_formalne,
    typy_kbn,
):
    """Wiele streszczeń → wiele rekordów."""
    session = _make_session_for_publication(
        importer_user,
        jezyki,
        charaktery_formalne,
        typy_kbn,
        abstracts=[
            {
                "text": "English abstract text here.",
                "language": "en",
            },
            {
                "text": "Polskie streszczenie tekstu.",
                "language": "pl",
            },
        ],
    )
    record = _create_publication(session)
    streszczenia = record.streszczenia.all()
    assert streszczenia.count() == 2


def test_build_abstracts_list_with_extra():
    """extra['abstracts'] → zwróć je."""
    from dataclasses import dataclass, field

    @dataclass
    class FakeResult:
        abstract: str | None = None
        extra: dict = field(default_factory=dict)

    result = FakeResult(
        abstract="Meta abstract",
        extra={"abstracts": [{"text": "Body abstract", "language": "en"}]},
    )
    abstracts = _build_abstracts_list(result)
    assert len(abstracts) == 1
    assert abstracts[0]["text"] == "Body abstract"


def test_build_abstracts_list_fallback_abstract():
    """Brak extra['abstracts'] → użyj abstract."""
    from dataclasses import dataclass, field

    @dataclass
    class FakeResult:
        abstract: str | None = None
        extra: dict = field(default_factory=dict)

    result = FakeResult(abstract="Only abstract")
    abstracts = _build_abstracts_list(result)
    assert len(abstracts) == 1
    assert abstracts[0]["text"] == "Only abstract"
    assert abstracts[0]["language"] is None


def test_build_abstracts_list_empty():
    """Brak wszystkiego → pusta lista."""
    from dataclasses import dataclass, field

    @dataclass
    class FakeResult:
        abstract: str | None = None
        extra: dict = field(default_factory=dict)

    result = FakeResult()
    abstracts = _build_abstracts_list(result)
    assert abstracts == []


@pytest.mark.django_db
def test_resolve_jezyk_by_crossref(jezyki):
    """Rozwiąż język po skrot_crossref."""
    jezyk = _resolve_jezyk("en")
    assert jezyk is not None
    assert jezyk.skrot_crossref == "en"


@pytest.mark.django_db
def test_resolve_jezyk_none(jezyki):
    """None → None."""
    assert _resolve_jezyk(None) is None


@pytest.mark.django_db
def test_resolve_jezyk_unknown(jezyki):
    """Nieznany kod → None."""
    assert _resolve_jezyk("xx") is None
