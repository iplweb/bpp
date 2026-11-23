"""FD#483: import wielu DOI naraz.

Wywołania sieciowe (CrossRef, PBN) są zamockowane: dostawca przez
``importer_publikacji.tasks.get_provider``, klient PBN przez
``importer_publikacji.wiele_doi.klient_pbn``. Celery działa w testach
w trybie eager, więc POST formularza od razu wykonuje pobieranie.
"""

import logging
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
import requests
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from importer_publikacji.forms import WieleDoiForm
from importer_publikacji.models import (
    ImportSession,
    MultipleWorksImport,
    MultipleWorksImportEntry,
)
from importer_publikacji.providers import FetchedPublication
from importer_publikacji.tasks import pobierz_paczke_doi_task
from importer_publikacji.wiele_doi import parsuj_liste_doi
from pbn_api.exceptions import HttpException

URL_FORMULARZA = reverse("importer_publikacji:wiele-doi")


def _url_paczki(batch):
    return reverse("importer_publikacji:batch-detail", kwargs={"batch_id": batch.pk})


class _FalszywyDostawca:
    """Zamiennik dostawcy CrossRef: ``zachowania`` mapuje DOI na wyjątek do
    rzucenia albo ``None`` (dostawca nie zna DOI); pozostałe DOI zwracają
    poprawne dane."""

    def __init__(self, zachowania=None):
        self.zachowania = zachowania or {}
        self.pobrane = []

    def fetch(self, identifier):
        self.pobrane.append(identifier)
        if identifier in self.zachowania:
            wynik = self.zachowania[identifier]
            if isinstance(wynik, Exception):
                raise wynik
            return wynik
        return FetchedPublication(
            raw_data={"DOI": identifier, "type": "journal-article"},
            title=f"Praca o numerze {identifier}",
            doi=identifier,
            year=2025,
            publication_type="journal-article",
            language="en",
        )


@pytest.fixture
def dostawca():
    falszywy = _FalszywyDostawca()
    with patch("importer_publikacji.tasks.get_provider", return_value=falszywy):
        yield falszywy


@pytest.fixture
def pbn():
    """Klient PBN, który domyślnie nie zna żadnego DOI (HTTP 404)."""
    client = MagicMock()
    client.get_publication_by_doi.side_effect = HttpException(404, "/doi", "")
    with patch("importer_publikacji.wiele_doi.klient_pbn", return_value=client):
        yield client


# --- parsowanie listy -------------------------------------------------------


def test_parsowanie_przyjmuje_rozne_postaci_doi():
    lista = parsuj_liste_doi(
        "10.1234/abc\n"
        "  https://doi.org/10.1234/DEF  \n"
        "\n"
        "http://dx.doi.org/10.1234/ghi?utm=1\n"
        "doi:10.1234/jkl\n"
        "https://www.doi.org/10.1234/mno\r\n"
    )
    assert lista.doi == [
        "10.1234/abc",
        "10.1234/def",
        "10.1234/ghi",
        "10.1234/jkl",
        "10.1234/mno",
    ]
    assert lista.nierozpoznane == []
    assert lista.duplikaty == 0


def test_parsowanie_pomija_duplikaty_bez_wzgledu_na_postac_i_wielkosc_liter():
    lista = parsuj_liste_doi(
        "10.1234/abc\nhttps://doi.org/10.1234/ABC\n10.1234/abc\n10.1234/inne"
    )
    assert lista.doi == ["10.1234/abc", "10.1234/inne"]
    assert lista.duplikaty == 2


def test_parsowanie_kilka_doi_w_jednej_linii():
    lista = parsuj_liste_doi("10.1234/a, 10.1234/b\t10.1234/c;")
    assert lista.doi == ["10.1234/a", "10.1234/b", "10.1234/c"]


def test_parsowanie_linia_bez_doi_nie_znika():
    lista = parsuj_liste_doi("10.1234/abc\nto nie jest numer\n12345")
    assert lista.doi == ["10.1234/abc"]
    assert lista.nierozpoznane == ["to nie jest numer", "12345"]


@pytest.mark.parametrize("tekst", ["", "   \n\n  ", None])
def test_parsowanie_pustego_tekstu(tekst):
    lista = parsuj_liste_doi(tekst)
    assert lista.doi == []
    assert lista.nierozpoznane == []


# --- formularz i limit ------------------------------------------------------


def test_formularz_odrzuca_liste_bez_doi():
    form = WieleDoiForm({"lista_doi": "nic tu nie ma"})
    assert not form.is_valid()
    assert "Nie rozpoznano żadnego numeru DOI" in form.errors["lista_doi"][0]


def test_formularz_limit(settings):
    settings.IMPORTER_WIELE_DOI_LIMIT = 3
    ok = WieleDoiForm({"lista_doi": "10.1234/a\n10.1234/b\n10.1234/c\n10.1234/A"})
    # Duplikat nie liczy się do limitu.
    assert ok.is_valid(), ok.errors

    za_duzo = WieleDoiForm({"lista_doi": "10.1234/a\n10.1234/b\n10.1234/c\n10.1234/d"})
    assert not za_duzo.is_valid()
    blad = za_duzo.errors["lista_doi"][0]
    assert "4 różnych numerów DOI" in blad
    assert "najwyżej 3" in blad


@pytest.mark.django_db
def test_post_ponad_limit_niczego_nie_tworzy(importer_client, settings, dostawca):
    settings.IMPORTER_WIELE_DOI_LIMIT = 2
    resp = importer_client.post(
        URL_FORMULARZA, {"lista_doi": "10.1234/a\n10.1234/b\n10.1234/c"}
    )
    assert resp.status_code == 200
    assert "najwyżej 2" in resp.content.decode()
    assert MultipleWorksImport.objects.count() == 0
    assert ImportSession.objects.count() == 0
    assert dostawca.pobrane == []


# --- tworzenie paczki i sesji ----------------------------------------------


@pytest.mark.django_db
def test_post_tworzy_paczke_i_zwykla_sesje_dla_kazdego_doi(
    importer_client, importer_user, dostawca, pbn
):
    resp = importer_client.post(
        URL_FORMULARZA,
        {"lista_doi": "10.1234/a\nhttps://doi.org/10.1234/B\n10.1234/a\nśmieć"},
    )
    batch = MultipleWorksImport.objects.get()
    assert resp.status_code == 302
    assert resp["Location"] == _url_paczki(batch)
    assert batch.provider_name == "CrossRef"
    assert batch.jest_lista_doi
    assert batch.created_by == importer_user

    wpisy = list(batch.entries.order_by("order"))
    assert [w.raw_bibtex for w in wpisy] == ["10.1234/a", "10.1234/b", "śmieć"]
    assert wpisy[2].parse_error
    assert wpisy[2].session is None

    # Każde poprawne DOI ma zwykłą sesję importu — pobraną, czekającą na
    # redaktora w pierwszym kroku kreatora.
    for wpis in wpisy[:2]:
        sesja = wpis.session
        assert sesja.provider_name == "CrossRef"
        assert sesja.identifier == wpis.raw_bibtex
        assert sesja.status == ImportSession.Status.FETCHED
        assert sesja.created_by == importer_user
        assert sesja.normalized_data["doi"] == wpis.raw_bibtex
        assert sesja.celery_task_id == ""
        assert sesja.get_continue_url() == reverse(
            "importer_publikacji:verify", kwargs={"session_id": sesja.pk}
        )
    assert dostawca.pobrane == ["10.1234/a", "10.1234/b"]


@pytest.mark.django_db
def test_import_wielu_doi_nie_tworzy_rekordow_publikacji(
    importer_client, dostawca, pbn
):
    importer_client.post(URL_FORMULARZA, {"lista_doi": "10.1234/a\n10.1234/b"})
    assert ImportSession.objects.count() == 2
    assert Wydawnictwo_Ciagle.objects.count() == 0
    assert Wydawnictwo_Zwarte.objects.count() == 0
    assert not ImportSession.objects.exclude(created_record_id=None).exists()


# --- błąd pobierania jednego DOI -------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "blad",
    [
        requests.exceptions.ConnectionError("brak sieci"),
        requests.exceptions.Timeout("za długo"),
        RuntimeError("nieprzewidziany błąd w danych jednej pracy"),
    ],
)
def test_blad_pobierania_jednego_doi_nie_przerywa_pozostalych(
    importer_client, dostawca, pbn, caplog, blad
):
    dostawca.zachowania["10.1234/zly"] = blad
    with caplog.at_level(logging.ERROR, logger="importer_publikacji.tasks"):
        importer_client.post(
            URL_FORMULARZA, {"lista_doi": "10.1234/a\n10.1234/zly\n10.1234/c"}
        )

    statusy = {
        s.identifier: s for s in ImportSession.objects.filter(batch_entry__isnull=False)
    }
    assert statusy["10.1234/a"].status == ImportSession.Status.FETCHED
    assert statusy["10.1234/c"].status == ImportSession.Status.FETCHED
    zla = statusy["10.1234/zly"]
    assert zla.status == ImportSession.Status.IMPORT_FAILED
    assert zla.last_failed_stage == "fetch"
    assert zla.last_error_message
    assert type(blad).__name__ in zla.last_error_traceback

    # Błąd nie został połknięty: jest w logu razem z tracebackiem.
    wpisy_logu = [r for r in caplog.records if "10.1234/zly" in r.getMessage()]
    assert len(wpisy_logu) == 1
    assert wpisy_logu[0].exc_info is not None
    assert wpisy_logu[0].exc_info[1] is blad


@pytest.mark.django_db
def test_doi_nieznane_dostawcy_daje_blad_pobierania_a_reszta_idzie_dalej(
    importer_client, dostawca, pbn
):
    dostawca.zachowania["10.1234/nieznane"] = None
    importer_client.post(URL_FORMULARZA, {"lista_doi": "10.1234/nieznane\n10.1234/b"})
    nieznana = ImportSession.objects.get(identifier="10.1234/nieznane")
    assert nieznana.status == ImportSession.Status.IMPORT_FAILED
    assert (
        ImportSession.objects.get(identifier="10.1234/b").status
        == ImportSession.Status.FETCHED
    )

    batch = MultipleWorksImport.objects.get()
    tresc = importer_client.get(_url_paczki(batch)).content.decode()
    assert "Błąd pobierania" in tresc
    assert (
        reverse("importer_publikacji:task-retry", kwargs={"session_id": nieznana.pk})
        in tresc
    )


# --- sprawdzenie w BPP i w PBN ---------------------------------------------


@pytest.mark.django_db
def test_praca_obecna_w_bpp_jest_oznaczona(
    importer_client, dostawca, pbn, wydawnictwo_ciagle
):
    wydawnictwo_ciagle.doi = "10.1234/JEST"
    wydawnictwo_ciagle.save()

    importer_client.post(URL_FORMULARZA, {"lista_doi": "10.1234/jest\n10.1234/nowa"})
    batch = MultipleWorksImport.objects.get()
    jest, nowa = batch.entries.order_by("order")
    assert jest.sprawdzenie["bpp"] == [
        {
            "model": "wydawnictwo_ciagle",
            "pk": wydawnictwo_ciagle.pk,
            "tytul": wydawnictwo_ciagle.tytul_oryginalny,
            "metoda": "DOI",
        }
    ]
    assert nowa.sprawdzenie["bpp"] == []

    tresc = importer_client.get(_url_paczki(batch)).content.decode()
    assert tresc.count("już jest w BPP") == 1
    assert (
        reverse("admin:bpp_wydawnictwo_ciagle_change", args=[wydawnictwo_ciagle.pk])
        in tresc
    )


@pytest.mark.django_db
def test_praca_w_bpp_wykryta_takze_gdy_dostawca_nie_zna_doi(
    importer_client, dostawca, pbn, wydawnictwo_ciagle
):
    wydawnictwo_ciagle.doi = "10.1234/jest"
    wydawnictwo_ciagle.save()
    dostawca.zachowania["10.1234/jest"] = None

    importer_client.post(URL_FORMULARZA, {"lista_doi": "10.1234/jest"})
    wpis = MultipleWorksImportEntry.objects.get()
    assert wpis.session.status == ImportSession.Status.IMPORT_FAILED
    assert [p["pk"] for p in wpis.sprawdzenie["bpp"]] == [wydawnictwo_ciagle.pk]


@pytest.mark.django_db
def test_praca_obecna_w_pbn_jest_oznaczona(importer_client, dostawca, pbn):
    def odpowiedz(doi):
        if doi == "10.1234/wpbn":
            return {"mongoId": "5e709189878c28a04737dc6f"}
        raise HttpException(404, "/doi", "")

    pbn.get_publication_by_doi.side_effect = odpowiedz

    importer_client.post(URL_FORMULARZA, {"lista_doi": "10.1234/wpbn\n10.1234/b"})
    batch = MultipleWorksImport.objects.get()
    w_pbn, poza = batch.entries.order_by("order")
    assert w_pbn.sprawdzenie["pbn"]["stan"] == "jest"
    assert w_pbn.sprawdzenie["pbn"]["mongo_id"] == "5e709189878c28a04737dc6f"
    assert poza.sprawdzenie["pbn"] == {"stan": "brak"}

    tresc = importer_client.get(_url_paczki(batch)).content.decode()
    assert tresc.count("jest w PBN") == 1
    assert "provider=PBN&amp;identifier=5e709189878c28a04737dc6f" in tresc
    # Sprawdzenie w PBN niczego nie wybiera za redaktora w kreatorze.
    assert "pbn_mongo_id" not in w_pbn.session.matched_data


@pytest.mark.django_db
def test_blad_pbn_nie_przerywa_pobierania(importer_client, dostawca, pbn):
    pbn.get_publication_by_doi.side_effect = HttpException(500, "/doi", "awaria")
    importer_client.post(URL_FORMULARZA, {"lista_doi": "10.1234/a\n10.1234/b"})
    assert (
        ImportSession.objects.filter(status=ImportSession.Status.FETCHED).count() == 2
    )
    for wpis in MultipleWorksImportEntry.objects.all():
        assert wpis.sprawdzenie["pbn"]["stan"] == "nie_sprawdzono"
        assert "Błąd komunikacji z PBN" in wpis.sprawdzenie["pbn"]["komunikat"]


@pytest.mark.django_db
def test_brak_konfiguracji_pbn_to_nie_sprawdzono(importer_client, dostawca):
    # Bez mocka klienta: uczelnia testowa nie ma danych dostępowych PBN.
    importer_client.post(URL_FORMULARZA, {"lista_doi": "10.1234/a"})
    wpis = MultipleWorksImportEntry.objects.get()
    assert wpis.session.status == ImportSession.Status.FETCHED
    assert wpis.sprawdzenie["pbn"]["stan"] == "nie_sprawdzono"
    batch = wpis.parent
    assert "nie sprawdzono" in importer_client.get(_url_paczki(batch)).content.decode()


# --- zadanie w tle: wpisy pominięte i już pobrane --------------------------


@pytest.mark.django_db
def test_zadanie_pomija_wpisy_pominiete_uszkodzone_i_juz_pobrane(
    importer_user, dostawca, pbn
):
    batch = baker.make(
        MultipleWorksImport, provider_name="CrossRef", created_by=importer_user
    )
    istniejaca = baker.make(ImportSession, status=ImportSession.Status.VERIFIED)
    baker.make(
        MultipleWorksImportEntry,
        parent=batch,
        order=0,
        raw_bibtex="10.1234/ma-sesje",
        session=istniejaca,
    )
    baker.make(
        MultipleWorksImportEntry,
        parent=batch,
        order=1,
        raw_bibtex="10.1234/pominiety",
        skipped=True,
    )
    baker.make(
        MultipleWorksImportEntry,
        parent=batch,
        order=2,
        raw_bibtex="śmieć",
        parse_error="Nie rozpoznano numeru DOI w tej linii.",
    )
    nowy = baker.make(
        MultipleWorksImportEntry, parent=batch, order=3, raw_bibtex="10.1234/nowy"
    )

    pobierz_paczke_doi_task.delay(batch.pk, importer_user.pk)

    assert dostawca.pobrane == ["10.1234/nowy"]
    assert ImportSession.objects.count() == 2
    nowy.refresh_from_db()
    assert nowy.session.status == ImportSession.Status.FETCHED
    istniejaca.refresh_from_db()
    assert istniejaca.status == ImportSession.Status.VERIFIED

    # Drugie uruchomienie niczego nie dubluje.
    pobierz_paczke_doi_task.delay(batch.pk, importer_user.pk)
    assert dostawca.pobrane == ["10.1234/nowy"]
    assert ImportSession.objects.count() == 2


# --- ekran zbiorczy ---------------------------------------------------------


@pytest.mark.django_db
def test_ekran_zbiorczy_pokazuje_status_i_odnosnik_do_sesji(
    importer_client, dostawca, pbn
):
    importer_client.post(URL_FORMULARZA, {"lista_doi": "10.1234/a\nśmieć"})
    batch = MultipleWorksImport.objects.get()
    sesja = ImportSession.objects.get()

    resp = importer_client.get(_url_paczki(batch))
    tresc = resp.content.decode()
    assert resp.status_code == 200
    assert f"paczka nr {batch.pk}" in tresc
    assert "10.1234/a" in tresc
    assert "Praca o numerze 10.1234/a" in tresc
    assert "Pobrano" in tresc
    assert "Nie rozpoznano DOI" in tresc
    assert sesja.get_continue_url() in tresc
    assert "Otwórz w kreatorze" in tresc
    assert f"{reverse('importer_publikacji:sessions')}?paczka={batch.pk}" in tresc
    # Wszystko pobrane — strona nie odświeża się już sama.
    assert "hx-trigger" not in tresc


@pytest.mark.django_db
def test_ekran_zbiorczy_odswieza_sie_gdy_wpisy_czekaja(importer_client, importer_user):
    batch = baker.make(
        MultipleWorksImport, provider_name="CrossRef", created_by=importer_user
    )
    baker.make(MultipleWorksImportEntry, parent=batch, raw_bibtex="10.1234/a")

    resp = importer_client.get(_url_paczki(batch), HTTP_HX_REQUEST="true")
    tresc = resp.content.decode()
    # Żądanie HTMX dostaje sam fragment (bez layoutu strony).
    assert "<html" not in tresc
    assert 'hx-trigger="every 5s"' in tresc
    assert "W kolejce" in tresc
    assert "Trwa pobieranie danych w tle" in tresc
    assert "paczka-doi-przerwane" not in tresc


@pytest.mark.django_db
def test_przerwane_pobieranie_mozna_wznowic(importer_client, importer_user, pbn):
    batch = baker.make(
        MultipleWorksImport, provider_name="CrossRef", created_by=importer_user
    )
    wpis = baker.make(MultipleWorksImportEntry, parent=batch, raw_bibtex="10.1234/a")
    MultipleWorksImport.objects.filter(pk=batch.pk).update(
        modified=timezone.now() - timedelta(hours=1)
    )

    tresc = importer_client.get(_url_paczki(batch)).content.decode()
    assert "paczka-doi-przerwane" in tresc
    assert "Wznów pobieranie" in tresc
    assert "hx-trigger" not in tresc
    # Przy przerwanym pobieraniu wpis da się też pobrać pojedynczo.
    assert (
        reverse("importer_publikacji:batch-entry-import", kwargs={"entry_id": wpis.pk})
        in tresc
    )

    url_wznow = reverse(
        "importer_publikacji:batch-resume", kwargs={"batch_id": batch.pk}
    )
    falszywy = _FalszywyDostawca()
    with patch("importer_publikacji.tasks.get_provider", return_value=falszywy):
        resp = importer_client.post(url_wznow)
        assert resp["Location"] == _url_paczki(batch)
        assert falszywy.pobrane == ["10.1234/a"]

        # Pobieranie nie stoi — powtórzony POST nie zleca drugiego zadania.
        baker.make(MultipleWorksImportEntry, parent=batch, raw_bibtex="10.1234/b")
        importer_client.post(url_wznow)
        assert falszywy.pobrane == ["10.1234/a"]


@pytest.mark.django_db
def test_gotowy_rekord_nie_jest_pokazywany_jako_wlasny_duplikat(
    importer_client, importer_user, wydawnictwo_ciagle
):
    from django.contrib.contenttypes.models import ContentType

    batch = baker.make(
        MultipleWorksImport, provider_name="CrossRef", created_by=importer_user
    )
    sesja = baker.make(
        ImportSession,
        status=ImportSession.Status.COMPLETED,
        created_record_content_type=ContentType.objects.get_for_model(
            wydawnictwo_ciagle
        ),
        created_record_id=wydawnictwo_ciagle.pk,
    )
    baker.make(
        MultipleWorksImportEntry,
        parent=batch,
        raw_bibtex="10.1234/a",
        session=sesja,
        sprawdzenie={
            "bpp": [
                {
                    "model": "wydawnictwo_ciagle",
                    "pk": wydawnictwo_ciagle.pk,
                    "tytul": "x",
                    "metoda": "DOI",
                }
            ],
            "pbn": {"stan": "brak"},
        },
    )
    tresc = importer_client.get(_url_paczki(batch)).content.decode()
    assert "Utworzono rekord" in tresc
    assert "Zobacz pracę" in tresc
    assert "już jest w BPP</span>" not in tresc


# --- lista sesji: filtr paczki ---------------------------------------------


@pytest.mark.django_db
def test_lista_sesji_filtruje_po_paczce(importer_client, dostawca, pbn):
    importer_client.post(URL_FORMULARZA, {"lista_doi": "10.1234/a\n10.1234/b"})
    importer_client.post(URL_FORMULARZA, {"lista_doi": "10.1234/c"})
    pierwsza, druga = MultipleWorksImport.objects.order_by("pk")
    luzna = baker.make(
        ImportSession,
        status=ImportSession.Status.FETCHED,
        provider_name="CrossRef",
        identifier="10.1234/luzna",
        normalized_data={"doi": "10.1234/luzna", "title": "Luźna"},
    )

    resp = importer_client.get(
        reverse("importer_publikacji:sessions"), {"paczka": pierwsza.pk}
    )
    doi_na_liscie = {s.identifier for s in resp.context["sessions"]}
    assert doi_na_liscie == {"10.1234/a", "10.1234/b"}
    tresc = resp.content.decode()
    assert f"paczka nr {pierwsza.pk}" in tresc
    assert _url_paczki(pierwsza) in tresc

    # Bez filtra widać wszystko (także sesje spoza paczek).
    resp = importer_client.get(reverse("importer_publikacji:sessions"), {"wyczysc": 1})
    assert luzna in resp.context["sessions"]
    assert len(resp.context["sessions"]) == 4

    # Nieprawidłowy numer paczki nie wywraca listy.
    resp = importer_client.get(reverse("importer_publikacji:sessions"), {"paczka": "x"})
    assert resp.status_code == 200


# --- uprawnienia ------------------------------------------------------------


@pytest.mark.django_db
def test_anonim_nie_ma_dostepu(client):
    for metoda in (client.get, client.post):
        resp = metoda(URL_FORMULARZA)
        assert resp.status_code == 302
        assert URL_FORMULARZA not in resp["Location"].split("?")[0]
    assert MultipleWorksImport.objects.count() == 0


@pytest.mark.django_db
def test_uzytkownik_bez_grupy_nie_ma_dostepu(client, django_user_model, dostawca):
    zwykly = baker.make(django_user_model, is_staff=True)
    client.force_login(zwykly)
    assert client.get(URL_FORMULARZA).status_code == 403
    assert client.post(URL_FORMULARZA, {"lista_doi": "10.1234/a"}).status_code == 403
    assert MultipleWorksImport.objects.count() == 0
    assert dostawca.pobrane == []

    batch = baker.make(MultipleWorksImport, provider_name="CrossRef")
    url_wznow = reverse(
        "importer_publikacji:batch-resume", kwargs={"batch_id": batch.pk}
    )
    assert client.post(url_wznow).status_code == 403


@pytest.mark.django_db
def test_wznowienie_tylko_dla_paczek_doi(importer_client):
    bibtex = baker.make(MultipleWorksImport, provider_name="BibTeX")
    url_wznow = reverse(
        "importer_publikacji:batch-resume", kwargs={"batch_id": bibtex.pk}
    )
    assert importer_client.post(url_wznow).status_code == 404


# --- strażnicy: dotychczasowe zachowanie -----------------------------------


@pytest.mark.django_db
def test_straznik_pojedynczy_import_doi_bez_zmian(importer_client, dostawca):
    """Pojedynczy import po DOI nadal tworzy jedną sesję, bez paczki."""
    resp = importer_client.post(
        reverse("importer_publikacji:fetch"),
        {"provider": "CrossRef", "identifier": "https://doi.org/10.1234/Solo"},
        HTTP_HX_REQUEST="true",
    )
    sesja = ImportSession.objects.get()
    assert MultipleWorksImport.objects.count() == 0
    assert sesja.identifier == "10.1234/solo"
    assert sesja.status == ImportSession.Status.FETCHED
    assert resp["HX-Redirect"] == reverse(
        "importer_publikacji:task-status", kwargs={"session_id": sesja.pk}
    )
    assert not hasattr(sesja, "batch_entry")


@pytest.mark.django_db
def test_straznik_paczka_bibtex_ma_dotychczasowy_ekran(importer_client):
    batch = baker.make(MultipleWorksImport, provider_name="BibTeX")
    wpis = baker.make(MultipleWorksImportEntry, parent=batch, title="Alfa")
    tresc = importer_client.get(_url_paczki(batch)).content.decode()
    assert "Import wielu prac (BibTeX)" in tresc
    assert "paczka-doi" not in tresc
    assert (
        reverse("importer_publikacji:batch-entry-import", kwargs={"entry_id": wpis.pk})
        in tresc
    )
    assert not batch.jest_lista_doi


@pytest.mark.django_db
def test_strona_glowna_i_formularz_doi_prowadza_do_importu_wielu_doi(importer_client):
    tresc = importer_client.get(reverse("importer_publikacji:index")).content.decode()
    assert 'id="tile-wiele-doi"' in tresc
    assert URL_FORMULARZA in tresc

    tresc = importer_client.get(
        reverse("importer_publikacji:index"), {"provider": "CrossRef"}
    ).content.decode()
    assert "Zaimportuj wiele DOI naraz" in tresc

    tresc = importer_client.get(
        reverse("importer_publikacji:index"), {"provider": "PBN"}
    ).content.decode()
    assert "Zaimportuj wiele DOI naraz" not in tresc


@pytest.mark.django_db
def test_formularz_pokazuje_ostatnie_paczki(importer_client, dostawca, pbn):
    importer_client.post(URL_FORMULARZA, {"lista_doi": "10.1234/a"})
    batch = MultipleWorksImport.objects.get()
    tresc = importer_client.get(URL_FORMULARZA).content.decode()
    assert "Ostatnie listy DOI" in tresc
    assert _url_paczki(batch) in tresc
