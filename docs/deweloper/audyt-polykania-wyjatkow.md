# Plan: logowanie „połykanych" wyjątków

## Cel

Żaden catch-all (`except Exception` / `except BaseException` / bare `except:`)
ani przypadek „pokazane userowi, nigdzie nie zalogowane" nie ma ginąć po cichu.
Minimum: pełny traceback w logach (`logger.exception`) + Rollbar tam, gdzie to
ścieżka produkcyjna (web/task/admin/model/importer). User może nadal widzieć
„wystąpił nieznany błąd" — ale my widzimy *co* się stało.

## Zakres (i czego NIE ruszamy)

- **W zakresie:** 105 cichych catch-all (`Exception`/`BaseException`/bare) +
  przypadki web-facing, które pokazują fallback userowi bez logu.
- **POZA zakresem:** ~140 `except Model.DoesNotExist: ...` — to idiomatyczny
  EAFP (oczekiwany control-flow, nie błąd). Logowanie ich byłoby szumem.
  Zostają nietknięte.
- `except <wąski typ z komentarzem>` (np. `CannotDeleteStatementsException`
  „PBN mówi że nie ma oświadczeń") — świadome, udokumentowane. Zostają.

## Wspólny helper

`src/bpp/util/wyjatki.py`:

```python
def zaloguj_polkniety_wyjatek(komunikat, *, logger=None, do_rollbar=True):
    """Woła się WEWNĄTRZ bloku except. Loguje pełny traceback + (opcjonalnie)
    raportuje do Rollbara. Rollbar best-effort (gdy nieskonfigurowany — sam log)."""
```

Re-eksport z `bpp.util` (fasada). Dzięki temu zmiana w jednym miejscu, a diff
w 30+ plikach jest jednolity i łatwy do review.

## Zasady stosowania

1. **BaseException → Exception** wszędzie, gdzie nie ma intencji łapania
   `KeyboardInterrupt`/`SystemExit` (czyli wszędzie tutaj) + logowanie.
2. **Web/admin/task/model/importer:** `do_rollbar=True` (domyślnie).
3. **Management commands / dev-utils** (`playwright_util`, `compare_dbtemplates`):
   logujemy (`do_rollbar=False` — bez szumu w monitoringu, ale log jest).
4. **`except (X.DoesNotExist, Exception)`** — rozbić: zostawić wąską klauzulę
   jako cichy control-flow, a `Exception` osobno z logowaniem.
5. Komunikat po polsku, konkretny: co robiliśmy, gdy padło.

## Etapy (1 commit / etap)

- **E1.** Helper `wyjatki.py` + re-eksport + test jednostkowy helpera.
- **E2.** Tier 1 — czyste `except ...: pass` (20 szt.).
- **E3.** `except BaseException` (22 szt.) — narrow + log.
- **E4.** Web-facing „pokazane, nie zalogowane" (admin/core, importer_publikacji,
  przemapuj_*, pbn_wysylka, zglos_publikacje, rozbieznosci_*).
- **E5.** Blok `pbn_import/utils/*` + `pbn_import/*` (~25 szt.).
- **E6.** `pbn_api/*`, `pbn_integrator/*`, reszta `except Exception`.
- **E7.** `bpp/*` (multiseek, admin, export, models, templatetags).
- **E8.** Self-review + `ruff` + uruchomienie testów dotkniętych modułów.

## Weryfikacja

- Po każdym etapie: `ruff format` + `ruff check` na dotkniętych plikach.
- Re-run analizatora AST — licznik cichych catch-all ma spadać do ~0
  (poza świadomie zostawionymi).
- Testy modułów, których dotknęliśmy (importer_publikacji, pbn_import).
