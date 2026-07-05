Konsolidacja Wydział→Jednostka, Faza A (addytywna): nowy słownik
`RodzajJednostki` z flagami behawioralnymi, pole `Jednostka.rodzaj` (FK) obok
dotychczasowego `rodzaj_jednostki`, pola per-węzeł przeniesione z wydziału
(`zezwalaj_na_ranking_autorow`, `poprzednie_nazwy`, `skrot_nazwy`), kolumna
`legacy_wydzial_id`, poszerzenie sluga jednostki. Zamknięto wyciek niewidocznych
jednostek przez API, sitemap i autouzupełnianie (bramka logowania na
edytorskim endpointcie). Komendy `waliduj_konwersje_wydzialow` (skan przed
konwersją) oraz `konwertuj_wydzialy_na_jednostki` (idempotentna konwersja
wydziałów na ukryte węzły drzewa jednostek). Zmiany w pełni addytywne — nic nie
jest usuwane, `Wydzial` nietknięty.
