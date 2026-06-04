# Przeglądanie i wyszukiwanie publikacji

Ten rozdział opisuje to, co widzi **każdy odwiedzający** stronę BPP — bez
logowania. Dane można wyszukiwać na dwa sposoby oraz przeglądać według
autorów, jednostek, źródeł i lat. Czynności redakcyjne (dodawanie i edycja
rekordów) opisuje osobna [Instrukcja redaktora](../redaktor/uczelnia.md).

## Dwa tryby wyszukiwania

Menu **szukaj** na górnej belce udostępnia dwa tryby. Różnią się one tym,
*jak precyzyjnie* formułujemy zapytanie.

### Wyszukiwanie szybkie (klawisz `/`)

Pozycja **szukaj → szybko** otwiera okno błyskawicznej wyszukiwarki po
tytule. To samo okno otworzysz z dowolnego miejsca na stronie, naciskając
klawisz `/` (ukośnik).

Wyszukiwanie szybkie jest *jednopolowe* — wpisujesz fragment tytułu
(minimum 3 znaki), a system natychmiast podpowiada pasujące prace. Obsługuje
kilka prostych operatorów:

- **Od początku wyrazu** — `preane` znajdzie „preanestetyczny", ale
  `anestetyczny` już nie (dopasowanie jest od początku słowa).
- **Wykluczanie słów** — poprzedzenie wyrazu minusem, np. `-onkologia`,
  zwróci prace, które danego słowa **nie** zawierają.
- **Całe frazy** — ujęcie w cudzysłów, np. `"Uniwersytet Medyczny"`,
  wyszuka dokładnie tę frazę.

Po wynikach poruszasz się strzałkami `↑` `↓`, `ENTER` przechodzi do
wybranej pozycji, a `ESC` zamyka okno.

!!! tip "Kiedy używać"
    Wyszukiwanie szybkie sprawdza się, gdy znasz fragment tytułu i chcesz
    w jednej chwili trafić do konkretnej pracy.

### Wyszukiwanie precyzyjne (formularz)

Pozycja **szukaj → precyzyjnie** otwiera rozbudowany formularz, w którym
budujesz zapytanie z wielu warunków jednocześnie — np. autor *oraz* rok
*oraz* typ pracy *oraz* jednostka. Poszczególne kryteria łączysz spójnikami
(i / lub), a całość możesz dowolnie zagnieżdżać. Wyniki da się sortować
i wyeksportować.

!!! tip "Kiedy używać"
    Wyszukiwanie precyzyjne sprawdza się, gdy chcesz zawęzić wyniki po
    kilku polach naraz (np. „artykuły danego autora z lat 2020–2023") —
    czego pojedyncze pole szybkiego wyszukiwania nie potrafi.

!!! note "Wyszukiwanie zapytaniem"
    W menu może pojawić się dodatkowo pozycja **zapytaniem** — to tryb dla
    zalogowanych redaktorów, pozwalający wpisać zapytanie w języku BPP-QL.
    Dla zwykłego odwiedzającego nie jest widoczny.

## Przeglądanie

Menu **przeglądaj** pozwala wędrować po bazie bez wpisywania zapytania —
od listy do listy aż do konkretnego rekordu. Dostępne są widoki:

- **Uczelnia** — strona główna z danymi i logo uczelni oraz jej strukturą.
- **Jednostki** — alfabetyczna lista wydziałów i jednostek; po wejściu
  w jednostkę zobaczysz przypisane do niej publikacje i pracowników.
- **Autorzy** — alfabetyczna lista autorów; strona pojedynczego autora to
  jego pełna bibliografia (patrz niżej).
- **Źródła** — wydawnictwa ciągłe (czasopisma) i inne źródła; po wejściu
  w źródło zobaczysz opublikowane w nim prace.
- **Wg roku** — prace pogrupowane według roku wydania.

## Strona autora („raport autora")

Po wejściu w nazwisko na liście autorów otwiera się **strona autora** —
zestawienie wszystkich jego publikacji w bazie wraz z podstawowymi danymi
(aktualne miejsce pracy, identyfikatory takie jak ORCID, jeśli uzupełnione).
To najprostszy sposób, by zobaczyć dorobek jednej osoby bez budowania
zapytania.

## Ranking autorów

Menu **raporty → ranking autorów** otwiera formularz, w którym wybierasz
zakres (np. lata, jednostkę) i otrzymujesz uszeregowaną listę autorów wraz
z sumami punktów i liczbą prac. Reguły decydujące o tym, które prace wchodzą
do rankingu, opisuje rozdział [Raporty i rankingi](raporty-rankingi.md).
