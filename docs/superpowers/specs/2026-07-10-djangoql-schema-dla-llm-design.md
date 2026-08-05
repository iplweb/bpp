# DjangoQL: ograniczony schemat + eksport dla LLM — design

Data: 2026-07-10
Gałąź: `feat-schema-for-llm` (od `dev`)

## Problem

`manage.py djangoql_describe_schema_for_llm bpp.Rekord --format=compact` na
domyślnym `DjangoQLSchema` dosięga **214 modeli** (55 aplikacji: PBN sync,
importery, deduplikatory, audyt, cache/views, admin plumbing) → 188 KB / 3419
linii. Dla LLM piszącego zapytania bibliograficzne to szum — realnie liczy się
~60 modeli rdzenia bibliograficznego.

Ten sam nadmiar dotyka widoku **„Szukaj zapytaniem"** (`bpp.views.zapytanie`),
który używa `BppQLSchema` — autocomplete podpowiada 214 modeli wewnętrznych.

## Cel

1. **Ograniczyć** przestrzeń modeli DjangoQL do allow-listy (~63 modele).
2. Użyć tego ograniczonego schematu **zarówno** w eksporcie dla LLM **jak i**
   w widoku „Szukaj zapytaniem" (+ walidacja eksportu multiseek→DjangoQL).
3. **Wygenerować** zacommitowany, ostemplowany wersją BPP plik compact dla LLM.
4. **Adminy** (`DjangoQLSearchMixin`) zostają na pełnym `BppQLSchema` (bez zmian).

## Mechanizm

DjangoQL przycina graf modeli przez `include` (allow-lista) **albo** `exclude`
(deny-lista), wzajemnie wykluczające się. Przy proporcji 214 : ~63 **allow-lista
jest odporniejsza**: nowe aplikacje nie zaśmiecą schematu, nic wrażliwego
(`bppuser`, `auth`, wewnętrzne PBN) nie wycieknie domyślnie. Wykluczenie modelu
usuwa też krawędzie (relacje) do niego — dokładnie to, czego chcemy.

## Architektura — jedna allow-lista, trzej konsumenci

```
SEARCH_ALLOWLIST  (63 klasy, w src/bpp/djangoql_schema.py, rozwiązywane
                   leniwie przez apps.get_model — bez top-level importów pbn_api/
                   ewaluacja_common, żeby nie tworzyć cykli importów)

BppQLSchemaOgraniczony(BppQLSchema)   include = SEARCH_ALLOWLIST
    ├─ widok „Szukaj zapytaniem"   (BppZapytanieSchema alias, zapytanie.py)
    └─ walidacja multiseek→DjangoQL (_REKORD_SCHEMA, multiseek_registry/
       djangoql_export.py)  — spójność „konwertuj → uruchom"

RekordLLMSchema(ExtrasSchema)          include = SEARCH_ALLOWLIST
    └─ komenda opisz_schemat_djangoql_dla_llm → src/bpp/data/
       rekord_djangoql_schema.compact.txt

BppQLSchema  (BEZ ZMIAN)  ← adminy zachowują pełny schemat
```

### Dlaczego dwie klasy (a nie jedna)

- Widok chce **pickerów** `<fk>__rel` (UX autocomplete) → baza `BppQLSchema`
  (`RelPickerSchemaMixin` + `ExtrasSchema`).
- Eksport LLM chce **czysto** (pickery generują błędy `FieldError` w logu i
  puste object_reference'y) → baza `ExtrasSchema` (agregaty + części dat, bez
  pickerów). Zapytanie napisane wg schematu bez pickerów **jest poprawne** wobec
  pełniejszego schematu widoku (pickery są addytywne), więc nauka bez pickerów
  jest bezpieczna.
- Obie dzielą **tę samą** `SEARCH_ALLOWLIST` — jedno źródło prawdy, brak dryfu.

## Allow-lista (64 modele)

> Uwaga: w toku implementacji dołączono też `bpp.ZewnetrzneBazyDanychView` —
> rekordową ścieżkę zapytań multiseek „Zewnętrzna baza danych"
> (`zewnetrzne_bazy.baza`). Osadzanie wartości słownikowych w commitowanym
> artefakcie ograniczono do bezpiecznych, standardowych tablic referencyjnych
> (`RekordLLMSchema.fk_options` + domyślne `--max-fk-options 0`), żeby do repo
> open-source nie trafiały dane instytucji (tytuły publikacji, abstrakty).

Rdzeń bibliograficzny + świadome „ratunki" (decyzje użytkownika):

- **Rekord + typy:** rekord, wydawnictwo_ciagle, wydawnictwo_zwarte, patent,
  praca_doktorska, praca_habilitacyjna
- **Autorstwo:** autorzy, wydawnictwo_ciagle_autor, wydawnictwo_zwarte_autor,
  patent_autor, autor, autor_dyscyplina, autor_jednostka, typ_odpowiedzialnosci,
  funkcja_autora, tytul, plec
- **Struktura:** jednostka, wydzial, uczelnia, rodzajjednostki
- **Źródło/wydawca:** zrodlo, konferencja, seria_wydawnicza, wydawca,
  poziom_wydawcy, rodzaj_zrodla, zasieg_zrodla
- **Słowniki:** charakter_formalny, typ_kbn, jezyk, dyscyplina_naukowa,
  status_korekty
- **Open access:** tryb_openaccess_wydawnictwo_ciagle,
  tryb_openaccess_wydawnictwo_zwarte, licencja_openaccess,
  wersja_tekstu_openaccess, czas_udostepnienia_openaccess
- **Patenty:** rodzaj_prawa_patentowego
- **Streszczenia/tytuły obce:** wydawnictwo_{ciagle,zwarte}_{streszczenie,tytul}
- **Bazy zewnętrzne:** zewnetrzna_baza_danych,
  wydawnictwo_{ciagle,zwarte}_zewnetrzna_baza_danych
- **Słowa kluczowe:** taggit.tag
- **Nagrody:** nagroda, organprzyznajacynagrody
- **Ratunek B (informacja_z):** zrodlo_informacji
- **Ratunek C (zatrudnienie):** grupa_pracownicza, wymiar_etatu, kierunek_studiow
- **Ratunek A (PBN id):** pbn_api.{Publication, Scientist, Institution, Language,
  Conference, Publisher, Journal}, bpp.cache_punktacja_autora (dane dyscyplin)
- **Ratunek D-part:** charakter_pbn, ewaluacja_common.rodzaj_autora

Świadomie **poza** allow-listą (nie da się odpytywać w widoku, znikają z LLM):
- `bppuser` / `auth` (wrażliwe), `sites.site`, `contenttypes.contenttype`
  (plumbing), taggit `tagged_items` (through — słowa kluczowe idą przez
  `slowa_kluczowe → taggit.tag`), `publikacje_habilitacyjne` (through),
- 183 reverse-accessory do modeli wewnętrznych (pipeline'y importu/dedup/
  ewaluacji/PBN) — to sedno odszumienia.

Model z allow-listy **nieosiągalny** BFS-em z `Rekord` (brak ścieżki DjangoQL)
jest po cichu pomijany (dotyczy m.in. `grant`/`grant_rekordu` — dlatego ich nie
ma).

## Komenda `opisz_schemat_djangoql_dla_llm`

`src/bpp/management/commands/opisz_schemat_djangoql_dla_llm.py` — BPP-owy
bliźniak `djangoql_describe_schema_for_llm`. Woła
`djangoql.llm.describe_schema_for_llm(RekordLLMSchema(Rekord), …)`.

Flagi (mirror djangoql + BPP):
- `--format {compact,json}` (domyślnie `compact`)
- `--max-fk-options N` (domyślnie 50 — słowniki poniżej progu wstawiają wartości)
- `--output PATH` (domyślnie `src/bpp/data/rekord_djangoql_schema.compact.txt`)
- `--stdout` (drukuj zamiast zapisu)
- `--model` (domyślnie `bpp.Rekord`), `--schema` (dotted path; domyślnie
  `RekordLLMSchema`)

**Stempel wersji:** nagłówek pliku zawiera `django_bpp.version.VERSION` — **bez
znacznika czasu** (stabilny diff między regeneracjami). Dla `compact` nagłówek
to linie `#`; dla `json` klucz `bpp_version` na szczycie obiektu.

Nagłówek compact:
```
# BPP <VERSION>
# Model: bpp.Rekord   Schemat: bpp.djangoql_schema.RekordLLMSchema
# Wygenerowano: manage.py opisz_schemat_djangoql_dla_llm
# Plik generowany — nie edytuj ręcznie.
```

## Artefakt

`src/bpp/data/rekord_djangoql_schema.compact.txt` — 63 modele, ~142 KB / ~1251
linii (z wartościami słownikowymi z realnej bazy; wartości to publiczne słowniki
referencyjne — charakter, język, dyscyplina — nie PII). Snapshot generowany raz,
commitowany; każda instancja może zregenerować własny komendą.

## Obsługa błędów

- Pobranie wartości relacji degraduje miękko w bibliotece (log + pominięcie).
- Komenda: walidacja że schemat się buduje; niezerowy exit przy błędzie zapisu.

## Ryzyka / zmiana zachowania

- Widok „Szukaj zapytaniem" **traci** możliwość odpytywania relacji do
  wykluczonych modeli. Po ratunkach jedyne realne straty to: `autor.user`
  (wrażliwe — celowo), `uczelnia.site`, taggit `tagged_items`,
  `publikacje_habilitacyjne`. Skalary (rok, doi, punkty_kbn…) i wszystkie
  relacje bibliograficzne zostają.
- Zapisane zapytania (`Zapytanie`) odwołujące się do wykluczonych pól przestaną
  działać w widoku — ryzyko niskie (pola wewnętrzne rzadko w zapytaniach usera).
- Multiseek→DjangoQL waliduje teraz wobec ograniczonego schematu — wszystkie
  pola multiseek muszą mieścić się w allow-liście (pokryte testem coverage).

## Testy

Nowy `src/bpp/tests/test_djangoql_schema_llm.py`:
1. `SEARCH_ALLOWLIST` — wszystkie etykiety rozwiązują się, bez duplikatów.
2. `RekordLLMSchema(Rekord).models` ⊆ allow-lista; obecne rdzenne (rekord, autor,
   zrodlo, charakter_formalny, dyscyplina_naukowa); **nieobecne** wrażliwe
   (bppuser, auth.user, contenttypes.contenttype, sites.site).
3. `BppQLSchemaOgraniczony(Rekord)` — start model = `bpp.rekord`; odrzuca pole do
   wykluczonego modelu (`autor.user = None` → `DjangoQLSchemaError`); przyjmuje
   `charakter_formalny.nazwa ~ "x"` i `pbn_uid != None` (PBN uratowane).
4. Komenda: `--stdout` → zaczyna się od `# BPP <VERSION>`, zawiera
   `start model: bpp.rekord`; `--format json --stdout` → poprawny JSON z
   `bpp_version`; `--output <tmp>` tworzy plik.

Regresja (uruchomić): `test_zapytanie.py`, `test_multiseek_djangoql_coverage.py`,
`test_multiseek_djangoql_*` (roundtrip/export), adminowe DjangoQL (bez zmian —
pełny schemat).

## Pliki

- `src/bpp/djangoql_schema.py` — +`_SEARCH_ALLOWLIST_LABELS`, `SEARCH_ALLOWLIST`,
  `BppQLSchemaOgraniczony`, `RekordLLMSchema`.
- `src/bpp/views/zapytanie.py` — `BppZapytanieSchema = BppQLSchemaOgraniczony`.
- `src/bpp/multiseek_registry/djangoql_export.py` — `_REKORD_SCHEMA =
  BppQLSchemaOgraniczony(Rekord)`.
- `src/bpp/management/commands/opisz_schemat_djangoql_dla_llm.py` — nowa.
- `src/bpp/data/rekord_djangoql_schema.compact.txt` — artefakt.
- `src/bpp/tests/test_djangoql_schema_llm.py` — testy.
- newsfragment towncrier.
