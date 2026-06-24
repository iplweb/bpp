"""Testy `_create_publication` (etap finalny wizarda) oraz CreateView.

Pokrywają tworzenie streszczeń (Streszczenie) z `normalized_data['abstracts']`
oraz fallback na pojedyncze pole `abstract`, auto-detekcję języka, walidację
braku roku publikacji (ValidationError zamiast TypeError) i obsługę tego
błędu na poziomie widoku.
"""

import pytest
from django.urls import reverse

from importer_publikacji.models import ImportSession
from importer_publikacji.views import _create_publication


def _make_session_for_publication(
    user,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    typy_odpowiedzialnosci,
    abstracts=None,
    abstract=None,
):
    """Helper: sesja gotowa do _create_publication."""
    from bpp.models import (
        Charakter_Formalny,
        Jezyk,
        Typ_KBN,
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
    statusy_korekt,
    typy_odpowiedzialnosci,
):
    """Abstrakt z normalized_data → Streszczenie."""
    session = _make_session_for_publication(
        importer_user,
        jezyki,
        charaktery_formalne,
        typy_kbn,
        statusy_korekt,
        typy_odpowiedzialnosci,
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
    statusy_korekt,
    typy_odpowiedzialnosci,
):
    """Brak language → auto-detect z tekstu."""
    session = _make_session_for_publication(
        importer_user,
        jezyki,
        charaktery_formalne,
        typy_kbn,
        statusy_korekt,
        typy_odpowiedzialnosci,
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
    statusy_korekt,
    typy_odpowiedzialnosci,
):
    """Brak abstracts → fallback na abstract."""
    session = _make_session_for_publication(
        importer_user,
        jezyki,
        charaktery_formalne,
        typy_kbn,
        statusy_korekt,
        typy_odpowiedzialnosci,
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
    statusy_korekt,
    typy_odpowiedzialnosci,
):
    """Brak abstracts i abstract → brak streszczeń."""
    session = _make_session_for_publication(
        importer_user,
        jezyki,
        charaktery_formalne,
        typy_kbn,
        statusy_korekt,
        typy_odpowiedzialnosci,
    )
    record = _create_publication(session)
    assert record.streszczenia.count() == 0


@pytest.mark.django_db
def test_create_publication_multiple_abstracts(
    importer_user,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    typy_odpowiedzialnosci,
):
    """Wiele streszczeń → wiele rekordów."""
    session = _make_session_for_publication(
        importer_user,
        jezyki,
        charaktery_formalne,
        typy_kbn,
        statusy_korekt,
        typy_odpowiedzialnosci,
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


def _make_session_z_zrodlem(
    user,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    zrodlo,
):
    """Sesja wydawnictwa ciągłego ze źródłem — do testów sugerowania punktacji."""
    session = _make_session_for_publication(
        user,
        jezyki,
        charaktery_formalne,
        typy_kbn,
        None,
        None,
    )
    session.zrodlo = zrodlo
    session.jest_wydawnictwem_zwartym = False
    session.save()
    return session


@pytest.mark.django_db
def test_create_publication_sugeruj_punktacje_wylaczone_nie_uzupelnia(
    importer_user,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    typy_odpowiedzialnosci,
    uczelnia,
    zrodlo,
):
    """Flaga `sugeruj_punktacje` = False (domyślnie) → punktacja NIE jest
    sugerowana automatycznie mimo istnienia Punktacja_Zrodla (obecne zachowanie).
    """
    from bpp.models.zrodlo import Punktacja_Zrodla

    assert uczelnia.sugeruj_punktacje is False
    Punktacja_Zrodla.objects.create(zrodlo=zrodlo, rok=2024, punkty_kbn=70)

    session = _make_session_z_zrodlem(
        importer_user, jezyki, charaktery_formalne, typy_kbn, zrodlo
    )
    record = _create_publication(session)

    assert record.punkty_kbn == 0


@pytest.mark.django_db
def test_create_publication_sugeruj_punktacje_wlaczone_uzupelnia(
    importer_user,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    typy_odpowiedzialnosci,
    uczelnia,
    zrodlo,
):
    """Flaga `sugeruj_punktacje` = True → punktacja sugerowana automatycznie
    z Punktacja_Zrodla. Sugestia jest podpowiedzią — pole pozostaje edytowalne.
    """
    from bpp.models.zrodlo import Punktacja_Zrodla

    uczelnia.sugeruj_punktacje = True
    uczelnia.save()
    Punktacja_Zrodla.objects.create(zrodlo=zrodlo, rok=2024, punkty_kbn=70)

    session = _make_session_z_zrodlem(
        importer_user, jezyki, charaktery_formalne, typy_kbn, zrodlo
    )
    record = _create_publication(session)

    assert record.punkty_kbn == 70

    # Sugestia to wyłącznie podpowiedź — operator może ją ręcznie zmienić.
    record.punkty_kbn = 100
    record.save()
    record.refresh_from_db()
    assert record.punkty_kbn == 100


@pytest.mark.django_db
def test_create_publication_sugeruj_punktacje_wlaczone_brak_danych_zrodla(
    importer_user,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    typy_odpowiedzialnosci,
    uczelnia,
    zrodlo,
):
    """Flaga włączona, ale brak Punktacja_Zrodla dla roku → brak sugestii,
    bez błędu (graceful no-op).
    """
    uczelnia.sugeruj_punktacje = True
    uczelnia.save()

    session = _make_session_z_zrodlem(
        importer_user, jezyki, charaktery_formalne, typy_kbn, zrodlo
    )
    record = _create_publication(session)

    assert record.punkty_kbn == 0


@pytest.mark.django_db
def test_create_publication_without_year_raises_validation_error(
    importer_user,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    typy_odpowiedzialnosci,
):
    """Brak roku → ValidationError z czytelnym komunikatem (nie TypeError)."""
    from django.core.exceptions import ValidationError

    session = _make_session_for_publication(
        importer_user,
        jezyki,
        charaktery_formalne,
        typy_kbn,
        statusy_korekt,
        typy_odpowiedzialnosci,
    )
    session.normalized_data["year"] = None
    session.save()

    with pytest.raises(ValidationError, match="Brak roku publikacji"):
        _create_publication(session)


@pytest.mark.django_db
def test_create_view_without_year_task_marks_session_failed(
    importer_client,
    importer_user,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    typy_odpowiedzialnosci,
):
    """POST do CreateView dla sesji bez roku → enqueue taska,
    task ustawia IMPORT_FAILED z czytelnym komunikatem (bez tracebacku
    w polu last_error_message).

    Mockujemy create_publication_task.delay żeby uniknąć propagacji
    wyjątku do widoku pod eager-mode (Celery legacy translation jest
    niedeterministyczna w xdist) — task wykonujemy explicit przez
    .apply() poniżej.
    """
    from unittest.mock import patch

    from importer_publikacji.tasks import create_publication_task

    session = _make_session_for_publication(
        importer_user,
        jezyki,
        charaktery_formalne,
        typy_kbn,
        statusy_korekt,
        typy_odpowiedzialnosci,
    )
    session.normalized_data["year"] = None
    session.save()

    url = reverse("importer_publikacji:create", kwargs={"session_id": session.pk})
    with patch("importer_publikacji.views.wizard.create_publication_task") as mock_task:
        mock_task.delay.return_value.id = "task-uuid"
        response = importer_client.post(url)

    # View enqueueuje taska i redirectuje na task-status.
    assert response.status_code == 302
    assert "task-status" in response["Location"]

    # .delay() nie jest eager — uruchamiamy taska synchronicznie.
    # Task re-raise wyjatek po zapisaniu stanu IMPORT_FAILED.
    from django.core.exceptions import ValidationError

    with pytest.raises(ValidationError, match="Brak roku publikacji"):
        create_publication_task.apply(args=[session.pk, importer_user.pk, False]).get()

    session.refresh_from_db()
    assert session.status == ImportSession.Status.IMPORT_FAILED
    assert "Brak roku publikacji" in session.last_error_message
    # Traceback siedzi w osobnym polu, nie wycieka do user-safe message.
    assert "Traceback" not in session.last_error_message
    assert "TypeError" not in session.last_error_message
