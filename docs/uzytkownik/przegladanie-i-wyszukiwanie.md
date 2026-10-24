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

## Strona autora („raport autora") {#strona-autora}

Po wejściu w nazwisko na liście autorów otwiera się **strona autora** —
zestawienie wszystkich jego publikacji w bazie wraz z podstawowymi danymi
(aktualne miejsce pracy, identyfikatory takie jak ORCID, jeśli uzupełnione).
To najprostszy sposób, by zobaczyć dorobek jednej osoby bez budowania
zapytania.

Strona autora składa się z **pasów**: sekcja zajmuje całą szerokość strony
albo dwie sekcje stoją obok siebie. Sekcje bez danych (np. autor bez
zdjęcia i biogramu) po prostu się nie pokazują, a sąsiednia sekcja zajmuje
wtedy całą szerokość. Na wąskich ekranach (telefon, tablet) sekcje układają
się jedna pod drugą. **Które sekcje są widoczne, w jakiej kolejności i jak
szerokie**, ustala uczelnia (patrz
[instrukcja administratora — układ podstrony autora](../administrator/ogolna.md#układ-podstrony-autora-profil-autora)).

!!! note "Zrzut ekranu"
    W tym miejscu można w przyszłości umieścić zrzut ekranu przedstawiający
    typowy układ strony autora.

### Sekcje strony autora

W układzie domyślnym, od góry:

- **Podsumowanie dorobku w bazie danych** — łączna liczba publikacji
  (z zakresem lat), łączny Impact Factor oraz łączna suma punktów MNiSW.
- **Zdjęcie i biogram** — zdjęcie jest klikalne (powiększenie w osobnym
  okienku). Zdjęcie i biogram uzupełnia sam autor (patrz
  [Mój profil autora](moj-profil-autora.md)) albo redaktor.
- **Afiliacja i identyfikatory** — aktualna jednostka, historia zatrudnienia,
  dyscypliny naukowe, stopnie naukowe (doktorat, habilitacja) oraz kafle
  identyfikatorów (patrz niżej).
- **Wykresy w latach** — liczba publikacji, suma punktów MNiSW oraz suma
  Impact Factor; domyślnie obejmują ostatnie 10 lat. Gdy autor nie ma
  zdjęcia ani biogramu, wykresy stają obok afiliacji, jeden pod drugim.
- **Statystyki wg charakteru formalnego** (np. ile artykułów, ile
  rozdziałów) oraz **najczęstsi współautorzy** — z odnośnikiem do
  wizualnej sieci powiązań.
- **Liczba cytowań** (o ile uczelnia pobiera takie dane) oraz **metryki
  ewaluacyjne** — te ostatnie widzi tylko zalogowany autor na własnej
  stronie i osoby uprawnione do metryk.
- **Osiągnięcia naukowe** pobierane z systemu RAD-on (dla autorów z ORCID).
- Formularz **„Wyszukaj publikacje autora”** — zawężenie listy prac
  m.in. po typie, jednostce, roku.
- Odnośniki do **raportu autora** oraz **eksport (BibTeX / RIS)** —
  patrz [Eksport publikacji autora](#eksport-publikacji-autora-bibtex-i-ris).
- Listy prac: **najlepsze prace** wg punktacji i wg Impact Factor,
  **najnowsze artykuły**, **najnowsze książki i rozdziały** oraz **ostatnio
  edytowane** rekordy (domyślnie po 5 pozycji), a jeśli uczelnia włączyła
  tę sekcję — **wyróżnione publikacje** wskazane przez samego autora.

### Kafle identyfikatorów

W sekcji afiliacji każdy identyfikator autora ma swój kafel: ORCID, PBN
(odnośnik „Profil w PBN”, z oznaczeniem „POL-on”, gdy autor jest w systemie
POL-on), Web of Science, Scopus, Google Scholar, profil w portalu uczelni
(np. PPM) oraz wewnętrzny identyfikator BPP. Numer w systemie kadrowym
widzą tylko zalogowani.

- **Kliknięcie w odnośnik** na kaflu (np. numer ORCID) otwiera profil
  w danym serwisie.
- **Kliknięcie w pozostałą część kafla** kopiuje identyfikator do schowka
  (dla PBN — adres profilu); kafel na chwilę podświetla się na zielono.
  Kopiować można też z klawiatury — ikoną w rogu kafla.

### Interakcje na stronie autora

- Kliknięcie w pozycję na liście prac prowadzi do **szczegółów publikacji**.
- Kliknięcie w **nazwę charakteru formalnego** w tabeli statystyk otwiera
  wyszukiwarkę precyzyjną (multiseek) z gotowym zapytaniem „ten autor +
  ten charakter" — od razu zobaczysz wszystkie prace danego rodzaju.

## Eksport publikacji autora (BibTeX i RIS) {#eksport-publikacji-autora-bibtex-i-ris}

Na stronie autora znajdują się przyciski **„BibTeX"** i
**„RIS"**. Przygotowują one plik zawierający **wszystkie publikacje autora**
(odpowiednio w formacie `.bib` oraz `.ris`), gotowy do zaimportowania
w menedżerach bibliografii — np. Zotero, Mendeley, EndNote, a w przypadku
BibTeX-a także w środowisku LaTeX.

Po kliknięciu przycisku otwiera się strona eksportu:

1. **Niezalogowany użytkownik** przechodzi najpierw automatyczną weryfikację
   „czy nie jesteś robotem” (ALTCHA) — trwa zwykle kilka sekund i nie
   wymaga przepisywania kodów. Do jej zakończenia widoczny jest tylko
   przycisk powrotu na stronę autora. Zalogowani pomijają ten krok.
2. Kliknij **„Generuj plik …”** — plik przygotowuje się w tle; strona
   pokazuje postęp, a po zakończeniu odnośnik do pobrania.

Zalogowani użytkownicy mogą też pobrać plik od razu, pod adresami
`/bpp/autor/<id>/eksport.bib` (BibTeX) i `/bpp/autor/<id>/eksport.ris`
(RIS), gdzie `<id>` to identyfikator autora.

!!! note
    Eksport obejmuje do 5000 prac jednego autora.

## Ranking autorów

Menu **raporty → ranking autorów** otwiera formularz, w którym wybierasz
zakres (np. lata, jednostkę) i otrzymujesz uszeregowaną listę autorów wraz
z sumami punktów i liczbą prac. Reguły decydujące o tym, które prace wchodzą
do rankingu, opisuje rozdział [Raporty i rankingi](raporty-rankingi.md).
