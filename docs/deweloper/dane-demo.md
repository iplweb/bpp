# Dane demo (`create_demo_data`)

Generator syntetycznych danych demo z wymiennymi motywami.

## Szybki start

```bash
uv run python src/manage.py create_demo_data \
    --motyw wiedzmin \
    --autorow 200 --ile-ciaglych 1000 --ile-zwartych 500 \
    --yes-i-am-sure --confirm-db <NAZWA_BAZY>
```

Z przeglądarki: kreator pierwszego uruchomienia (pusta baza) pyta
„Utworzyć dane demo?” i generuje je w tle w tej samej skali — patrz
[Pierwsze uruchomienie](../administrator/pierwsze-uruchomienie.md)
i `src/bpp_setup_wizard/README.md`. Nowy motyw dopisz też do
`OPISY_MOTYWOW` w `src/bpp_setup_wizard/dane_demo.py` (pilnuje tego test),
a nowy pasek postępu (`desc=` w `make_progress`) — do `ETAPY_GENERATORA`
w tym samym pliku, żeby pasek kreatora nie stał w miejscu.

## Motywy (`--motyw`)

- `realistyczny` (domyślny) — polskie dane akademickie
- `lem` — Stanisław Lem
- `wiedzmin` — Wiedźmin
- `harry-potter` — Harry Potter
- `disney` — Disney
- `mitologia` — mitologia grecka, rzymska, słowiańska i nordycka
- `trylogia` — Trylogia Sienkiewicza
- `miks` — wszystkie motywy fabularne naraz (bez `realistyczny`):
  największa różnorodność imion, nazwisk i tytułów

Motyw może mieć „autorów obowiązkowych” (`autorzy_obowiazkowi`), tworzonych
zawsze jako pierwsi i nigdy nie losowanych drugi raz. `wiedzmin` (i `miks`)
ma ich kilku — Yennefer Merigold, Regis z Cintry, Cahir z Aretuzy itd. —
bo skrypty zrzutów ekranu (`bin/docs-demo-*.py`) szukają ich po nazwisku.

## Wybrane flagi

- `--bez-prefiksu` — pełny realizm (bez markera „Demo —")
- `--procent-ze-streszczeniem 70` — odsetek prac ze streszczeniem
- `--od-roku 2020 --do-roku 2026` — zakres lat prac
- `--seed 123` — deterministyczny wynik
- `--uzytkownik LOGIN` — komu przypisać wpisy „utworzono" w historii
  rekordów (domyślnie konto techniczne `bpp-system`)
- `--zgloszen 40` — liczba zgłoszeń publikacji (`zglos_publikacje`);
  `0` wyłącza ich generowanie

## Historia rekordów demo (`--uzytkownik`)

Generator zapisuje `bulk_create`, więc bez dodatkowego kroku rekordy demo
nie miałyby żadnego śladu na stronie „Historia" w adminie. Dlatego na koniec
generowania każdy utworzony rekord z własną stroną w adminie dostaje wpis
historii (`LogEntry`, akcja „dodano") o treści:

> Utworzono poleceniem create_demo_data (dane demonstracyjne, motyw=…, seed=…)

Dotyczy to: uczelni (tylko gdy stworzył ją generator), jednostek i wydziałów,
autorów, powiązań autor–dyscyplina, źródeł, wydawców, wydawnictw ciągłych
i zwartych oraz zgłoszeń publikacji. Pominięte są obiekty edytowane
w inline'ach (autorzy prac, streszczenia, punktacja źródeł, poziomy
wydawców) i dane wyliczane (liczba N, metryki ewaluacji).

Modele wersjonowane przez django-reversion (autor, uczelnia) dostają
dodatkowo wersję „utworzenia" z tym samym komentarzem — każdy rekord we
własnej rewizji, żeby przywrócenie wersji jednego autora nie cofało
pozostałych. Na stronie „Historia" autora wpis „Utworzono…" pojawia się
raz.

Wpisy są przypisane do konta technicznego `bpp-system` (to samo konto
podpisuje inne operacje systemowe); `--uzytkownik LOGIN` przypisuje je
wskazanemu użytkownikowi, np. superużytkownikowi uruchamiającemu komendę.

`cleanup_demo_data` usuwa razem z obiektami demo całą ich historię
(`LogEntry` i wersje reversion, także z późniejszych edycji) — nie zostaje
osierocona historia.

## Zgłoszenia publikacji (`--zgloszen`)

Generator tworzy zgłoszenia publikacji rozłożone po wszystkich statusach
obiegu (nowe, wymaga zmian, po zmianach, zaakceptowane, zaimportowane,
odrzucone, spam) — przy `--zgloszen` ≥ 7 każdy status występuje co
najmniej raz:

- zaakceptowane i zaimportowane są podpięte (`odpowiednik_w_bpp`) do
  wygenerowanych prac WC/WZ i przejmują ich tytuł, rok, DOI i autorów;
- pozostałe mają tytuły z wybranego motywu i 1–5 autorów demo
  z jednostkami i dyscyplinami;
- część ma DOI, adres „Dostępna w sieci pod adresem", formę dostępu
  i informację o opłatach; zwrócone mają przyczynę zwrotu i kod edycji;
- adresy e-mail zgłaszających są w domenie `demo.example.org`;
- pliki załączników nie są tworzone.

## Co jeszcze powstaje (dodatki)

Poza uczelnią, autorami, czasopismami i pracami generator dokłada kilka
rzeczy, dzięki którym na bazie demo nie są puste narzędzia redakcyjne
i porządkowe. Każdy dodatek ma własny generator losowy (`<seed>-<nazwa>`),
więc dla danego `--seed` rdzeń danych jest taki sam jak bez dodatków.
`--bez-dodatkow` wyłącza wszystkie naraz.

- **Dwudyscyplinowcy** (`--dwudyscyplinowcow 8`, `0` — wcale): autorzy
  z pseudonimem „dwudyscyplinowy” (widać go przy nazwisku w całym BPP),
  dyscyplina 60% + subdyscyplina 40% w każdym roku (rodzaj „N”), po 6
  artykułów — połowa przypisana do subdyscypliny i opublikowana
  w czasopiśmie, które ma tę dyscyplinę (praca „zgodna” w module
  dwudyscyplinowców). Ekran pokazuje okres wybrany na górnym pasku.
- **Rzadsze rodzaje rekordów** (`--bez-rzadkich-typow`): prace doktorskie
  (z promotorem) i habilitacyjne, patenty z autorami, konferencje (przy
  ~5% prac), serie wydawnicze (~10% książek, z numerem w serii), granty
  (~3% prac), nagrody (kilka książek).
- **Celowe „brudy”** (`--bez-brudow`):
  - zdublowani autorzy — to samo imię i nazwisko, inicjał zamiast imienia
    albo nazwisko dwuczłonowe; jedna praca oryginału przeniesiona na
    duplikat (duplikat nie ma dyscypliny, więc ta praca jest też
    rozbieżnością „brak przypisania”);
  - zdublowane czasopisma — ten sam ISSN, inna nazwa, bez odpowiednika
    w PBN, z jedną przeniesioną pracą;
  - zdublowane prace ciągłe — ten sam tytuł, rok, czasopismo i autorzy
    (co druga także z tym samym DOI);
  - rozbieżne dyscypliny autorów prac (dyscyplina spoza przypisań autora
    albo jej brak) i punkty pracy inne niż punktacja czasopisma.

  Generator ich nie wyszukuje — deduplikatory i porównania uruchamia
  użytkownik („Skanuj” na ekranie deduplikatora). Skan znajdzie też
  trochę „naturalnych” podobieństw: losowe nazwiska i tytuły czasem się
  powtarzają.
- **Lustro PBN** (`--bez-pbn`) — lokalne tabele PBN wypełnione tak, jakby
  BPP pobrało je z PBN; bez sieci i bez tokenu:
  - instytucja (uczelnia demo), czasopisma z punktami i dyscyplinami,
    wydawcy z punktami, naukowcy (autorzy z dyscypliną), publikacje
    (~70% prac), oświadczenia instytucji, historia wysyłki (~85% wysłane,
    ~10% błąd, ~5% w toku);
  - celowe różnice: inna punktacja (~10% czasopism, jeden rok) lub
    dodatkowa dyscyplina (~5%), literówka w tytule / brakujący autor /
    inny DOI (~5% publikacji), inna dyscyplina w oświadczeniu (~4%),
    oświadczenie autora spoza publikacji, 5 publikacji i 3 naukowców
    tylko w PBN, 2 czasopisma usunięte w PBN (z aktywnym następcą o tym
    samym ISSN — do przemapowania);
  - dane wyglądają na pobrane z PBN w chwili generowania: wpisy
    o pobraniu publikacji, osób z instytucji i czasopism mają tę datę
    i użytkownika „system” (na świeżej instalacji nie ma jeszcze kont).
    Jak po prawdziwym pobraniu, po 7 dniach ekrany PBN zaczną prosić
    o świeże dane.

  Porównań BPP↔PBN generator nie uruchamia — listy rozbieżności
  (dyscypliny z oświadczeń, czasopisma) wypełniają się po kliknięciu
  „Przebuduj”/„Przelicz” na ich ekranach. Przyciski wysyłki do PBN nadal
  wymagają prawdziwego PBN.
- **Konta demo** (`--konta-demo`, domyślnie WYŁĄCZONE): `admin`
  (superużytkownik), `redaktor` (wprowadzanie danych, zgłoszenia
  publikacji, indeks autorów), `raporty` (generowanie raportów), `user`
  (bez uprawnień, powiązany z autorem demo). Hasło = login. Istniejącego
  konta generator nie zmienia. Hasła są jawne, więc to opcja tylko dla
  instancji demonstracyjnych — i nie dla bpp-wsl, gdzie pierwsze konto
  zakłada kreator (kreator pomija ten krok, gdy w bazie jest już
  jakiekolwiek konto).

Na skali bpp-wsl (200 autorów, 1000 + 500 prac) dodatki wydłużają
generowanie o kilka sekund.

## Plik POL-on do importu (`--polon-plik`)

Generator potrafi zapisać fałszywy eksport POL-on „Rozszerzone zestawienie
pracowników podmiotu" dla uczelni demo — do przećwiczenia „operacje → import
z POLON" i „ewaluacja → liczba N" na bazie demo.

Przy tworzeniu danych (plik powstaje na samym końcu):

```bash
uv run python src/manage.py create_demo_data --motyw wiedzmin --seed 42 \
    --polon-plik /tmp/ \
    --yes-i-am-sure --confirm-db <NAZWA_BAZY>
```

Na istniejącej bazie demo (wygenerowanej albo odtworzonej z dumpa; baza
jest tylko czytana):

```bash
uv run python src/manage.py generuj_plik_polon_demo --out /tmp/
```

Podanie katalogu daje nazwę jak w prawdziwym eksporcie
(`rozszerzone_zestawienie_pracownikow_podmiotu_na_dzien_wygenerowania_raportu_<RRRR-MM-DD>.xlsx`).

Domyślnie plik zawiera cztery dyscypliny z celem FTE N na rok: filozofia (16),
nauki teologiczne (5), biotechnologia (15), archeologia (14) — po imporcie
liczba N wychodzi ≥ 12 w trzech z nich, a „nauki teologiczne" są
nieraportowane (< 12). Własne dyscypliny i cele:
`--dyscypliny filozofia=16 "nauki teologiczne=5"` (w `create_demo_data`:
`--polon-dyscypliny`); nazwy muszą być dokładnie takie jak w słowniku
dyscyplin.

Zawartość pliku:

- ok. 75% wierszy to osoby w liczbie N (kilka w dwóch dyscyplinach, 60/40),
  po ok. 10% pracowników badawczo-dydaktycznych spoza N (B) i dydaktycznych (Z);
- do pliku trafiają tylko autorzy uczelni o **unikalnym** imieniu i nazwisku
  (importer nie rozstrzygnie imienników); brakujący ORCID dostaje fałszywy,
  poprawny numer (wyłączenie w `generuj_plik_polon_demo`: `--bez-orcid`);
- cztery celowo błędne wiersze: zatrudnienie w innej uczelni (pominięty),
  osoba spoza BPP, dyscyplina spoza słownika („eliksirologia stosowana") i
  osoba w N bez wymiaru etatu. Wyłączenie: `--bez-blednych-wierszy`
  (w `create_demo_data`: `--polon-bez-blednych-wierszy`).

Plik nie ma roku — zaimportuj go cztery razy, z polem „Rok" 2022, 2023, 2024
i 2025 (z „Zapisz zmiany do bazy"), a potem „Oblicz liczbę N". Plik ma
własny generator losowy, więc `--polon-plik` nie zmienia pozostałych danych
dla danego `--seed`.

> Skrypt `bin/docs-demo-sloty.py` oznacza **wszystkich** autorów jako „N" —
> po nim „nauki teologiczne" nie zejdą poniżej 12. Do pokazania dyscypliny
> nieraportowanej importuj plik na bazie bez tego skryptu.

## Sprzątanie

Manifest zapisany przy tworzeniu (np. `demo_data_manifest_*.json`):

```bash
uv run python src/manage.py cleanup_demo_data \
    --manifest <plik.json> --yes-i-am-sure --confirm-db <NAZWA_BAZY>
```

> Cleanup usuwa wyłącznie obiekty z manifestu (po PK) i ich historię —
> bezpieczny dla istniejących danych; razem z nimi znikają konta demo,
> lustro PBN i wpisy o pobraniu danych z PBN. Wyniki skanów i porównań
> uruchomionych przez użytkownika mogą potem wskazywać na usunięte
> rekordy — wystarczy uruchomić je ponownie. Po `create_demo_data` uruchom `denorm_flush`, by
> wypełnić cache opisów bibliograficznych.
