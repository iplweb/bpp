"""FD#615 i FD#442 — filtry listy sesji importu i zapamiętywanie widoku.

* FD#442: filtry etapu/stanu zakończenia (status, etap błędu) i rekordu
  wynikowego, link do rekordu w tabeli.
* FD#615: szybki filtr „tylko błędy importu” oraz zapamiętanie filtrów
  i sortowania — w adresie URL i w sesji użytkownika; po powrocie na listę
  bez parametrów widok wraca z komunikatem i przyciskiem „Wyczyść”.
"""

from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker

from importer_publikacji.models import ImportSession
from importer_publikacji.views import SESSIONS_SAVED_VIEW_KEY

S = ImportSession.Status
URL = "importer_publikacji:sessions"


def _sesja(user, status, tytul, **kwargs):
    return ImportSession.objects.create(
        created_by=user,
        provider_name="CrossRef",
        identifier=f"10.1/{tytul}",
        raw_data={},
        normalized_data={"title": tytul, "doi": f"10.1/{tytul}"},
        status=status,
        **kwargs,
    )


def _widoczne(response):
    return {s.normalized_data["title"] for s in response.context["sessions"]}


def _get(client, params=None, **headers):
    return client.get(reverse(URL), params or {}, **headers)


@pytest.fixture
def sesje(importer_user):
    rekord = baker.make("bpp.Wydawnictwo_Ciagle", tytul_oryginalny="Rekord FD442")
    ct = ContentType.objects.get_for_model(rekord)
    return {
        "ok": _sesja(
            importer_user,
            S.COMPLETED,
            "ok",
            created_record_content_type=ct,
            created_record_id=rekord.pk,
        ),
        "blad_pobierania": _sesja(
            importer_user, S.IMPORT_FAILED, "blad_pobierania", last_failed_stage="fetch"
        ),
        "blad_tworzenia": _sesja(
            importer_user,
            S.IMPORT_FAILED,
            "blad_tworzenia",
            last_failed_stage="create",
            last_error_message="Problem: brak źródła",
        ),
        "w_toku": _sesja(importer_user, S.SOURCE_MATCHED, "w_toku"),
        "pobieranie": _sesja(importer_user, S.FETCHING, "pobieranie"),
        "anulowana": _sesja(importer_user, S.CANCELLED, "anulowana"),
        "rekord": rekord,
    }


# --- Filtry (FD#442, FD#615) -------------------------------------------------


@pytest.mark.django_db
def test_bez_filtra_statusu_lista_bez_anulowanych(importer_client, sesje):
    """Strażnik: domyślny widok jak dotąd — wszystko poza anulowanymi."""
    assert _widoczne(_get(importer_client)) == {
        "ok",
        "blad_pobierania",
        "blad_tworzenia",
        "w_toku",
        "pobieranie",
    }


@pytest.mark.django_db
def test_filtr_tylko_bledy_importu(importer_client, sesje):
    response = _get(importer_client, {"status": S.IMPORT_FAILED})
    assert _widoczne(response) == {"blad_pobierania", "blad_tworzenia"}
    assert response.context["tylko_bledy"] is True
    assert 'aria-pressed="true"' in response.content.decode()


@pytest.mark.django_db
def test_filtr_statusu_wielokrotny_wybor(importer_client, sesje):
    response = _get(importer_client, {"status": [S.COMPLETED, S.SOURCE_MATCHED]})
    assert _widoczne(response) == {"ok", "w_toku"}
    assert response.context["tylko_bledy"] is False


@pytest.mark.django_db
def test_anulowane_widoczne_po_jawnym_wyborze(importer_client, sesje):
    assert _widoczne(_get(importer_client, {"status": S.CANCELLED})) == {"anulowana"}


@pytest.mark.django_db
def test_filtr_utkniete(importer_client, sesje, settings):
    """„Utknięte” = pobieranie/tworzenie bez postępu dłużej niż próg
    watchdoga; świeże pobieranie się nie łapie."""
    settings.IMPORTER_STALL_TIMEOUT = 180
    stara = _sesja(sesje["ok"].created_by, S.CREATING, "stara")
    ImportSession.objects.filter(pk=stara.pk).update(
        modified=timezone.now() - timedelta(minutes=10)
    )
    assert _widoczne(_get(importer_client, {"status": "utkniete"})) == {"stara"}
    assert _widoczne(
        _get(importer_client, {"status": ["utkniete", S.IMPORT_FAILED]})
    ) == {"stara", "blad_pobierania", "blad_tworzenia"}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "etap,oczekiwane",
    [("fetch", {"blad_pobierania"}), ("create", {"blad_tworzenia"})],
)
def test_filtr_etapu_bledu(importer_client, sesje, etap, oczekiwane):
    assert _widoczne(_get(importer_client, {"etap_bledu": etap})) == oczekiwane


@pytest.mark.django_db
def test_filtr_rekordu_wynikowego(importer_client, sesje):
    assert _widoczne(_get(importer_client, {"rekord": "jest"})) == {"ok"}
    assert _widoczne(_get(importer_client, {"rekord": "brak"})) == {
        "blad_pobierania",
        "blad_tworzenia",
        "w_toku",
        "pobieranie",
    }


@pytest.mark.django_db
def test_tabela_link_do_rekordu_i_etap_bledu(importer_client, sesje):
    content = _get(importer_client).content.decode()
    rekord = sesje["rekord"]
    assert f'href="{rekord.get_absolute_url()}"' in content
    assert reverse("admin:bpp_wydawnictwo_ciagle_change", args=[rekord.pk]) in content
    assert "etap:" in content
    assert "tworzenie rekordu" in content
    assert 'title="Problem: brak źródła"' in content


@pytest.mark.django_db
def test_pola_filtrow_maja_etykiety(importer_client, sesje):
    """Dostępność: każde nowe pole ma etykietę powiązaną przez ``for``."""
    content = _get(importer_client).content.decode()
    for pole in ("status", "etap_bledu", "rekord", "title", "created_by"):
        assert f'<label for="id_{pole}">' in content


# --- Zapamiętywanie widoku (FD#615) --------------------------------------------


@pytest.mark.django_db
def test_powrot_bez_parametrow_przywraca_widok_z_komunikatem(importer_client, sesje):
    _get(importer_client, {"status": S.IMPORT_FAILED, "sort": "status", "title": ""})
    assert importer_client.session[SESSIONS_SAVED_VIEW_KEY] == (
        "status=import_failed&sort=status"
    )

    response = _get(importer_client)

    assert _widoczne(response) == {"blad_pobierania", "blad_tworzenia"}
    assert response.context["sort"] == "status"
    content = response.content.decode()
    assert "Pokazuję zapamiętane filtry i sortowanie" in content
    assert "Status: Błąd importu" in content
    assert "Sortowanie: Status, rosnąco" in content
    assert "wyczysc=1" in content
    # Pasek adresu dostaje kanoniczny URL widoku.
    assert response.context["sessions_url"] == (
        reverse(URL) + "?status=import_failed&sort=status"
    )
    assert "history.replaceState" in content


@pytest.mark.django_db
def test_jawne_parametry_bez_komunikatu(importer_client, sesje):
    _get(importer_client, {"status": S.IMPORT_FAILED})
    response = _get(importer_client, {"rekord": "jest"})
    assert _widoczne(response) == {"ok"}
    assert "Pokazuję zapamiętane" not in response.content.decode()
    assert importer_client.session[SESSIONS_SAVED_VIEW_KEY] == "rekord=jest"


@pytest.mark.django_db
def test_wyczysc_zapomina_widok(importer_client, sesje):
    _get(importer_client, {"status": S.IMPORT_FAILED})

    response = _get(importer_client, {"wyczysc": "1"})
    assert "Pokazuję zapamiętane" not in response.content.decode()
    assert len(_widoczne(response)) == 5
    assert SESSIONS_SAVED_VIEW_KEY not in importer_client.session

    response = _get(importer_client)
    assert "Pokazuję zapamiętane" not in response.content.decode()
    assert len(_widoczne(response)) == 5


@pytest.mark.django_db
def test_reset_pustymi_polami_zapomina_widok(importer_client, sesje):
    """Przycisk „Reset” wysyła formularz z pustymi polami — po nim wejście
    bez parametrów nie przywraca już starych filtrów."""
    _get(importer_client, {"status": S.IMPORT_FAILED})
    _get(importer_client, {"title": "", "doi": "", "etap_bledu": ""})
    assert SESSIONS_SAVED_VIEW_KEY not in importer_client.session
    assert "Pokazuję zapamiętane" not in _get(importer_client).content.decode()


@pytest.mark.django_db
def test_bledny_formularz_nie_nadpisuje_zapamietanego(importer_client, sesje):
    _get(importer_client, {"status": S.IMPORT_FAILED})
    _get(importer_client, {"date_from": "nie-data"})
    assert importer_client.session[SESSIONS_SAVED_VIEW_KEY] == "status=import_failed"


@pytest.mark.django_db
def test_nieznane_sortowanie_ignorowane(importer_client, sesje):
    response = _get(importer_client, {"sort": "password"})
    assert response.context["sort"] == "-created"
    assert SESSIONS_SAVED_VIEW_KEY not in importer_client.session


@pytest.mark.django_db
def test_htmx_zmiana_filtra_podmienia_url(importer_client, sesje):
    response = _get(
        importer_client,
        {"status": S.IMPORT_FAILED, "doi": ""},
        HTTP_HX_REQUEST="true",
        HTTP_HX_TRIGGER="session-filter-form",
    )
    url = urlparse(response["HX-Replace-Url"])
    assert url.path == reverse(URL)
    assert parse_qs(url.query) == {"status": ["import_failed"]}
    assert "HX-Push-Url" not in response


@pytest.mark.django_db
def test_htmx_wejscie_z_paska_przywraca_i_dodaje_wpis_historii(importer_client, sesje):
    """Link „Importy w toku / ostatnie” (HTMX, bez parametrów) przywraca
    zapamiętany widok i wpisuje jego URL do historii przeglądarki."""
    _get(importer_client, {"etap_bledu": "fetch"})
    response = _get(
        importer_client,
        HTTP_HX_REQUEST="true",
        HTTP_HX_TRIGGER="import-sessions-link",
    )
    assert _widoczne(response) == {"blad_pobierania"}
    assert response["HX-Push-Url"] == reverse(URL) + "?etap_bledu=fetch"
    assert "Etap błędu: Pobieranie danych" in response.content.decode()
