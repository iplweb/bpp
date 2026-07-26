import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle

# Znacznik tabeli redakcyjnej ("postac=rekordy") w wyrenderowanym HTML-u.
# MUSI zawierac prefiks '<td class=' — sama nazwa klasy "rekord-id-cell"
# wystepuje w dokumencie ZAWSZE, bo zapytanie.html definiuje dla niej regule
# CSS w bloku <style>. Asercja na goley nazwie klasy przechodzi wiec takze
# dla postaci, ktore tabeli redakcyjnej wcale nie renderuja (zlapane przy
# odparkowaniu zadania 6: test "pivot degraduje" byl zielony jeszcze wtedy,
# gdy pivot juz mial wlasny render).
TABELA_REDAKCYJNA = b'<td class="rekord-id-cell">'


@pytest.fixture
def zalogowany_redaktor(client, admin_user):
    client.force_login(admin_user)
    return client


@pytest.mark.django_db
def test_postac_domyslna_to_tabela_redakcyjna(
    zalogowany_redaktor, wydawnictwo_ciagle, denorms
):
    denorms.flush()
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {"model": "rekord", "query": f"rok = {wydawnictwo_ciagle.rok}"},
    )
    assert res.status_code == 200
    assert TABELA_REDAKCYJNA in res.content


@pytest.mark.django_db
def test_postac_lista_renderuje_partial_multiseeka(
    zalogowany_redaktor, wydawnictwo_ciagle, denorms
):
    denorms.flush()
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "list",
        },
    )
    assert b"multiseek-list-report" in res.content


@pytest.mark.django_db
def test_postac_lista_nie_pokazuje_widgetu_usuwania(
    zalogowany_redaktor, wydawnictwo_ciagle, denorms
):
    """Widget ❌ jest sesyjny i multiseekowy — na /zapytanie/ nie działałby."""
    denorms.flush()
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "list",
        },
    )
    assert b"data-remove-result" not in res.content


@pytest.mark.django_db
def test_postac_tabela_ma_sumy(zalogowany_redaktor, wydawnictwo_ciagle, denorms):
    """Suma w stopce to SUMA CAŁEGO zbioru — nie wartość jednego wiersza.

    Dwa rekordy (40 + 10), zeby "50.00" mogło pochodzic TYLKO z agregatu w
    stopce, a nie z przypadkowego powtorzenia wartosci jednego z wierszy.
    """
    wydawnictwo_ciagle.punkty_kbn = 40
    wydawnictwo_ciagle.save()
    baker.make(Wydawnictwo_Ciagle, rok=wydawnictwo_ciagle.rok, punkty_kbn=10)
    denorms.flush()
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "table",
        },
    )
    assert b"multiseek-table-report" in res.content
    assert b"Suma:" in res.content
    # Lokalizacja pl: separator dziesiętny to przecinek (Decimal -> "50,00"),
    # nie punkt — inaczej niż literał "0.00" z default_if_none (tekst, nie
    # liczba, więc l10n go nie dotyka).
    assert b"50,00" in res.content


@pytest.mark.django_db
def test_postac_niedozwolona_dla_autora_degraduje(
    zalogowany_redaktor, autor_jan_nowak, denorms
):
    denorms.flush()
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {"model": "autor", "query": 'nazwisko = "Nowak"', "postac": "bibtex"},
    )
    assert res.status_code == 200
    assert b"multiseek-list-report" not in res.content
    # Pozytywny dowod degradacji do "rekordy": galaz autorska tabeli
    # (zapytanie.html, model_key != "rekord") renderuje TEN SAM znacznik
    # tabeli redakcyjnej co galaz rekordowa.
    assert TABELA_REDAKCYJNA in res.content


@pytest.mark.django_db
def test_postac_pivot_wybieralna_dla_obu_modeli(
    zalogowany_redaktor, wydawnictwo_ciagle, autor_jan_nowak, denorms
):
    """Zasada tego widoku: opcja w <select> albo dziala, albo jej nie ma.

    Rekordy maja render tabeli krzyzowej od Zadania 6. Autorzy dostaja
    wlasny rejestr wymiarow w Zadaniu 9 (ten test byl straznikiem "jeszcze
    nie" — teraz odwraca sie w straznika "juz tak", bo pivot dziala dla
    OBU modeli).
    """
    denorms.flush()
    dla_rekordu = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {"model": "rekord", "query": f"rok = {wydawnictwo_ciagle.rok}"},
    )
    dla_autora = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {"model": "autor", "query": 'nazwisko = "Nowak"'},
    )
    assert b'value="pivot"' in dla_rekordu.content
    assert b'value="pivot"' in dla_autora.content


@pytest.mark.django_db
def test_postac_pivot_dla_rekordu_zastepuje_tabele_redakcyjna(
    zalogowany_redaktor, wydawnictwo_ciagle, denorms
):
    """Pivot ma tabele redakcyjna ZASTAPIC, nie stanac obok niej.

    Render macierzy sprawdza test_zapytanie_pivot.py — tu pilnujemy drugiej
    polowy kontraktu: galaz "rekordy" ma sie nie wykonac.
    """
    denorms.flush()
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "pivot",
            "pivot_row": "rok",
            "pivot_val": "liczba",
        },
    )
    assert res.status_code == 200
    assert res.context["pivot"] is not None
    assert TABELA_REDAKCYJNA not in res.content


@pytest.mark.django_db
def test_postac_pivot_dla_autora_renderuje_macierz(
    zalogowany_redaktor, autor_jan_nowak, denorms
):
    """Przeciwienstwo dawnej degradacji: postac=pivot dla autora ma dzis
    renderowac tabele krzyzowa, NIE tabele redakcyjna (Zadanie 9)."""
    denorms.flush()
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {"model": "autor", "query": 'nazwisko = "Nowak"', "postac": "pivot"},
    )
    assert res.status_code == 200
    assert res.context["pivot"] is not None
    assert b"multiseek-list-report" not in res.content
    assert TABELA_REDAKCYJNA not in res.content


@pytest.mark.django_db
def test_postac_bibtex_renderuje_wlasny_partial(
    zalogowany_redaktor, wydawnictwo_ciagle, denorms
):
    """multiseek ma dedykowany partial na BibTeX (<pre> + przycisk kopiowania)
    — /zapytanie/ ma go używać, nie podstawiać listy opisów jako placeholder.
    """
    denorms.flush()
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "bibtex",
        },
    )
    assert b"multiseek-bibtex-container" in res.content
    assert b"multiseek-list-report" not in res.content


@pytest.mark.django_db
def test_postac_bibtex_nie_pokazuje_przycisku_kopiowania(
    zalogowany_redaktor, wydawnictwo_ciagle, denorms
):
    """Przycisk "Skopiuj" ma handler JS TYLKO w multiseeku (common-results.html)
    — na /zapytanie/ byłby martwy (klik bez efektu), więc go chowamy.
    Tekst BibTeX zostaje w pełni obecny i zaznaczalny/kopiowalny ręcznie.
    """
    denorms.flush()
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "bibtex",
        },
    )
    assert b"multiseek-bibtex-container" in res.content
    assert b'data-action="copy-bibtex"' not in res.content


@pytest.mark.django_db
def test_multiseek_nadal_pokazuje_widget_usuwania(client, wydawnictwo_ciagle, denorms):
    """Dowód neutralności flagi hide_chrome: multiseek jej nie przekazuje."""
    denorms.flush()
    from django.template.loader import render_to_string

    from bpp.models import Rekord

    html = render_to_string(
        "multiseek/report-body-list.html",
        {"object_list": Rekord.objects.all(), "export_mode": False},
    )
    assert "data-remove-result" in html


@pytest.mark.django_db
def test_multiseek_bibtex_nadal_pokazuje_przycisk_kopiowania(
    client, wydawnictwo_ciagle, denorms
):
    """Dowód neutralności flagi hide_chrome dla partiala BibTeX: multiseek
    jej nie przekazuje, więc przycisk "Skopiuj" mu zostaje."""
    denorms.flush()
    from django.template.loader import render_to_string

    from bpp.models import Rekord

    html = render_to_string(
        "multiseek/report-body-bibtex.html",
        {"object_list": Rekord.objects.all()},
    )
    assert 'data-action="copy-bibtex"' in html


@pytest.mark.django_db
def test_pager_zachowuje_postac_na_kolejnej_stronie(zalogowany_redaktor, denorms):
    """Regresja na `_zapytanie_pager.html`: bez `&postac=` link „następna
    strona" resetowałby wybraną postać z powrotem na „rekordy"."""
    rok = 2031
    for _ in range(30):
        baker.make(Wydawnictwo_Ciagle, rok=rok)
    denorms.flush()

    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {"model": "rekord", "query": f"rok = {rok}", "postac": "list"},
    )
    assert b"postac=list" in res.content


@pytest.mark.django_db
def test_pasek_eksportu_ma_link_do_csv(
    zalogowany_redaktor, wydawnictwo_ciagle, denorms
):
    denorms.flush()
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {"model": "rekord", "query": f"rok = {wydawnictwo_ciagle.rok}"},
    )
    assert b"/zapytanie/eksport/csv/" in res.content


@pytest.mark.django_db
def test_pasek_eksportu_bez_bibtexa_przy_liscie(
    zalogowany_redaktor, wydawnictwo_ciagle, denorms
):
    denorms.flush()
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "list",
        },
    )
    assert b"/zapytanie/eksport/bib/" not in res.content


@pytest.mark.django_db
def test_pasek_eksportu_ma_bibtexa_przy_postaci_bibtex(
    zalogowany_redaktor, wydawnictwo_ciagle, denorms
):
    denorms.flush()
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "bibtex",
        },
    )
    assert b"/zapytanie/eksport/bib/" in res.content


@pytest.mark.django_db
def test_pasek_eksportu_koduje_query_ze_znakami_specjalnymi(
    zalogowany_redaktor, wydawnictwo_ciagle, denorms
):
    """Cudzyslow i spacja w zapytaniu musza przetrwac podroz przez URL —
    bez |urlencode link eksportu prowadziłby do INNEGO zapytania niz to,
    ktore user widzi na ekranie (albo do bledu 400 po stronie serwera)."""
    denorms.flush()
    # "Wydawnictwo" musi pasowac do tytulu z fixture (inaczej 0 wynikow —
    # pasek eksportu w ogole by sie nie wyrenderowal, a test nic by nie
    # dowodzil).
    query = f'tytul_oryginalny ~ "Wydawnictwo" and rok = {wydawnictwo_ciagle.rok}'
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {"model": "rekord", "query": query},
    )
    from django.template.defaultfilters import urlencode as tpl_urlencode

    oczekiwany_fragment = f"query={tpl_urlencode(query)}".encode()
    assert oczekiwany_fragment in res.content


@pytest.mark.django_db
def test_pasek_eksportu_przenosi_postac(
    zalogowany_redaktor, wydawnictwo_ciagle, denorms
):
    """Link eksportu MUSI przenosic wybrana postac — inaczej eksport CSV z
    postaci "table" cichuteczko wyeksportowalby zupelnie inna postac."""
    denorms.flush()
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "postac": "table",
        },
    )
    assert b"postac=table" in res.content
    assert b"/zapytanie/eksport/csv/?model=rekord" in res.content


@pytest.mark.django_db
def test_pasek_eksportu_nieobecny_przy_zerowych_wynikach(zalogowany_redaktor, denorms):
    denorms.flush()
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {"model": "rekord", "query": "rok = 1900"},
    )
    assert res.status_code == 200
    # Sam string klasy "zapytanie-eksport-toolbar" wystepuje TAKZE w regule
    # CSS w <style> (renderowanej zawsze) — sprawdzamy wiec konkretny znacznik
    # otwierajacy <p>, nie samo wystapienie nazwy klasy w tresci strony.
    assert b'<p class="zapytanie-eksport-toolbar">' not in res.content


@pytest.mark.django_db
def test_pasek_eksportu_nieobecny_dla_autora(
    zalogowany_redaktor, autor_jan_nowak, denorms
):
    """Eksport LISTY autorow (postac="rekordy", domyslna) dziś 400-uje
    KAŻDY format (patrz zapytanie_export.py, Zadanie 11 to naprawi) — pasek
    dla model=autor + postac=rekordy nie ma prawa proponowac martwych
    linkow. Kontrapunkt: postac=pivot NIŻEJ, gdzie eksport realnie działa."""
    denorms.flush()
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {"model": "autor", "query": 'nazwisko = "Nowak"'},
    )
    assert res.status_code == 200
    assert b'<p class="zapytanie-eksport-toolbar">' not in res.content


@pytest.mark.django_db
def test_pasek_eksportu_obecny_dla_autora_pivota(
    zalogowany_redaktor, autor_jan_nowak, denorms
):
    """Kontrapunkt testu wyzej (DEFEKT #4 z brief-u Zadania 9): eksport
    MACIERZY (postac="pivot") dziala naprawde (przez _eksport_pivota), wiec
    pasek MUSI pokazac linki csv/xlsx — inaczej dzialajaca funkcja nie
    mialaby zadnego wejscia w UI."""
    denorms.flush()
    res = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {"model": "autor", "query": 'nazwisko = "Nowak"', "postac": "pivot"},
    )
    assert res.status_code == 200
    assert b'<p class="zapytanie-eksport-toolbar">' in res.content
    assert b"/zapytanie/eksport/csv/" in res.content
    assert b"/zapytanie/eksport/xlsx/" in res.content


@pytest.mark.django_db
def test_tabela_suma_tylko_na_ostatniej_stronie(zalogowany_redaktor, denorms):
    """Regresja na `page_obj=results` w include'u tabeli: bez tego stopka
    "Suma:" renderowałaby się na KAŻDEJ stronie, nie tylko ostatniej."""
    rok = 2032
    for _ in range(30):
        baker.make(Wydawnictwo_Ciagle, rok=rok)
    denorms.flush()

    pierwsza = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {"model": "rekord", "query": f"rok = {rok}", "postac": "table"},
    )
    assert b"Suma:" not in pierwsza.content

    druga = zalogowany_redaktor.get(
        reverse("bpp:zapytanie"),
        {
            "model": "rekord",
            "query": f"rok = {rok}",
            "postac": "table",
            "page": 2,
        },
    )
    assert b"Suma:" in druga.content
