# Krok „Sprawdź w PBN" w importerze publikacji

Data: 2026-07-08
Autor: sesja Claude Code (feat/importer-pbn-check-step)

## Cel

Dla źródeł **NIE-PBN** dodać do wizarda importera publikacji nowy krok,
umieszczony bezpośrednio **przed** krokiem „Przegląd". W tym kroku operator
(jeśli jest zalogowany do PBN swoim tokenem) może wyszukać odpowiednik
importowanej pracy w PBN po **DOI**, **tytule** i **stronie WWW**, obejrzeć
znalezione rekordy i wybrać jeden z nich jako **odpowiednik PBN** importowanej
publikacji.

Wybór odpowiednika zasila `ImportSession.matched_data["pbn_mongo_id"]` — to samo
pole, które przy tworzeniu rekordu odczytuje istniejąca funkcja
`_link_pbn_uid`, ustawiając `record.pbn_uid`. Reszta pipeline'u tworzenia
rekordu pozostaje bez zmian.

## Kontekst kodu (stan zastany)

Wizard importera (`src/importer_publikacji/`) to sekwencja kroków HTMX:

```
Index → Fetch → Verify → Source → Authors → Punktacja → Review → Create → Done
```

- Każdy krok ma widok klasowy w `views/wizard.py` oraz parę funkcji
  `_render_<step>_step` / `_render_<step>_full` w `views/steps.py`.
- Nawigacja: przycisk „Dalej" to POST na URL kroku (zapisuje dane i zwraca
  partial następnego kroku); „Wstecz" to `hx-get` na poprzedni krok. Cel
  swap-a: `#importer-wizard`.
- Kolejność kroków jest zakodowana w DWÓCH miejscach, które trzeba zmieniać
  spójnie:
  1. co każdy widok POST renderuje jako następny partial,
  2. `ImportSession.get_continue_url()` — mapa `status → URL` używana do
     wznawiania przerwanej sesji.
- Breadcrumbs (`_breadcrumbs_oob.html`) NIE pokazują kroków — nie wymagają
  zmian.

### Istniejąca integracja PBN w kroku Verify (do usunięcia)

Krok Verify już dziś wywołuje `_check_pbn_by_doi(session)`
(`views/pbn_check.py`), który **cicho** sprawdza PBN po DOI i sam ustawia
`session.matched_data["pbn_mongo_id"]`. Zgodnie z decyzją projektową ten cichy
auto-set **zostaje usunięty** — jedynym źródłem powiązania PBN staje się nowy,
jawny krok z wyborem operatora.

Zachowujemy:
- `_link_pbn_uid(session, record)` — czyta `matched_data["pbn_mongo_id"]` przy
  tworzeniu rekordu. Nowy krok zasila to samo pole.
- Funkcje pomocnicze z `pbn_check.py` przydatne do obsługi błędów PBN
  (`_empty_pbn_result` itp.) — mogą być reużyte lub wzorowane.

### „Zalogowany do PBN"

Operator jest „zalogowany do PBN", gdy jego konto ma osobisty token OAuth:
`request.user.pbn_token` (niepusty) oraz `request.user.pbn_token_possibly_valid()`
(model `bpp.models.profile`). Klient PBN z tym tokenem buduje się przez
`uczelnia.pbn_client(request.user.pbn_token)`. Bez tokenu wywołanie API rzuca
`WillNotExportError` / `NeedsPBNAuthorisationException`.

Autoryzacja PBN: URL `pbn_api:authorize`, przyjmuje parametr `?next=<url>`
(po OAuth wraca na wskazaną stronę).

### Wyszukiwanie w PBN

- **Serwer PBN**: `client.search_publications(doi=…)`, `search_publications(title=…)`
  — wzorzec w `bpp/views/autocomplete/wydawnictwo_nadrzedne_w_pbn.py`. Zwraca
  listę dictów z co najmniej `mongoId`, `title`. Rekord ściągamy lokalnie przez
  `zapisz_mongodb(client.get_publication_by_id(mongoId), Publication)`.
- **Po WWW**: PBN API nie udostępnia wyszukiwania po adresie URL publikacji.
  Dopasowujemy w **lokalnym cache**: `pbn_api.Publication.objects.filter(
  publicUri__icontains=url)`. Pole `pbn_api.Publication.publicUri` przechowuje
  adres publikacji.

## Przepływ docelowy

Tylko dla **NIE-PBN** (`session.provider_name != "PBN"`):

```
… → Punktacja → [Sprawdź w PBN] → Przegląd → Utwórz
```

Dla źródła **PBN** krok jest pomijany (Punktacja → Przegląd, jak dziś).

### Zachowanie kroku „Sprawdź w PBN"

GET:
1. Jeśli źródło to PBN → redirect do Przeglądu (defensywnie, krok nie dotyczy).
2. Jeśli operator **niezalogowany** do PBN → panel informacyjny:
   - link „Zaloguj się do PBN" → `pbn_api:authorize?next=<url tego kroku>`,
   - przycisk „Pomiń — weryfikacja opcjonalna" → przejście do Przeglądu.
3. Jeśli operator **zalogowany** → wykonaj trzy wyszukiwania i pokaż wyniki.

Wyszukiwanie (`_search_pbn_equivalents`):
- `by_doi` — serwer PBN po DOI (jeśli sesja ma DOI), ≤10 pozycji.
- `by_title` — serwer PBN po tytule, ≤10 pozycji.
- `by_www` — lokalny cache po `publicUri` (jeśli sesja ma URL), ≤10 pozycji.
- Deduplikacja po `mongoId` — jeśli ten sam rekord trafia z kilku osi,
  pokazujemy go raz, oznaczając skąd trafił.
- Obsługa błędów PBN wzorowana na `pbn_check.py`: `NeedsPBNAuthorisationException`
  → potraktuj jak „niezalogowany"; `PraceSerwisoweException` → komunikat „PBN w
  trakcie prac serwisowych"; inne → komunikat błędu, bez wywalania kroku.

Wyświetlanie wyników: dla każdej osi lista ≤10 pozycji, każda z: tytuł, DOI,
rok, autorzy, link „otwórz w PBN" oraz przycisk „Wybierz jako odpowiednik".
Gdy w danej osi jest **dokładnie jeden** wynik — ta sama akcja wyboru z
komunikatem w duchu „czy akceptujesz ten rekord z PBN jako odpowiednik?".

POST-y (akcje HTMX):
- `pbn-select` (parametr `mongo_id`) — pobierz rekord lokalnie
  (`get_publication_by_id` + `zapisz_mongodb`), ustaw
  `matched_data["pbn_mongo_id"]`, przerysuj krok z panelem „Wybrany odpowiednik".
- `pbn-clear` — usuń `matched_data["pbn_mongo_id"]`, przerysuj krok.
- `pbn` (POST „Dalej") — `status = PBN_CHECK`, renderuj Przegląd.

Nawigacja: „Wstecz" → Punktacja; „Dalej" → Przegląd.

## Komponenty do zmiany / dodania

1. **`models.py`** — nowy status
   `ImportSession.Status.PBN_CHECK = "pbn_check", "Sprawdzenie w PBN"`.
   `get_continue_url()`:
   - `PUNKTACJA → "pbn"` gdy `provider_name != "PBN"`, w przeciwnym razie `"review"`,
   - `PBN_CHECK → "review"`.
   Jeśli `makemigrations --check` zażąda migracji `AlterField` dla `status`
   (rozszerzenie `choices`) — dołączyć wygenerowaną migrację (NIE edytować
   istniejących).

2. **`views/pbn_search.py`** (nowy moduł, logika testowalna/mockowalna):
   - `_operator_pbn_logged_in(user) -> bool`.
   - `_search_pbn_equivalents(session, user) -> dict` z kluczami
     `by_doi` / `by_title` / `by_www` (listy) oraz metainformacją o błędach
     (`error`, `needs_auth`).
   - `_select_pbn_equivalent(session, user, mongo_id)` — pobranie i zapis
     lokalny + ustawienie `matched_data`.

3. **`views/wizard.py`** — nowy `PbnCheckView` (GET / POST) oraz akcje
   `PbnSelectView`, `PbnClearView`. Modyfikacja `PunktacjaView.post`:
   po zapisaniu punktacji renderuj krok PBN (NIE-PBN) lub Przegląd (PBN).

4. **`views/steps.py`** — `_pbn_context`, `_render_pbn_step`, `_render_pbn_full`.

5. **`views/helpers.py`** — stała `STEP_PBN =
   "importer_publikacji/partials/step_pbn.html"`.

6. **`urls.py`** — trasy `pbn`, `pbn-select`, `pbn-clear`.

7. **`templates/.../partials/step_pbn.html`** — nowy szablon (Foundation CSS,
   monochromatyczne Foundation-Icons). Trzy sekcje wyników, panel wyboru,
   panel „niezalogowany", przyciski Wstecz/Dalej.

8. **`templates/.../partials/step_review.html`** — „Wstecz" prowadzi do kroku
   PBN dla NIE-PBN (lub Punktacji dla PBN). Wymaga flagi w kontekście review
   (np. `back_step_url`) — dodać w `_review_context`.

9. **`views/steps.py` (`_verify_context`)** — usunąć wywołanie
   `_check_pbn_by_doi` do auto-ustawiania `pbn_mongo_id`. (Sam `pbn_check.py`
   może zostać w repo — używany przez `_link_pbn_uid` i ewentualnie reużywany;
   usuwamy tylko cichy auto-set z kroku Verify oraz zależną prezentację
   `pbn_result` w szablonie Verify, jeśli istnieje.)

## Testy (TDD, pytest + model_bakery)

- `test_operator_pbn_logged_in` — token jest / brak / wygasły.
- `test_search_pbn_equivalents` (mock klienta PBN):
  - trzy osie zwracają wyniki; limit 10 na oś; dedup po `mongoId`;
  - WWW z lokalnego cache (`publicUri__icontains`);
  - `NeedsPBNAuthorisationException` → `needs_auth=True`;
  - `PraceSerwisoweException` → komunikat, brak wyjątku.
- `PbnCheckView` GET:
  - źródło PBN → redirect do review;
  - operator niezalogowany → panel z linkiem autoryzacji + „Pomiń";
  - operator zalogowany → wyniki wyszukiwania.
- `pbn-select` ustawia `matched_data["pbn_mongo_id"]` i pobiera rekord lokalnie;
  `pbn-clear` czyści pole.
- Przejścia:
  - `Punktacja.post` → krok PBN (NIE-PBN) vs → Review (PBN-source);
  - `PbnCheck.post` → Review;
  - `get_continue_url` dla `PUNKTACJA` (obie ścieżki) i `PBN_CHECK`.
- Regresja: usunięcie auto-checku z Verify nie psuje `_link_pbn_uid`
  (gdy `matched_data["pbn_mongo_id"]` ustawiony ręcznie → `record.pbn_uid`
  linkowany przy tworzeniu).

## Poza zakresem (YAGNI)

- Brak wyszukiwania po ISBN / objectId (spec: DOI / WWW / tytuł).
- Brak zmian w logice tworzenia rekordu poza zasilaniem `pbn_mongo_id`.
- Brak modyfikacji istniejących migracji.
- Brak zmian w krokach Source / Authors / Fetch.
- Krok jest **opcjonalny** — operator zawsze może przejść dalej bez wyboru
  odpowiednika (brak wymuszania powiązania PBN).

## Ryzyka i decyzje

- **Wydajność / czas odpowiedzi**: dwa zapytania sieciowe do PBN (DOI, tytuł)
  wykonują się synchronicznie w GET kroku. Akceptowalne — analogiczne do
  istniejącego `_check_pbn_by_doi` (jedno zapytanie w Verify). Błędy/timeouty
  degradują do komunikatu, nie wywalają kroku.
- **„Po WWW" tylko z lokalnego cache**: jeśli odpowiednik PBN nie był wcześniej
  pobrany lokalnie, wyszukiwanie po WWW go nie znajdzie. To świadomy
  kompromis — PBN API nie wspiera wyszukiwania po URL. DOI/tytuł idą na żywo do
  serwera i pokrywają większość przypadków.
- **Nowy status w `choices`**: rozszerzenie `TextChoices` na `CharField` nie
  zmienia schematu bazy; ewentualną migrację `AlterField` (kosmetyczną)
  dołączamy zgodnie z `makemigrations --check`.
