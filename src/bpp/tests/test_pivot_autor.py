import pytest
from model_bakery import baker

from bpp.models import Autor
from bpp.models.autor import Tytul


@pytest.mark.django_db
def test_baza_kadrowa_liczy_autorow(jednostka):
    from bpp.pivot.autor import DIMENSIONS, METRICS, zbuduj_pivot_autora
    from bpp.pivot.core import BRAK

    baker.make(Autor, aktualna_jednostka=jednostka, _quantity=3)
    baker.make(Autor, aktualna_jednostka=None)

    wynik = zbuduj_pivot_autora(
        Autor.objects.all(), DIMENSIONS["jednostka"], None, METRICS["liczba_autorow"]
    )

    assert wynik.grand_total == 4
    etykiety = {label: wynik.row_totals[key] for key, label in wynik.rows}
    assert etykiety == {str(jednostka): 3, BRAK: 1}


@pytest.mark.django_db
def test_wymiar_ma_orcid_grupuje_na_tak_nie():
    from bpp.pivot.autor import DIMENSIONS, METRICS, zbuduj_pivot_autora

    baker.make(Autor, orcid="0000-0001-0000-0001")
    baker.make(Autor, orcid=None, _quantity=2)

    wynik = zbuduj_pivot_autora(
        Autor.objects.all(), DIMENSIONS["ma_orcid"], None, METRICS["liczba_autorow"]
    )

    etykiety = {label: wynik.row_totals[key] for key, label in wynik.rows}
    assert etykiety == {"TAK": 1, "NIE": 2}


@pytest.mark.django_db
def test_krzyzowo_jednostka_x_tytul(jednostka):
    from bpp.pivot.autor import DIMENSIONS, METRICS, zbuduj_pivot_autora

    tytul = baker.make(Tytul)
    baker.make(Autor, aktualna_jednostka=jednostka, tytul=tytul, _quantity=2)

    wynik = zbuduj_pivot_autora(
        Autor.objects.all(),
        DIMENSIONS["jednostka"],
        DIMENSIONS["tytul"],
        METRICS["liczba_autorow"],
    )

    assert wynik.grand_total == 2
    assert len(wynik.cols) == 1


@pytest.mark.django_db
def test_rok_urodzenia_jako_wymiar():
    import datetime

    from bpp.pivot.autor import DIMENSIONS, METRICS, zbuduj_pivot_autora

    baker.make(Autor, urodzony=datetime.date(1970, 5, 1))
    baker.make(Autor, urodzony=datetime.date(1980, 5, 1))

    wynik = zbuduj_pivot_autora(
        Autor.objects.all(),
        DIMENSIONS["rok_urodzenia"],
        None,
        METRICS["liczba_autorow"],
    )

    assert {label for _, label in wynik.rows} >= {"1970", "1980"}


@pytest.mark.django_db
def test_filtr_do_wielu_nie_zwielokrotnia_liczby_autorow(jednostka):
    """Filtr po relacji do-wielu mnoży wiersze autora — wynik ma tego nie widzieć.

    CZEGO TEN TEST NIE DOWODZI: nie jest testem dedupu przez świeży queryset
    w zbuduj_pivot_autora. Sprawdzone empirycznie — po usunięciu tamtej linii
    ten test nadal przechodzi, bo metryka bazy K to Count(pk, distinct=True),
    a DISTINCT w agregacie sam zwija zwielokrotnione wiersze. Dedup staje się
    nośny dopiero przy metrykach Σ (bazy P/U, Zadanie 10) — tam Sum nie ma jak
    rozpoznać duplikatu, i tam należy postawić test, który BEZ dedupu pada.
    Tutaj testujemy kontrakt widoczny dla usera: liczba autorów nie puchnie
    od zatrudnień.
    """
    import datetime

    from bpp.models import Autor_Jednostka
    from bpp.pivot.autor import DIMENSIONS, METRICS, zbuduj_pivot_autora

    autor = baker.make(Autor, aktualna_jednostka=jednostka)
    # Dwa ODDZIELNE, nienakładające się okresy zatrudnienia tego samego
    # autora w tej samej jednostce — model wymusza unikalność (autor,
    # jednostka) dla wpisów bez daty (`rozpoczal_prace IS NULL`) i brak
    # nakładania dla wpisów datowanych (ExclusionConstraint), więc
    # zwielokrotnienie testujemy dwoma różnymi okresami, nie duplikatem.
    baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=datetime.date(2020, 1, 1),
        zakonczyl_prace=datetime.date(2020, 12, 31),
    )
    baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=datetime.date(2021, 1, 1),
        zakonczyl_prace=datetime.date(2021, 12, 31),
    )

    qs = Autor.objects.filter(autor_jednostka__jednostka=jednostka)
    wynik = zbuduj_pivot_autora(
        qs, DIMENSIONS["jednostka"], None, METRICS["liczba_autorow"]
    )

    assert wynik.grand_total == 1


@pytest.mark.django_db
def test_parse_params_nieznany_wymiar_wraca_do_domyslnego():
    """DEFEKT #2 z brief-u: „rok" nie jest w ogóle kluczem w DIMENSIONS
    autorskich (to wymiar publikacyjny bazy P/U, jeszcze niewprowadzony —
    Zadanie 10), więc DIMENSIONS.get("rok", default) trafia na fallback
    niezależnie od tego, czy per-bazowe odrzucanie przez expr_dla() w ogóle
    działa. Ten test sprawdza tylko, że NIEZNANY klucz wymiaru cicho
    wraca do DEFAULT_ROW — nie sprawdza (i nie może, przy jednej bazie K)
    odrzucenia wymiaru ZNANEGO, ale niedostępnego w bieżącej bazie. Ta
    ścieżka (`expr_dla(baza) is None` dla realnego wymiaru publikacyjnego)
    dostanie swój właściwy test w Zadaniu 10, gdy pojawią się wymiary z
    `expr` jako słownikiem per baza."""
    from bpp.pivot.autor import DEFAULT_ROW, parse_pivot_params_autor

    row, col, metric = parse_pivot_params_autor(
        {"pivot_row": "rok", "pivot_val": "liczba_autorow"}
    )

    assert row.key == DEFAULT_ROW


@pytest.mark.django_db
def test_bramka_rozmiaru_macierzy(monkeypatch, jednostka):
    from bpp.pivot import core
    from bpp.pivot.autor import DIMENSIONS, METRICS, zbuduj_pivot_autora

    baker.make(Autor, aktualna_jednostka=jednostka, _quantity=3)
    monkeypatch.setattr(core, "PIVOT_MAX_CELLS", 0)

    with pytest.raises(core.PivotTooLargeError):
        zbuduj_pivot_autora(
            Autor.objects.all(),
            DIMENSIONS["autor"],
            None,
            METRICS["liczba_autorow"],
        )
