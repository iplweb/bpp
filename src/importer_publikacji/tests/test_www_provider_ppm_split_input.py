"""``WWWProvider.split_input`` dla list Omega-PSIR/PPM — Track C spike.

Werdykt (patrz findings doc pod
``docs/superpowers/handoffs/2026-07-10-ppm-lista-spike-findings.md``):

- ``articles-xml.seam?year=YYYY`` (SEO-sitemapa Omega-PSIR, statyczna,
  bez JS) -> DZIAŁA: rozpoznajemy kształt URL-a, pobieramy XML, zwracamy
  N ``SplitRecord`` z URL-ami stron szczegółowych, które
  ``WWWProvider.fetch()`` już umie rozwiązać (citation_*/omega_psir).
- ``globalResultList.seam`` (siatka wyników wyszukiwania) -> BLOCKED:
  renderowana AJAX-em JSF/Seam z statefulnym ``javax.faces.ViewState``,
  server-rendered HTML nie niesie linków do prac. Celowo NIE rozpoznajemy
  tego kształtu — dostajemy bezpieczny fallback do 1 rekordu (identyczny
  jak zachowanie domyślne), zamiast fingować listę.
"""

from unittest.mock import patch

import pytest

from importer_publikacji.providers import SplitRecord
from importer_publikacji.providers.www import WWWProvider

from ._www_provider_samples import (
    SAMPLE_HTML_PPM_GLOBAL_RESULT_LIST,
    SAMPLE_OMEGA_ARTICLES_SITEMAP_XML,
    _mock_response,
)

SITEMAP_URL = "https://ppm.umlub.pl/articles-xml.seam?year=2026"
GLOBAL_RESULT_LIST_URL = (
    "https://ppm.umlub.pl/globalResultList.seam?r=projectmain&tab=PROJECT&lang=pl"
)


@patch("importer_publikacji.providers.www.requests.get")
def test_split_input_ppm_articles_sitemap_returns_one_record_per_article(mock_get):
    mock_get.return_value = _mock_response(text=SAMPLE_OMEGA_ARTICLES_SITEMAP_XML)

    provider = WWWProvider()
    records = provider.split_input(SITEMAP_URL)

    assert len(records) == 3
    assert all(isinstance(r, SplitRecord) and r.ok for r in records)
    assert records[0].raw == (
        "https://ppm.umlub.pl/info/article/UML001085ec4f064177b924ac8a993e7701/"
    )
    assert records[1].raw == (
        "https://ppm.umlub.pl/info/article/UML0057c12f802b4ae7a8ef45ba8aaad38a/"
    )
    assert records[2].raw == (
        "https://ppm.umlub.pl/info/article/UML00cc39550a89431597f0949c8c467ef4/"
    )
    # Fetch faktycznie zostal wywolany na URL-u sitemapy, nie na czyms
    # zgadywanym.
    mock_get.assert_called_once()
    assert mock_get.call_args.args[0] == SITEMAP_URL


@patch("importer_publikacji.providers.www.requests.get")
def test_split_input_ppm_sitemap_http_error_falls_back_to_single_record(mock_get):
    mock_get.return_value = _mock_response(status_code=500)

    provider = WWWProvider()
    records = provider.split_input(SITEMAP_URL)

    assert records == [SplitRecord(raw=SITEMAP_URL)]


@patch("importer_publikacji.providers.www.requests.get")
def test_split_input_ppm_sitemap_malformed_xml_falls_back_to_single_record(mock_get):
    mock_get.return_value = _mock_response(text="<not><valid</not>")

    provider = WWWProvider()
    records = provider.split_input(SITEMAP_URL)

    assert records == [SplitRecord(raw=SITEMAP_URL)]


def test_split_input_non_ppm_url_is_unaffected():
    """URL-e spoza kształtu articles-xml.seam nie ruszają sieci wcale."""
    provider = WWWProvider()
    records = provider.split_input("https://example.com/article/1")
    assert records == [SplitRecord(raw="https://example.com/article/1")]


@patch("importer_publikacji.providers.www.requests.get")
def test_split_input_ppm_global_result_list_falls_through_today(mock_get):
    """Dokumentuje dzisiejszy bezpieczny fallback dla siatki AJAX.

    Nie zgadujemy: 1 rekord, identycznie jak default. Ten sam URL trafi
    potem do zwykłego single-fetch, ktory (bo strona nie niesie
    citation_*/DC/JSON-LD) zwroci ``None`` — operator zobaczy czytelny
    blad "nie znaleziono danych", a nie fikcyjny import.
    """
    mock_get.return_value = _mock_response(text=SAMPLE_HTML_PPM_GLOBAL_RESULT_LIST)

    provider = WWWProvider()
    records = provider.split_input(GLOBAL_RESULT_LIST_URL)

    assert records == [SplitRecord(raw=GLOBAL_RESULT_LIST_URL)]
    # split_input dla nierozpoznanego ksztaltu nie robi ZADNEGO requesta —
    # tylko validate_identifier parsuje sam URL lokalnie.
    mock_get.assert_not_called()


@pytest.mark.xfail(
    reason=(
        "BLOKADA (Track C, spike 2026-07-10): globalResultList.seam "
        "renderuje siatke wynikow przez JSF/Seam AJAX z statefulnym "
        "javax.faces.ViewState - stateless requests.get widzi tylko "
        "zakladki z licznikami, zero linkow do prac w server-rendered "
        "HTML. Brak odkrytego publicznego REST/OAI dla TEGO widoku "
        "(w odroznieniu od articles-xml.seam, ktory dziala). Ten test "
        "dokumentuje DOCELOWE zachowanie na przyszlosc: split_input "
        "powinien kiedys umiec rozbic tez wyniki wyszukiwania z grida, "
        "nie tylko roczny eksport XML. Wymaga albo (a) headless "
        "przegladarki odtwarzajacej ViewState, albo (b) odkrycia "
        "prywatnego API PPM (dostepne tylko na wniosek, patrz "
        "api@omegapsir.io), albo (c) wspolpracy z administratorem PPM."
    ),
    strict=True,
)
@patch("importer_publikacji.providers.www.requests.get")
def test_split_input_ppm_global_result_list_target_behavior_xfail(mock_get):
    mock_get.return_value = _mock_response(text=SAMPLE_HTML_PPM_GLOBAL_RESULT_LIST)

    provider = WWWProvider()
    records = provider.split_input(GLOBAL_RESULT_LIST_URL)

    assert len(records) >= 2
