# Import POLON / absencji — „Uruchom ponownie z zapisem do bazy"

Data: 2026-07-07
Gałąź: `feature/import-polon-zapis-do-bazy`

## Problem

Importy w aplikacji `import_polon` (`ImportPlikuPolon` — dyscypliny,
`ImportPlikuAbsencji` — absencje) mają tryb „dry-run": pole
`zapisz_zmiany_do_bazy` (default `False`) decyduje, czy `perform()` faktycznie
zapisuje dane do bazy, czy tylko analizuje i pokazuje podgląd.

Gdy użytkownik uruchomił import BEZ zapisu (dry-run) i na stronie wyników widzi,
że wynik jest poprawny, **nie ma sposobu, by ten sam import „domknąć" zapisem do
bazy** bez tworzenia nowego importu od zera (ponowny upload pliku, ponowne
ustawienie parametrów). Istniejący reset (`RestartLongRunningOperationView`,
URL `.../regen/`) uruchamia ponownie z **tą samą** wartością flagi — reset
dry-runa daje znów dry-run.

## Cel

Na stronie wyników dry-runa udostępnić akcję „uruchom ponownie, ale tym razem
zapisz do bazy": reset istniejącego obiektu z przestawieniem
`zapisz_zmiany_do_bazy` na `True`.

Zakres: **oba** importery (POLON + absencje) — dzielą tę samą maszynerię.

## Mechanika (stan istniejący)

- Oba modele dziedziczą po `long_running.models.Operation`.
- `Operation.mark_reset()` (atomic): czyści `started_on`, `finished_on`,
  `finished_successfully`, `traceback`, woła `on_reset()` (kasuje wiersze-dzieci)
  i zapisuje obiekt.
- `perform()` → `analyze_file_import_polon()` / `analyze_file_import_absencji()`
  zapisują do bazy tylko w miejscach `if parent_model.zapisz_zmiany_do_bazy:`.
- `LongRunningTaskCallerMixin.task_on_commit(pk)` kolejkuje
  `perform_generic_long_running_task` przez `transaction.on_commit`.
- Router (`LongRunningRouterView`) po sukcesie odsyła na stronę wyników.

**Wniosek: żadna migracja ani zmiana modeli nie jest potrzebna** — pole już
istnieje. Funkcja to widok + URL + szablon + przyciski.

## Rozwiązanie

### Przepływ

```
[Wyniki dry-runa]  (zapisz_zmiany_do_bazy == False, finished_successfully)
   │ przycisk „Zapisz ten import do bazy" → GET strona potwierdzenia
   ▼
[Strona potwierdzenia]  ostrzeżenie + formularz POST + „Anuluj"
   │ POST
   ▼
[ZapiszDoBazy view]  guard: owner + finished + not zapisz_zmiany_do_bazy
   │ object.zapisz_zmiany_do_bazy = True
   │ object.mark_reset()          # czyści stan + kasuje wiersze-dzieci
   │ task_on_commit(pk)            # ponowne perform() — tym razem zapis
   ▼
[Router → progress → wyniki]  zielony callout „Zmiany wprowadzono do bazy"
```

### Decyzja: mutacja istniejącego obiektu (nie klon)

Przestawiamy flagę na tym samym obiekcie i resetujemy go — dosłownie „taki
reset, ALE modyfikuj bazę". Reużywa całą maszynerię `mark_reset`, zero
kopiowania pliku, a strona wyników po zapisie wiernie odzwierciedla stan.
Utrata śladu „to był kiedyś dry-run" jest akceptowalna.

### Komponenty

1. `src/import_polon/views/` — współdzielony mixin `ZapiszDoBazyMixin`
   (`RestrictToOwnerMixin` + `LongRunningTaskCallerMixin`):
   - `get`: renderuje szablon potwierdzenia.
   - `post`: guard → flip flagi → `mark_reset()` → `task_on_commit` → redirect
     na router.
   - Dwie cienkie podklasy: `ZapiszDoBazyImportPolonView`,
     `ZapiszDoBazyImportAbsencjiView` (jak istniejące `RestartImportView` /
     `RestartImportAbsencjiView`).
2. **Guard** (POST): `finished_on is not None` ORAZ
   `zapisz_zmiany_do_bazy is False`. Inaczej redirect bez akcji (idempotencja —
   ochrona przed podwójnym zapisem).
3. `urls.py` — dwie ścieżki: `dane/<uuid:pk>/zapisz-do-bazy/`,
   `absencje/<uuid:pk>/zapisz-do-bazy/`
   (nazwy: `importplikupolon-zapisz-do-bazy`,
   `importplikuabsencji-zapisz-do-bazy`).
4. Szablon współdzielony `templates/import_polon/potwierdz_zapis_do_bazy.html` —
   nazwa pliku, rok/typ, ostrzeżenie o modyfikacji bazy, POST-submit + „Anuluj".
5. Przyciski w calloutach dry-run:
   - `wierszimportuplikupolon_list.html:169-175` (gałąź `{% else %}`),
   - `wierszimportuplikuabsencji_list.html` (analogiczny callout).
   Link GET do strony potwierdzenia; widoczny tylko dla dry-runa, więc po
   zapisie sam znika (results pokaże wtedy zielony `if`-callout).

### Bezpieczeństwo / obsługa błędów

- Zapis wyłącznie przez **POST** (GET tylko pokazuje potwierdzenie) — prefetch/
  robot nie zmodyfikuje bazy.
- `RestrictToOwnerMixin` — tylko właściciel importu (inny user → 404).
- Ponowny POST po już-zapisanym imporcie → guard → redirect, brak podwójnego
  zapisu.

## Testy (TDD)

Dla POLON i absencji symetrycznie:

- POST na dry-run: flaga → `True`, stan zresetowany (`started_on is None`
  bezpośrednio po `mark_reset`), task zakolejkowany
  (`django_capture_on_commit_callbacks`).
- GET: renderuje stronę potwierdzenia (status 200, właściwy template).
- Guard: POST na imporcie z `zapisz_zmiany_do_bazy=True` nie resetuje / redirect.
- Ownership: inny user → 404.

## Poza zakresem

- Klonowanie importu / zachowanie osobnego rekordu dry-runa.
- Zmiana zachowania istniejącego `.../regen/`.
- Idempotencja zapisu na poziomie domeny (upsert `Autor_Dyscyplina`) — to
  istniejąca odpowiedzialność rdzenia importu.
