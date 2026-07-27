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
    nośny dopiero przy metrykach Σ (bazy P/U) — tam Sum nie ma jak rozpoznać
    duplikatu, i tam stoi test, który BEZ dedupu pada:
    `test_dedup_po_zatrudnieniach_nie_zawyza_sumy_slotow`.
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
    """NIEZNANY klucz wymiaru cicho wraca do DEFAULT_ROW.

    Klucz musi być naprawdę nieobecny w DIMENSIONS — „rok" od Zadania 10 jest
    prawdziwym wymiarem (bazy P/U) i jego odrzucanie sprawdza osobny test
    `test_parse_params_wymiar_publikacyjny_zalezy_od_bazy_metryki`, który
    ćwiczy ścieżkę `expr_dla(baza) is None`, a nie fallback `dict.get`.
    """
    from bpp.pivot.autor import DEFAULT_ROW, parse_pivot_params_autor

    row, col, metric = parse_pivot_params_autor(
        {"pivot_row": "nie_ma_takiego_wymiaru", "pivot_val": "liczba_autorow"}
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


# --- Zadanie 10: bazy P (prace) i U (udziały) -------------------------------
#
# Testy baz P/U MUSZĄ brać fixture `denorms` i wołać `denorms.flush()`: baza P
# czyta materializowany widok `bpp_autorzy_mat` (relacja `autorzy`), a wymiary
# publikacyjne dochodzą do `bpp_rekord_mat` (`Rekord`). Bez flusha oba cache są
# puste i asercje sprawdzałyby pustkę.


@pytest.mark.django_db
def test_baza_prac_liczy_prace_autora(
    autor_jan_nowak, jednostka, wydawnictwo_ciagle, wydawnictwo_zwarte, denorms
):
    from bpp.pivot.autor import DIMENSIONS, METRICS, zbuduj_pivot_autora

    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)
    wydawnictwo_zwarte.dodaj_autora(autor_jan_nowak, jednostka)
    denorms.flush()

    wynik = zbuduj_pivot_autora(
        Autor.objects.all(), DIMENSIONS["autor"], None, METRICS["liczba_prac"]
    )

    assert wynik.grand_total == 2


@pytest.mark.django_db
def test_baza_prac_autor_x_rok(autor_jan_nowak, jednostka, wydawnictwo_ciagle, denorms):
    from bpp.pivot.autor import DIMENSIONS, METRICS, zbuduj_pivot_autora

    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)
    denorms.flush()

    wynik = zbuduj_pivot_autora(
        Autor.objects.all(),
        DIMENSIONS["autor"],
        DIMENSIONS["rok"],
        METRICS["liczba_prac"],
    )

    assert [label for _, label in wynik.cols] == [str(wydawnictwo_ciagle.rok)]
    assert wynik.grand_total == 1


@pytest.mark.django_db
def test_liczba_prac_nie_liczy_pracy_raz_na_wspolautora(
    autor_jan_nowak, autor_jan_kowalski, jednostka, wydawnictwo_ciagle, denorms
):
    """Test NOŚNOŚCI `distinct=True` w METRICS["liczba_prac"] — bez niego pada.

    Dwóch autorów TEJ SAMEJ jednostki i jedna WSPÓLNA praca. Grupa „jednostka"
    zbiera więc dwa wiersze relacji `autorzy` z tym samym `rekord_id`.
    `Count("autorzy__rekord_id", distinct=True)` daje 1 (tyle jest unikatowych
    prac); bez `distinct=True` wychodzi 2 — zmierzone na tych samych danych:
    `bez distinct: 2, z distinct: 1`.

    Wszystkie pozostałe testy „liczby prac" grupują po wymiarze `autor`, gdzie
    DISTINCT jest no-opem (w grupie jest z definicji jeden autor, więc jeden
    wiersz `autorzy` na pracę — zmierzone: bez=1, z=1). Dlatego ten test
    grupuje po `jednostka`: to jedyny układ, w którym mutacja „usuń
    distinct=True" zapala czerwone światło.
    """
    from bpp.pivot.autor import DIMENSIONS, METRICS, zbuduj_pivot_autora

    autor_jan_nowak.aktualna_jednostka = jednostka
    autor_jan_nowak.save()
    autor_jan_kowalski.aktualna_jednostka = jednostka
    autor_jan_kowalski.save()
    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    denorms.flush()

    wynik = zbuduj_pivot_autora(
        Autor.objects.all(), DIMENSIONS["jednostka"], None, METRICS["liczba_prac"]
    )

    assert wynik.row_totals[jednostka.pk] == 1, "bez distinct=True wychodzi 2"
    assert wynik.grand_total == 1


@pytest.mark.django_db
def test_liczba_prac_miedzy_jednostkami_dubluje_i_ostrzega(
    autor_jan_nowak,
    autor_jan_kowalski,
    jednostka,
    druga_jednostka,
    wydawnictwo_ciagle,
    denorms,
):
    """Ta sama praca w DWÓCH jednostkach: suma 2 przy jednej unikatowej pracy
    — i adnotacja o dublowaniu MUSI się pokazać.

    Dublowanie MIĘDZY wartościami wymiaru jest zamierzone (§7 specu: pracę
    liczymy w każdej jednostce, która ma w niej udział), ale wtedy sumy
    przewyższają liczbę prac i partial ma o tym uprzedzić
    (`report-body-pivot.html`, gałąź `pivot.has_autorzy_dim`). Do tej poprawki
    rejestr autorski podawał tam twarde `False`, więc notka nie pokazywała się
    NIGDY — mimo że pivot REKORDOWY w identycznym układzie ostrzega. To jest
    preset „Produktywność jednostek".

    Kontrapunkt w tym samym teście: wymiar `rok` jest atrybutem samej pracy,
    więc grupa nie może zawierać jej dwóch egzemplarzy — suma jest dokładna
    (1) i notka ma się NIE pokazać.
    """
    from bpp.pivot.autor import DIMENSIONS, METRICS, zbuduj_pivot_autora

    autor_jan_nowak.aktualna_jednostka = jednostka
    autor_jan_nowak.save()
    autor_jan_kowalski.aktualna_jednostka = druga_jednostka
    autor_jan_kowalski.save()
    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, druga_jednostka)
    denorms.flush()

    po_jednostce = zbuduj_pivot_autora(
        Autor.objects.all(), DIMENSIONS["jednostka"], None, METRICS["liczba_prac"]
    )
    assert po_jednostce.grand_total == 2, "praca liczona w obu jednostkach"
    assert po_jednostce.has_autorzy_dim is True

    po_roku = zbuduj_pivot_autora(
        Autor.objects.all(), DIMENSIONS["rok"], None, METRICS["liczba_prac"]
    )
    assert po_roku.grand_total == 1
    assert po_roku.has_autorzy_dim is False


@pytest.mark.django_db
def test_bazy_kadrowa_i_udzialow_nie_ostrzegaja_o_dublowaniu(
    zwarte_z_dyscyplinami, autor_jan_nowak, jednostka, denorms
):
    """Kontrapunkt do testu wyżej: adnotacja jest dla bazy P, nie dla wszystkich.

    Baza K liczy autorów (`Count(pk, distinct=True)`, autor należy do jednej
    grupy), baza U sumuje wiersze udziału (każdy ma jednego autora) — obie są
    z definicji addytywne, więc ostrzeżenie byłoby fałszywym alarmem.
    """
    from bpp.pivot.autor import DIMENSIONS, METRICS, zbuduj_pivot_autora

    denorms.flush()

    kadrowa = zbuduj_pivot_autora(
        Autor.objects.all(), DIMENSIONS["jednostka"], None, METRICS["liczba_autorow"]
    )
    assert kadrowa.has_autorzy_dim is False

    udzialy = zbuduj_pivot_autora(
        Autor.objects.all(), DIMENSIONS["autor"], None, METRICS["suma_slotow"]
    )
    assert udzialy.has_autorzy_dim is False


@pytest.mark.django_db
def test_autorzy_bez_dorobku_nie_zapychaja_macierzy(jednostka):
    """Autor bez ani jednej pracy wchodzi w bazie P przez LEFT JOIN z NULL-em.

    Nie potrzeba `denorms`: nie tworzymy tu żadnej publikacji, więc nie ma
    czego flushować — sprawdzamy właśnie, że pusty dorobek daje pustą macierz,
    a nie wiersz z zerem.
    """
    baker.make(Autor, aktualna_jednostka=jednostka, _quantity=3)

    from bpp.pivot.autor import DIMENSIONS, METRICS, zbuduj_pivot_autora

    wynik = zbuduj_pivot_autora(
        Autor.objects.all(), DIMENSIONS["jednostka"], None, METRICS["liczba_prac"]
    )

    assert wynik.rows == []
    assert wynik.grand_total == 0


@pytest.mark.django_db
def test_baza_udzialow_sumuje_sloty(zwarte_z_dyscyplinami, autor_jan_nowak, denorms):
    """Σ slotów na danych zbudowanych PRODUKCYJNĄ ścieżką.

    `zwarte_z_dyscyplinami` tworzy realną publikację (KSP, 20 pkt) z dwoma
    autorami przypiętymi do dyscyplin i woła `przelicz_punkty_dyscyplin()` —
    tak samo, jak robi to produkcja. Wiersze `bpp_cache_punktacja_autora`
    powstają więc same, z realnym `rekord_id`; nie fabrykujemy kluczy.
    Dwóch autorów po połowie udziału → slot 0.5 i pkdaut 10 na każdego.
    Trzeci autor (bez żadnego udziału) sprawdza, że LEFT JOIN nie wpuszcza go
    do macierzy jako wiersza z zerem.
    """
    from decimal import Decimal

    from bpp.models.cache import Cache_Punktacja_Autora_Query
    from bpp.pivot.autor import DIMENSIONS, METRICS, zbuduj_pivot_autora

    bez_udzialow = baker.make(Autor, nazwisko="Bezdorobkowy")
    denorms.flush()

    # Dowód, że JOIN przez cache_punktacja_autora_query naprawdę trafia w
    # istniejący Rekord (gdyby rekord_id nie pasował, sumy byłyby zerowe, a
    # test „zielony z pustki").
    assert (
        Cache_Punktacja_Autora_Query.objects.filter(
            autor=autor_jan_nowak, rekord__rok=zwarte_z_dyscyplinami.rok
        ).count()
        == 1
    )

    wynik = zbuduj_pivot_autora(
        Autor.objects.all(), DIMENSIONS["autor"], None, METRICS["suma_slotow"]
    )
    # Dwóch autorów × 0.5 slota
    assert wynik.grand_total == Decimal("1.0000")
    assert wynik.row_totals[autor_jan_nowak.pk] == Decimal("0.5000")
    assert bez_udzialow.pk not in wynik.row_totals
    assert len(wynik.rows) == 2

    wynik_pkd = zbuduj_pivot_autora(
        Autor.objects.all(), DIMENSIONS["autor"], None, METRICS["suma_pkdaut"]
    )
    assert wynik_pkd.grand_total == Decimal("20.0000")
    assert wynik_pkd.row_totals[autor_jan_nowak.pk] == Decimal("10.0000")


@pytest.mark.django_db
def test_baza_udzialow_nie_zawyza_sumy_przy_wielu_pracach(
    zwarte_z_dyscyplinami,
    wydawnictwo_ciagle,
    autor_jan_nowak,
    jednostka,
    dyscyplina1,
    denorms,
):
    """CENTRALNY test niezawyżania: wymiar MUSI iść tą samą relacją do-wielu,
    po której sumuje metryka.

    Jan Nowak ma DWIE prace i DWA wiersze udziału:

    * zwarte z `zwarte_z_dyscyplinami` — dwóch autorów, slot 0.5, pkdaut 10;
    * `wydawnictwo_ciagle` (20 pkt, jeden autor) — slot 1.0, pkdaut 20.

    Poprawna Σ slotów = 0.5 + 1.0 = **1.5**, Σ pkdaut = 10 + 20 = **30**.
    Gdyby wymiar „rok" w bazie U szedł przez `autorzy__rekord__rok` (druga,
    NIEZALEŻNA relacja do-wielu), Django zrobiłoby iloczyn kartezjański
    2 wiersze `autorzy` × 2 wiersze udziału = 4 → Σ slotów **3.0** i Σ pkdaut
    **60**, czyli dokładnie dwukrotność. Zmierzone: taki błędny wariant
    naprawdę zwraca 3.0000. Dlatego asercje są na dokładne liczby.
    """
    from decimal import Decimal

    from bpp.pivot.autor import DIMENSIONS, METRICS, zbuduj_pivot_autora

    wydawnictwo_ciagle.punkty_kbn = 20
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.dodaj_autora(
        autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1
    )
    wydawnictwo_ciagle.przelicz_punkty_dyscyplin()
    denorms.flush()

    tylko_nowak = Autor.objects.filter(pk=autor_jan_nowak.pk)

    # Sanity: obie relacje do-wielu mają po dwa wiersze — dopiero wtedy
    # iloczyn kartezjański byłby widoczny.
    assert autor_jan_nowak.cache_punktacja_autora_query_set.count() == 2
    assert autor_jan_nowak.autorzy_set.count() == 2

    slot_x_rok = zbuduj_pivot_autora(
        tylko_nowak, DIMENSIONS["autor"], DIMENSIONS["rok"], METRICS["suma_slotow"]
    )
    assert slot_x_rok.grand_total == Decimal("1.5000")

    pkd_x_dyscyplina = zbuduj_pivot_autora(
        tylko_nowak,
        DIMENSIONS["autor"],
        DIMENSIONS["dyscyplina"],
        METRICS["suma_pkdaut"],
    )
    assert pkd_x_dyscyplina.grand_total == Decimal("30.0000")

    # Baza P na tym samym materiale: dwie prace, nie cztery.
    prace = zbuduj_pivot_autora(
        tylko_nowak, DIMENSIONS["autor"], DIMENSIONS["rok"], METRICS["liczba_prac"]
    )
    assert prace.grand_total == 2


@pytest.mark.django_db
def test_dedup_po_zatrudnieniach_nie_zawyza_sumy_slotow(
    zwarte_z_dyscyplinami, autor_jan_nowak, jednostka, denorms
):
    """Test NOŚNOŚCI dedupu w `zbuduj_pivot_autora` — bez niego pada.

    Wejściowy queryset jest zawężony po relacji do-wielu
    `autor_jednostka__jednostka`, a autor ma KILKA wierszy `Autor_Jednostka`:
    jeden bez daty (dokłada go dopisanie autora do publikacji w
    `zwarte_z_dyscyplinami`) plus dwa dopisane tu okresy. Muszą to być okresy
    nienakładające się i tylko jeden bez daty — model wymusza unikalność wpisów
    bez daty (`UniqueConstraint`) i brak nakładania dla datowanych
    (`ExclusionConstraint`), więc zwielokrotnienia nie da się zrobić duplikatem.

    `Count(pk, distinct=True)` bazy K sam by takie zwielokrotnienie zwinął, ale
    `Sum` nie ma jak — bez `Autor.objects.filter(pk__in=base_qs.values("pk"))`
    w `zbuduj_pivot_autora` suma wychodzi 1.5000 zamiast 0.5000 (trzy wiersze
    zatrudnienia × 0.5 slota). Sprawdzone: po zakomentowaniu tamtej linii ten
    test pada właśnie na tej trzykrotności.
    """
    import datetime
    from decimal import Decimal

    from bpp.models import Autor_Jednostka
    from bpp.pivot.autor import DIMENSIONS, METRICS, zbuduj_pivot_autora

    denorms.flush()

    baker.make(
        Autor_Jednostka,
        autor=autor_jan_nowak,
        jednostka=jednostka,
        rozpoczal_prace=datetime.date(2020, 1, 1),
        zakonczyl_prace=datetime.date(2020, 12, 31),
    )
    baker.make(
        Autor_Jednostka,
        autor=autor_jan_nowak,
        jednostka=jednostka,
        rozpoczal_prace=datetime.date(2021, 1, 1),
        zakonczyl_prace=datetime.date(2021, 12, 31),
    )

    zatrudnienia = Autor_Jednostka.objects.filter(
        autor=autor_jan_nowak, jednostka=jednostka
    ).count()
    assert zatrudnienia == 3, "1 wpis bez daty + 2 okresy dopisane wyżej"

    qs = Autor.objects.filter(
        autor_jednostka__jednostka=jednostka, pk=autor_jan_nowak.pk
    )
    assert qs.count() == zatrudnienia, "filtr ma zwielokrotnić wiersze autora"

    wynik = zbuduj_pivot_autora(qs, DIMENSIONS["autor"], None, METRICS["suma_slotow"])

    assert wynik.grand_total == Decimal("0.5000")


@pytest.mark.django_db
def test_wymiar_niedostepny_w_bazie_udzialow():
    """`bpp_cache_punktacja_autora` nie zna typu odpowiedzialności ani
    charakteru formalnego — te wymiary istnieją tylko w bazie P."""
    from bpp.pivot.autor import (
        BAZA_KADROWA,
        BAZA_PRACE,
        BAZA_UDZIALY,
        DIMENSIONS,
    )

    assert DIMENSIONS["typ_odpowiedzialnosci"].expr_dla(BAZA_UDZIALY) is None
    assert DIMENSIONS["charakter_formalny"].expr_dla(BAZA_UDZIALY) is None
    assert DIMENSIONS["typ_odpowiedzialnosci"].expr_dla(BAZA_PRACE) is not None
    # Wymiary publikacyjne nie istnieją w bazie kadrowej — sam bpp_autor nie
    # ma dojścia do rekordu.
    for klucz in (
        "rok",
        "dyscyplina",
        "jednostka_pracy",
        "typ_odpowiedzialnosci",
        "charakter_formalny",
    ):
        assert DIMENSIONS[klucz].expr_dla(BAZA_KADROWA) is None


@pytest.mark.django_db
def test_parse_params_wymiar_publikacyjny_zalezy_od_bazy_metryki():
    """Seam `baza`: ten sam `pivot_row=rok` jest odrzucany przy metryce bazy K
    i przyjmowany przy metrykach baz P/U."""
    from bpp.pivot.autor import DEFAULT_ROW, parse_pivot_params_autor

    row, _col, metric = parse_pivot_params_autor(
        {"pivot_row": "rok", "pivot_val": "liczba_autorow"}
    )
    assert metric.key == "liczba_autorow"
    assert row.key == DEFAULT_ROW

    for metryka in ("liczba_prac", "suma_slotow", "suma_pkdaut"):
        row, _col, metric = parse_pivot_params_autor(
            {"pivot_row": "rok", "pivot_val": metryka}
        )
        assert metric.key == metryka
        assert row.key == "rok", f"rok ma być dostępny dla metryki {metryka}"

    # To samo dla kolumny: baza K nie ma prawa jej przyjąć.
    _row, col, _metric = parse_pivot_params_autor(
        {"pivot_row": "jednostka", "pivot_col": "rok", "pivot_val": "liczba_autorow"}
    )
    assert col is None

    _row, col, _metric = parse_pivot_params_autor(
        {"pivot_row": "autor", "pivot_col": "rok", "pivot_val": "suma_slotow"}
    )
    assert col is not None and col.key == "rok"
