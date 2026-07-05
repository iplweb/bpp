# Design — `ewaluacja_liczba_n` per-uczelnia (R2, write+read)

Data: 2026-06-03
Gałąź: `feature/multi-hosted-config`
Kontekst: wątek G z `HANDOFF-multi-hosted.md`. Następny po R1 (slot read-side).

## Cel i zakres

W instalacji wielouczelnianej **liczba N liczona jest osobno per uczelnia**
(per dyscyplina). Dziś `ewaluacja_liczba_n` jest tylko CZĘŚCIOWO per-uczelnia:
`LiczbaNDlaUczelni`/`DyscyplinaNieRaportowana` mają FK `uczelnia`, widoki/komenda
przekazują uczelnię — ale **rdzeń liczenia jest globalny**: tabele udziałów
`IloscUdzialowDlaAutoraZaRok`/`...ZaCalosc` nie mają uczelni, a pipeline
`oblicz_liczby_n_dla_ewaluacji_2022_2025` kasuje i przebudowuje je GLOBALNIE
(z autorów wszystkich uczelni), więc dla każdej uczelni `LiczbaNDlaUczelni`
zawiera N policzone z autorów CAŁEJ bazy.

**W zakresie R2:**
- FK `uczelnia` na `IloscUdzialowDlaAutoraZaRok` i `IloscUdzialowDlaAutoraZaCalosc`,
- migracja + backfill (single→domyślna, multi-z-danymi→fail; jak `0425`),
- zawężenie CAŁEGO pipeline'u liczenia (`utils.py`) per uczelnia,
- filtrowanie odczytów (`views/export.py`, `views/list.py`, `views/verify.py`)
  po uczelni oglądającego,
- `oblicz_dyscypliny_nieraportowane` dostaje uczelnię (wszystkie wywołania).

**Poza zakresem R2:**
- Import z POLON (populuje `Autor_Dyscyplina`/`wymiar_etatu`) — żyje poza tą apką;
  R2 liczy z `Autor_Dyscyplina`. (Odnotowane jako osobny ewentualny wątek.)
- Federacja optymalizacji — świadomie odłożona (decyzja usera, nie teraz).
- Integrator (handoff §D), drobne (§E) — osobne wątki, po R2.

## Reguła wiodąca (decyzja usera)

**Uczelnia autora = `autor.aktualna_jednostka.uczelnia`.** Autor jest liczony do
liczby N danej uczelni wtedy i tylko wtedy, gdy jego `aktualna_jednostka`:
- jest ustawiona (NIE NULL), oraz
- `skupia_pracownikow == True` (NIE „obca jednostka").

Autor z `aktualna_jednostka=NULL` lub obcą jednostką jest **całkowicie pomijany**
— nie powstają dla niego żadne wiersze `IloscUdzialow*`, nie wchodzi do żadnej
liczby N. („Jego rekord sobie jest i tyle.")

## Invariant zgodności

Single-install: wszyscy autorzy z `aktualna_jednostka` w tej jednej uczelni liczą
się jak dziś → liczby N identyczne. **Jedyna świadoma różnica vs obecny stan:**
autorzy z `aktualna_jednostka=NULL`/obcą przestają być liczeni (dziś pipeline
liczył ich globalnie) — to korekta zgodna z regułą domenową, nie regresja.

## Zmiany schematu

`src/ewaluacja_liczba_n/models.py`:
- `IloscUdzialowDlaAutoraZaRok`: dodać `uczelnia = ForeignKey("bpp.Uczelnia",
  on_delete=CASCADE, null=True, blank=True)`; `unique_together` →
  `("autor", "dyscyplina_naukowa", "rok", "uczelnia")`.
- `IloscUdzialowDlaAutoraZaCalosc`: dodać `uczelnia` FK (jw.); `unique_together` →
  `("autor", "dyscyplina_naukowa", "rodzaj_autora", "uczelnia")`.
- Pole nullable na czas migracji; po czystym rebuildzie zawsze wypełnione
  (autorzy bez przypisania są pomijani). NOT NULL ewentualnie później.

Migracje:
- M1: `AddField uczelnia` na obu modelach + zmiana `unique_together`.
- M2 (lub w M1, RunPython): backfill — `Uczelnia.objects.all()[:2]`: jeśli 1 →
  `update(uczelnia=ta)` na wierszach `uczelnia__isnull=True` obu tabel; jeśli są
  wiersze bez uczelni a uczelni ≠ 1 → `raise RuntimeError` (jak `0425`). Reverse: no-op.
- Reguła: tylko nowe pliki migracji.

## Pipeline liczenia (`utils.py`) — zawężenie per uczelnia

Wszystkie funkcje liczące dostają/propagują `uczelnia` i operują WYŁĄCZNIE na
wierszach tej uczelni:

- `oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia, rok_min, rok_max)`:
  - delete: `IloscUdzialowDlaAutoraZaRok.objects.filter(uczelnia=uczelnia, **lata).delete()`
    (dziś: globalny `filter(**lata).delete()`),
  - iteracja: `Autor_Dyscyplina.objects.filter(**lata,
    autor__aktualna_jednostka__uczelnia=uczelnia,
    autor__aktualna_jednostka__skupia_pracownikow=True)`
    (zawężenie do autorów tej uczelni; pomija NULL/obcą — `__uczelnia=` odrzuca NULL),
  - `create(..., uczelnia=uczelnia)`,
  - wywołania kroków 1–4 przekazują `uczelnia`.
- `oblicz_sumy_udzialow_za_calosc(uczelnia, rok_min, rok_max)`:
  - delete: `IloscUdzialowDlaAutoraZaCalosc.objects.filter(uczelnia=uczelnia).delete()`
    (dziś: globalny `objects.all().delete()` — to główny bug międzyuczelniany),
  - agregacja tylko z `ZaRok.filter(uczelnia=uczelnia, lata)`,
  - `create(..., uczelnia=uczelnia)`.
- `oblicz_srednia_liczbe_n_dla_dyscyplin(uczelnia, …)`: udziały z
  `ZaRok.filter(uczelnia=uczelnia, **lata)`; reszta (zapis `LiczbaNDlaUczelni`
  per uczelnia) bez zmian.
- `oblicz_dyscypliny_nieraportowane(uczelnia, rok=2025)`: suma z
  `ZaRok.filter(uczelnia=uczelnia, rok=rok)`.
- `dolicz_bonus_za_nieraportowana(uczelnia, nieraportowane_ids, …)`: iteruje
  `ZaCalosc.filter(uczelnia=uczelnia)`.
- `oblicz_liczbe_n_na_koniec_2025(uczelnia)`: udziały z
  `ZaRok.filter(uczelnia=uczelnia, rok=2025)`.

Zewnętrzni callerzy (`przelicz_n`, `views/index.py`, `ewaluacja_metryki/tasks.py`,
`ewaluacja_metryki/.../oblicz_metryki.py`) JUŻ przekazują `uczelnia` — bez zmian
po ich stronie (poza ewentualnym dopasowaniem sygnatur, jeśli któraś funkcja
zyskała wymagany parametr `uczelnia` — `oblicz_dyscypliny_nieraportowane` zyskuje).

## Odczyty (read views) — filtr po uczelni oglądającego

Źródło uczelni: `Uczelnia.objects.get_for_request(request)` (spójne z istniejącym
`views/index.py`; bez override superusera, bez zależności od `raport_slotow`).
- `views/export.py:23` (`ZaRok.filter`), `:207` (`ZaCalosc.all()`) → `.filter(uczelnia=U)`.
- `views/list.py:184,211,223` (`ZaRok`), `:331` (`ZaCalosc.all()`) → `.filter(uczelnia=U)`.
- `views/verify.py:227` (`ZaRok rok=2025`) → `.filter(uczelnia=U)`.
- `views/list.py` wywołania `oblicz_dyscypliny_nieraportowane()` (:113,243,357,412)
  → przekazać `uczelnia=U`.

(Te widoki są w kontekście jednej uczelni — `RaportSlotowUczelnia`-podobnym —
więc `get_for_request` daje uczelnię z site'u oglądającego.)

## Testy

- **Invariant single-install:** istniejące testy `ewaluacja_liczba_n` zielone;
  fixture jednouczelniany → `LiczbaNDlaUczelni`/udziały identyczne jak dziś
  (dla autorów z `aktualna_jednostka` w tej uczelni).
- **Multi-install izolacja:** 2 uczelnie, autorzy w obu (różne `aktualna_jednostka`);
  `oblicz_liczby_n_dla_ewaluacji_2022_2025(U1)` potem `(U2)` → `ZaRok`/`ZaCalosc`
  mają wiersze obu uczelni (drugi przebieg NIE kasuje wierszy U1); `LiczbaNDlaUczelni`
  U1 policzone tylko z autorów U1, U2 tylko z autorów U2.
- **Wykluczenie nieprzypisanych:** autor z `aktualna_jednostka=NULL` i autor z
  jednostką `skupia_pracownikow=False` → ZERO wierszy `IloscUdzialow*`, brak wpływu
  na liczbę N.
- **Read view filtruje:** export/list/verify dla U1 nie pokazują wierszy U2.
- **Migracja backfill:** single → istniejące wiersze dostają domyślną uczelnię;
  (test jednostkowy backfillu opcjonalny — trudny na świeżej bazie testowej).

## Migracja i deploy

- Single-install: M-backfill wpisze domyślną uczelnię w legacy `IloscUdzialow*`;
  następny `przelicz_n` przeliczy poprawnie per uczelnia (identycznie).
- Multi-install z danymi: backfill **failuje** dopóki nie przeliczy się per uczelnia
  (admin: usuń stary cache udziałów / przelicz). Spójne z `0425`.

## Komendy weryfikacji

- Testy: `uv run pytest src/ewaluacja_liczba_n/ -q -p no:cacheprovider`.
- `uv run python src/manage.py makemigrations --check --dry-run`
  (z `PYTEST_TESTCONTAINERS_DISABLE=1 DJANGO_BPP_SKIP_DOTENV=1`).
- Lint: `uv run ruff check <pliki>` (NIE `--fix`).

## Po R2 (kolejka usera)

Integrator per-uczelnia (handoff §D) → drobne (§E). Federacja optymalizacji — olana.
