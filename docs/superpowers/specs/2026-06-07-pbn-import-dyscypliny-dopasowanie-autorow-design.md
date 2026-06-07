# Import PBN — dopasowanie autorów po imieniu/nazwisku oraz odporne przypisywanie dyscyplin

Data: 2026-06-07
Branch: `feature/pbn-dyscypliny-autoprzypisanie` (baza: `feature/multi-hosted-config`)
Worktree: `/Users/mpasternak/Programowanie/bpp-pbn-dyscypliny`

## Problem

Integracja oświadczeń z PBN (`integruj_oswiadczenia_z_instytucji_pojedyncza_praca`)
ma trzy powiązane wady, które ujawniły się w sesji importu #11:

1. **Twardy crash całej sesji importu na konflikcie dyscyplin.** Gdy autor ma na
   dany rok przypisaną JEDNĄ dyscyplinę, a PBN przynosi INNĄ, kod podnosi
   `raise Exception("Nie ma przypsiania do {X}, ale jakeis inne jest...")`. Wyjątek
   propaguje przez `integruj_oswiadczenia_z_instytucji` → `statement_import.run` i
   **wywala całą sesję importu** (status: Błąd). Jeden konflikt na jednym autorze
   zabija wszystko dalej.

2. **Szum „autor nie znaleziony w publikacji".** Raport niespójności
   `author_not_found` odpala się ZANIM uruchomi się logika ratunkowa (tiery
   dopasowania po imieniu/nazwisku). Skutek: dashboard pokazuje jako problem prace,
   które de facto da się (albo dałoby się) automatycznie dopasować — bo w BPP jest
   współautor o IDENTYCZNYM imieniu i nazwisku, tylko z innym ID niż naukowiec
   wskazany w oświadczeniu PBN. Przykłady: Janas Adam, Szpyt Kamil, Daren Artur.

3. **Brak auto-przypisania dyscypliny przy luźnym dopasowaniu.** Gdy autor jest
   współautorem pracy w PBN i ma tam oświadczoną dyscyplinę, a w BPP brak
   jakichkolwiek przypisań dyscyplin na ten rok — można bezpiecznie założyć
   przypisanie na podstawie danych PBN, zostawiając ślad w logu/uwagach. Częściowo
   już zaimplementowane (gałąź `Autor_Dyscyplina.DoesNotExist`), ale bez procentów
   i bez spójnego raportowania.

### Stan obecny (kluczowe pliki)

- `src/pbn_integrator/utils/statements.py`
  - `integruj_oswiadczenia_z_instytucji_pojedyncza_praca` (linie ~36–300):
    - linia ~95: `aut = elem.get_bpp_autor()` — naukowiec PBN → Autor BPP.
    - linie ~114–117: tier-1, dopasowanie po dokładnym `autor=aut`.
    - linia ~126: **przedwczesny** raport `author_not_found`.
    - linie ~137–222: tiery 2–4 (nazwisko/imię iexact, zamienione, znormalizowane).
    - linie ~224–265: gdy są dyscypliny → `rec.autor = aut` (podmiana autora) +
      raport `author_auto_fixed`.
    - linie ~266–281: ustawienie dyscypliny; tu jest `raise Exception` na konflikcie.
- `src/pbn_api/models/oswiadczenie_instytucji.py`
  - `get_bpp_autor` (linie 84–136): własne 4-tier dopasowanie (pbn_uid, ORCID,
    nazwisko/imię iexact, znormalizowane).
  - `get_bpp_discipline` (linie 175–181): `disciplines["name"]` → `Dyscyplina_Naukowa`.
- `src/bpp/models/abstract/authors.py`
  - `_waliduj_dyscypline` (linie ~155–188): rzuca `ValidationError`, gdy autor nie ma
    `Autor_Dyscyplina` (po `dyscyplina_naukowa` LUB `subdyscyplina_naukowa`) na rok
    rekordu.
- `src/bpp/models/dyscyplina_naukowa.py`
  - `Autor_Dyscyplina` (linie 93–209): `unique_together = (rok, autor)` — DOKŁADNIE
    jeden wiersz na (autor, rok). Dwa „sloty": `dyscyplina_naukowa` (wymagana,
    `procent_dyscypliny`) + `subdyscyplina_naukowa` (opcjonalna,
    `procent_subdyscypliny`). `clean()` pilnuje sumy procentów ≤ 100 i że
    dyscyplina ≠ subdyscyplina.

## Cel

- Import PBN **nigdy nie wywala się** na konflikcie dyscyplin — konflikt staje się
  raportowaną niespójnością (ostry warning + log), import leci dalej.
- Współautorzy o identycznym imieniu/nazwisku (inne ID) są **automatycznie
  dopasowywani**, a niespójność jest raportowana jako informacyjna, nie alarmowa.
- Autorzy, którzy NIE są współautorami pracy w BPP — zostają jako `manual_fix` z
  opisowym komunikatem; **nigdy nie dopisujemy** ich automatycznie do publikacji.
- Auto-zakładane przypisania dyscyplin dostają sensowne procenty (100 dla jednej,
  50/50 dla dwóch) i zawsze ślad w logu/uwagach „automatycznie — brak danych".

## Rozwiązanie

### Część 1 — odporne przypisywanie dyscypliny (problem 1 + 3)

Nowy helper (proponowana lokalizacja: `src/pbn_integrator/utils/dyscypliny.py`):

```python
class WynikPrzypisaniaDyscypliny(enum.Enum):
    BRAK_ZMIAN = "brak_zmian"           # D już jest główną lub sub na ten rok
    UTWORZONO = "utworzono"             # nowy wiersz, dyscyplina = D, 100%
    DODANO_SUB = "dodano_sub"           # dopisano D jako subdyscyplinę
    KONFLIKT_BRAK_MIEJSCA = "konflikt"  # oba sloty zajęte, D różna od obu

def przypisz_dyscypline_pbn(autor, rok, dyscyplina) -> WynikPrzypisaniaDyscypliny:
    ...
```

Logika (jeden wiersz `Autor_Dyscyplina` na (autor, rok)):

| Sytuacja | Wynik | Akcja |
|---|---|---|
| Brak wiersza na ten rok | `UTWORZONO` | utwórz wiersz; `dyscyplina_naukowa = D`, `procent_dyscypliny = 100` |
| D == główna lub D == sub | `BRAK_ZMIAN` | nic |
| Wiersz jest, sub pusty, D ≠ główna | `DODANO_SUB` | `subdyscyplina_naukowa = D`; procenty wg reguły niżej |
| Oba sloty zajęte, D ≠ obie | `KONFLIKT_BRAK_MIEJSCA` | **nie ruszaj wiersza**; sygnał ostrego warninga |

**Reguła procentów (tylko gdy uzupełniamy BRAK danych — nigdy nie nadpisujemy
procentów wpisanych przez użytkownika):**

- `UTWORZONO` (jedna dyscyplina) → `procent_dyscypliny = 100`.
- `DODANO_SUB`, gdy istniejące procenty wyglądają na auto/puste
  (`procent_dyscypliny` jest `None` LUB `== 100` przy pustym `procent_subdyscypliny`)
  → rebalans `50/50` (`procent_dyscypliny = 50`, `procent_subdyscypliny = 50`).
- `DODANO_SUB`, gdy procenty NIE pasują do wzorca auto (użytkownik ma własny,
  ręczny podział) → **nie ruszamy** `procent_dyscypliny`; ustawiamy
  `procent_subdyscypliny = None`; emitujemy ostrzeżenie „procenty do weryfikacji".
- Każda auto-akcja zostawia w logu/uwagach: „automatycznie założono — brak danych
  w BPP".

Helper jest czysty i testowalny w izolacji (nie zna PBN-owej semantyki callbacków —
zwraca enum, a mapowanie na log/raport robi wołający).

**Zmiana w `statements.py`:** usunąć `raise Exception(...)` (≈ linia 274). Blok
ustawiania dyscypliny woła `przypisz_dyscypline_pbn(...)` i mapuje wynik:

- `UTWORZONO` → log info + `inconsistency_callback(type="discipline_auto_assigned")`;
  `rec.dyscyplina_naukowa_id = D.pk`.
- `DODANO_SUB` → log info + `discipline_added_as_sub`; `rec.dyscyplina_naukowa_id = D.pk`.
- `BRAK_ZMIAN` → `rec.dyscyplina_naukowa_id = D.pk` (D jest jednym ze slotów).
- `KONFLIKT_BRAK_MIEJSCA` → **ostry** warning do logu +
  `discipline_conflict_no_room`; **nie** ustawiamy `rec.dyscyplina_naukowa_id` na D
  — zostawiamy `rec.dyscyplina_naukowa` BEZ ZMIAN; import leci dalej.

`rec.dyscyplina_naukowa_id` ustawiamy WYŁĄCZNIE, gdy D jest po operacji jednym z
dwóch slotów autora — inaczej `_waliduj_dyscypline` (przy ewentualnym `rec.clean()`/
zapisie) znów by rzuciło.

**Uwaga korektności — bezwarunkowy `rec.save()` (statements.py:299).** `rec.save()`
jest wołany na końcu funkcji ZAWSZE, a Django `save()` NIE woła `clean()` (walidacja
tylko w jawnym `rec.clean()`). Wcześniej (linia ~245) blok ratunkowy robi
`rec.autor = aut` (podmiana współautora). Dlatego w gałęzi `KONFLIKT_BRAK_MIEJSCA`
NIE wolno zostawić `rec.dyscyplina_naukowa_id` ustawionego na D — inaczej zapis
utrwali parę `(autor, dyscyplina)`, której autor nie ma na ten rok (cicha
niespójność, bo `save()` nie waliduje). Reguła: na konflikcie zostawiamy
`rec.dyscyplina_naukowa` taką, jaka była przed próbą (najczęściej `None` dla świeżo
dopasowanego rekordu); ustawiamy ją na D dopiero, gdy D jest realnym slotem autora.

**Transakcje (F3).** Import biegnie w `transaction.atomic()`. Skoro zamieniamy
`raise` na „raportuj i jedź dalej", `update_or_create` w helperze osłaniamy
savepointem (`with transaction.atomic():`), aby ewentualny `IntegrityError` nie
unieważnił całej zewnętrznej transakcji sesji importu (wzorzec użyty już na tym
branchu przy rozdzielaniu faz importu).

### Część 2 — dopasowanie autora po imieniu/nazwisku (problemy 2 + 3)

Tiery dopasowania (2–4) już istnieją. Problem: raport `author_not_found` (≈ linia
126) odpala się PRZED ratunkiem. Przebudowa kolejności raportowania:

- **Tier-1 zawodzi, ale dalszy tier jednoznacznie (`len(matching_recs) == 1`)
  dopasowuje współautora TEJ pracy o tym samym imieniu/nazwisku** →
  raport `author_matched_by_name` (poziom: informacyjny) zamiast `author_not_found`.
  Następnie przypisanie dyscypliny przez Część 1. *(Janas / Szpyt / Daren.)*
- **Wszystkie tiery zawodzą = autor o tym samym imieniu/nazwisku istnieje w BPP, ale
  NIE jest współautorem tej pracy** → `author_needs_manual_fix` z opisowym
  komunikatem („Autor {X} (PBN) o tym samym imieniu i nazwisku istnieje w BPP, ale
  nie figuruje jako współautor tej pracy — wymaga ręcznej korekty"). **Nigdy** nie
  dopisujemy autora do publikacji. *(Bałdys-Waligórska — potwierdzone: log + ręka.)*

Dopasowanie pozostaje **jednoznaczne**: gdy `len(matching_recs) > 1` (kilku
współautorów o tym samym imieniu/nazwisku) → nie zgadujemy, raport ambiguity +
`manual_fix`.

**Relacja do istniejących typów raportów (F2 — co znika, co zostaje):**

- `author_not_found` (statements.py:126) — **USUWAMY** to wywołanie. Było
  przedwczesne (odpalało się przed ratunkiem), generowało fałszywy alarm dla prac,
  które dawały się dopasować. Sam tier-1 (po ID) wciąż może zawieść — ale to nie
  jest już „niespójność", tylko normalny przebieg ratunku.
- `author_auto_fixed` (statements.py:236) — **zastępujemy** przez
  `author_matched_by_name` (info). To ten sam moment (udane dopasowanie po
  imieniu/nazwisku + podmiana `rec.autor`), tylko z czytelniejszą nazwą i poziomem
  informacyjnym zamiast alarmowego.
- `no_override_without_disciplines` (statements.py:257) — **zostaje** bez zmian
  (dopasowano współautora, ale PBN nie przyniósł dyscypliny → nic nie nadpisujemy).
- `author_needs_manual_fix` (statements.py:211) — **zostaje**, doprecyzowujemy
  komunikat (autor o tym samym imieniu/nazwisku istnieje, ale nie jest współautorem
  tej pracy).

### Część 3 — taksonomia niespójności i komunikaty

Ujednolicone `inconsistency_type` (każdy raport niesie pracę i autora PBN/BPP oraz
dyscyplinę, jeśli jest):

| `inconsistency_type` | poziom | znaczenie |
|---|---|---|
| `author_matched_by_name` | info | auto-dopasowano współautora o tym samym imieniu/nazwisku (inne ID) |
| `author_needs_manual_fix` | warning | autor o tym samym imieniu/nazwisku istnieje, ale nie jest współautorem pracy |
| `discipline_auto_assigned` | info | utworzono `Autor_Dyscyplina` z PBN (100%) — „brak danych w BPP" |
| `discipline_added_as_sub` | info | dopisano subdyscyplinę (rebalans 50/50 lub procenty do weryfikacji) |
| `discipline_conflict_no_room` | warning (ostry) | oba sloty zajęte, dyscyplina z PBN różna od obu — nie zmieniono |

Komunikat dla `discipline_auto_assigned` w formacie czytelnym dla użytkownika:
„Autorowi {nazwisko imię} przypisano dyscyplinę {D} na podstawie pracy {tytuł},
rok {R} — automatycznie, brak danych w BPP."

## Pliki do zmiany

- **Nowy:** `src/pbn_integrator/utils/dyscypliny.py` — enum + `przypisz_dyscypline_pbn`.
- **Zmiana:** `src/pbn_integrator/utils/statements.py` — usunięcie `raise`, wołanie
  helpera, przebudowa kolejności raportów dopasowania autora. Przy okazji
  konsolidacja powtórzonych `elem.get_bpp_discipline()` (wołane 3× w linii 267/268/
  275 — każde to osobny `.get()`) do jednej zmiennej (F4).
- **Testy (nowe):**
  - `src/pbn_integrator/tests/test_dyscypliny.py` — unit dla helpera (4 wyniki +
    reguła procentów).
  - rozszerzenie istniejących testów `integruj_oswiadczenia_*` (lokalizacja wg
    konwencji w `src/pbn_integrator/tests/`).

Brak nowych migracji — model `Autor_Dyscyplina` bez zmian.

## Testowanie

**Unit — `przypisz_dyscypline_pbn`:**
- brak wiersza → `UTWORZONO`, `procent_dyscypliny == 100`.
- D == główna → `BRAK_ZMIAN`, brak zmian w bazie.
- D == sub → `BRAK_ZMIAN`.
- wiersz z główną (auto: 100, sub pusty), D inna → `DODANO_SUB`, `50/50`.
- wiersz z ręcznym podziałem (np. 70/—), D inna → `DODANO_SUB`, główna 70 nietknięta,
  `procent_subdyscypliny is None`, ostrzeżenie „do weryfikacji".
- oba sloty zajęte, D różna od obu → `KONFLIKT_BRAK_MIEJSCA`, brak zmian.

**Integracyjne — `integruj_oswiadczenia_z_instytucji_pojedyncza_praca`:**
- współautor o tym samym imieniu/nazwisku, inne ID → `author_matched_by_name`,
  dyscyplina przypisana, **brak wyjątku**.
- autor o tym samym imieniu/nazwisku spoza listy współautorów →
  `author_needs_manual_fix`, autor NIE dopisany do pracy.
- konflikt dyscyplin (oba sloty zajęte) → `discipline_conflict_no_room`, sesja
  importu kończy się sukcesem (brak `raise`).

Konwencje: pytest funkcyjny, `@pytest.mark.django_db`, `model_bakery.baker.make`.

## Punkty otwarte / do potwierdzenia przy rewizji

1. **Heurystyka „user ma dane".** „100 + pusty sub" traktujemy jako naszą auto-daną
   (rebalansowalną do 50/50). Każdy inny podział = dana użytkownika (nie ruszamy).
   Czy ta granica jest OK?
2. **Lokalizacja helpera** — `pbn_integrator/utils/dyscypliny.py`. Alternatywa:
   metoda na `Autor_DyscyplinaManager`. Wybrano wolną funkcję dla braku sprzężenia
   modelu z semantyką PBN.
