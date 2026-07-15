"""Testy kaflowej strony głównej importera (``IndexView``):

- kafle dla wszystkich zarejestrowanych dostawców (etykiety + ikony),
- deep-link ``?provider=<name>`` renderujący formularz fetch tego
  dostawcy — zarówno jako pełna strona, jak i partial HTMX (ten sam URL,
  który kafel pushuje przez ``hx-push-url``, musi się tak samo renderować
  przy Back/Forward/refreshu),
- pasek „importy w toku" (licznik + link do pełnej listy sesji).
"""

import pytest
from django.urls import reverse

from importer_publikacji.models import ImportSession, MultipleWorksImport
from importer_publikacji.providers import get_providers_metadata


@pytest.mark.django_db
def test_landing_shows_tile_per_provider(importer_client):
    """Strona główna (bez ``?provider=``) pokazuje kafel dla KAŻDEGO
    zarejestrowanego dostawcy — z widocznym ``choice_label``."""
    url = reverse("importer_publikacji:index")
    response = importer_client.get(url)

    assert response.status_code == 200
    content = response.content.decode()

    metadata = get_providers_metadata()
    assert metadata, "Brak zarejestrowanych providerów — test nic nie sprawdza."
    for meta in metadata.values():
        assert meta["choice_label"] in content
        assert meta["icon"] in content


@pytest.mark.django_db
def test_landing_tile_links_to_provider_query_param(importer_client):
    """Kafel dostawcy musi HTMX-owo celować w ``?provider=<name>`` z
    ``hx-push-url`` — to jest URL, który później musi się renderować
    identycznie przy bezpośrednim wejściu (deep-link/refresh/Back)."""
    url = reverse("importer_publikacji:index")
    response = importer_client.get(url)
    content = response.content.decode()

    assert 'hx-push-url="true"' in content
    assert "?provider=CrossRef" in content


@pytest.mark.django_db
def test_provider_deep_link_renders_fetch_form_full_page(importer_client):
    """``?provider=CrossRef`` jako zwykły GET (bez HTMX) renderuje pełną
    stronę z formularzem fetch dla CrossRef — deep-link/refresh musi
    działać tak samo jak kliknięcie kafla."""
    url = reverse("importer_publikacji:index") + "?provider=CrossRef"
    response = importer_client.get(url)

    assert response.status_code == 200
    content = response.content.decode()
    assert 'value="CrossRef"' in content
    assert "Identyfikator" in content
    # Pełna strona (nie sam fragment) — ma layout bazowy z stopką/topbarem.
    assert "importer-wizard" in content


@pytest.mark.django_db
def test_provider_deep_link_renders_fetch_form_htmx_partial(importer_client):
    """To samo ``?provider=CrossRef`` żądane przez HTMX zwraca sam fragment
    (bez pełnego layoutu) — tak jak przy kliknięciu kafla."""
    url = reverse("importer_publikacji:index") + "?provider=CrossRef"
    response = importer_client.get(url, HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    content = response.content.decode()
    assert 'value="CrossRef"' in content
    # Fragment HTMX nie zawiera pełnego dokumentu.
    assert "<html" not in content.lower()


@pytest.mark.django_db
def test_provider_deep_link_preselects_identifier(importer_client):
    """``?provider=`` + ``?identifier=`` (używane przez linki adminowe —
    „Dodaj z CrossRef API", „Użyj importera") muszą nadal prefillować pole
    identyfikatora."""
    url = (
        reverse("importer_publikacji:index")
        + "?provider=CrossRef&identifier=10.1234%2Ftest"
    )
    response = importer_client.get(url)
    content = response.content.decode()
    assert "10.1234/test" in content


@pytest.mark.django_db
def test_in_progress_bar_shows_zero_when_no_sessions(importer_client):
    """Brak sesji/paczek → pasek informuje, że nie ma importów w toku,
    zamiast pokazywać licznik."""
    url = reverse("importer_publikacji:index")
    response = importer_client.get(url)
    content = response.content.decode()
    assert "Brak importów w toku." in content


@pytest.mark.django_db
def test_in_progress_bar_counts_active_sessions(importer_client, importer_user):
    """Sesje w trakcie (nie COMPLETED/CANCELLED/IMPORT_FAILED) wchodzą do
    licznika na pasku; zakończone/anulowane/martwe — nie."""
    ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1/a",
        status=ImportSession.Status.FETCHED,
        raw_data={},
        normalized_data={},
    )
    ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1/b",
        status=ImportSession.Status.VERIFIED,
        raw_data={},
        normalized_data={},
    )
    ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1/done",
        status=ImportSession.Status.COMPLETED,
        raw_data={},
        normalized_data={},
    )
    ImportSession.objects.create(
        created_by=importer_user,
        provider_name="CrossRef",
        identifier="10.1/cancelled",
        status=ImportSession.Status.CANCELLED,
        raw_data={},
        normalized_data={},
    )

    url = reverse("importer_publikacji:index")
    response = importer_client.get(url)
    content = response.content.decode()

    assert "Masz <strong>2</strong>" in content
    assert "importy w toku." in content


@pytest.mark.django_db
def test_in_progress_bar_links_to_sessions_list(importer_client):
    """Pasek linkuje (HTMX, z push-url) do pełnej listy sesji
    (``SessionListView``), a nie do pełnego DataTable na landingu."""
    url = reverse("importer_publikacji:index")
    response = importer_client.get(url)
    content = response.content.decode()

    sessions_url = reverse("importer_publikacji:sessions")
    assert 'id="import-sessions-link"' in content
    assert sessions_url in content
    # Landing NIE ma dumpować pełnej tabeli sesji (tylko slim bar).
    assert 'id="sessions-table"' not in content


@pytest.mark.django_db
def test_sessions_list_full_page_shows_table_and_back_link(importer_client):
    """Samodzielna strona listy sesji (link z paska) pokazuje pełną tabelę
    ORAZ link powrotny do landingu (bo to jej WŁASNY pushed URL, patrz
    ``SessionListView``)."""
    url = reverse("importer_publikacji:sessions")
    response = importer_client.get(url)

    assert response.status_code == 200
    content = response.content.decode()
    assert "Sesje importu" in content
    assert "Powrót do importera" in content


@pytest.mark.django_db
def test_in_progress_bar_counts_unfinished_batch(importer_client, importer_user):
    """Paczka (``MultipleWorksImport``) z niedokończonymi wpisami też liczy
    się do „importów w toku"."""
    from importer_publikacji.models import MultipleWorksImportEntry

    batch = MultipleWorksImport.objects.create(
        created_by=importer_user,
        provider_name="BibTeX",
        raw_input="@article{a,}\n@article{b,}",
    )
    MultipleWorksImportEntry.objects.bulk_create(
        [
            MultipleWorksImportEntry(parent=batch, order=0, raw_bibtex="@article{a,}"),
            MultipleWorksImportEntry(parent=batch, order=1, raw_bibtex="@article{b,}"),
        ]
    )

    url = reverse("importer_publikacji:index")
    response = importer_client.get(url)
    content = response.content.decode()

    assert "Masz <strong>1</strong>" in content
    assert "import w toku." in content
