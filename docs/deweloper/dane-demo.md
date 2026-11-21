# Dane demo (`create_demo_data`)

Generator syntetycznych danych demo z wymiennymi motywami.

## Szybki start

```bash
uv run python src/manage.py create_demo_data \
    --motyw wiedzmin \
    --autorow 200 --ile-ciaglych 1000 --ile-zwartych 500 \
    --yes-i-am-sure --confirm-db <NAZWA_BAZY>
```

## Motywy (`--motyw`)

- `realistyczny` (domyślny) — polskie dane akademickie
- `lem` — Stanisław Lem
- `wiedzmin` — Wiedźmin
- `harry-potter` — Harry Potter
- `disney` — Disney

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
> bezpieczny dla istniejących danych. Po `create_demo_data` uruchom `denorm_flush`, by
> wypełnić cache opisów bibliograficznych.
