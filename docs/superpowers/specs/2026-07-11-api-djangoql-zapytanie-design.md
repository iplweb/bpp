# API BPP: wyszukiwanie DjangoQL po API (autoryzowane, read-only)

**Data:** 2026-07-11
**Autor:** Michał Pasternak (+ Claude)
**Status:** design zaakceptowany — w realizacji (gałąź `feat-api-zapytanie`)

## Cel

Wystawić istniejący silnik DjangoQL BPP (`apply_search` + uszczelniony schemat)
jako **autoryzowany** endpoint REST API — żeby zalogowany użytkownik (cookie-sesja)
oraz agent MCP (bearer) mogli zadawać **precyzyjne zapytania po rekordach** zamiast
tylko płaskiego FTS `?q=` z Fazy 0.

To rozszerzenie warstwy MCP: Faza 0 (`/api/v1/szukaj/`) daje anonimowy,
rankowany full-text; ten endpoint daje autoryzowane, strukturalne zapytania
(złożone warunki: rok + charakter + relacje autor/jednostka) nad trzema modelami.

### Czego dotyczy, a czego nie

- **Dotyczy:** odczyt przez DjangoQL nad `bpp.Rekord`, `bpp.Autor`, `bpp.Autorzy`.
- **NIE dotyczy:** zapisu (pozostaje read-only), innych modeli jako korzeni
  zapytania, publicznego/anonimowego dostępu (to jest gate'owane).

## Kontekst (ustalony z kodu)

- **Silnik już istnieje.** `djangoql.queryset.apply_search(qs, q, schema=…)`
  napędza dziś web-owy edytor „Szukaj zapytaniem" (`bpp.views.zapytanie`,
  `ZapytanieView`) — staff-only, modele Rekord + Autor.
- **Schematy DjangoQL** (`bpp.djangoql_schema`, obecne na `dev` po merge #524):
  - `BppQLSchema` — pełny, z auto-pickerami `<fk>__rel`; napędza wyszukiwarkę
    DjangoQL **w adminie**.
  - `BppQLSchemaOgraniczony(DeprecatedAndRestrictedFieldsMixin, BppQLSchema)` —
    web-edytor + walidacja eksportu multiseek; allow-lista `SEARCH_ALLOWLIST`,
    zachowuje pickery (autocomplete dla człowieka).
  - `RekordLLMSchema(DeprecatedAndRestrictedFieldsMixin, ExtrasSchema)` —
    generacja compact-schematu do promptu LLM; **bez pickerów** (agent uczy się
    notacji z kropką), `include = SEARCH_ALLOWLIST`, `fk_options`/
    `no_value_targets` (osadzanie wartości bezpiecznych słowników, twarda
    blokada nazw instytucji).
  - **Wspólny kontrakt bezpieczeństwa:** `DeprecatedAndRestrictedFieldsMixin`
    + `SEARCH_ALLOWLIST` — jeden zestaw dozwolonych modeli/pól; `SEARCH_ALLOWLIST`
    zawiera już `Rekord`, `Autor`, `Autorzy` (+ join-tables i słowniki).
- **Gate web-edytora:** `user_can_use_query_editor(user)` — superuser **albo**
  staff w grupie `GR_WPROWADZANIE_DANYCH`.
- **Rozbicie błędów:** `bpp/views/zapytanie.py` ma gotowe `_error_payload` /
  `_error_location` (mapują wyjątek DjangoQL na `{error, line, column, mark}`).
- **Bearer:** `oauth_mcp/authentication.py::StrictOAuth2Authentication`
  (na `dev` po merge #526) — 401 na zły bearer, przepuszcza sesję jako anon.

## Decyzje projektowe (WIĄŻĄCE)

| Wymiar | Decyzja |
|--------|---------|
| **Auth** | jeden endpoint, dwa wejścia: `authentication_classes = [SessionAuthentication, StrictOAuth2Authentication]` |
| **Gate** | reuse `user_can_use_query_editor` (superuser lub staff+grupa) — **ten sam kontrakt co web-edytor** |
| **Modele** | `bpp.Rekord`, `bpp.Autor`, `bpp.Autorzy` (i tylko te jako korzeń) |
| **Wyniki** | kompaktowa płaska projekcja per model (relacje jako string+URL, bez chodzenia po hyperlinkach) |
| **Schemat walidacji** | `RekordLLMSchema` (agent-facing, bez pickerów) — round-trip z tym, czego uczymy agenta |
| **Read-only** | tylko `GET`, `ListModelMixin` |
| **Gałąź** | `feat-api-zapytanie` od `dev` (komplet zależności obecny) |

## 1. Kształt endpointu — per-model

```
GET /api/v1/zapytanie/rekord/?q=<djangoql>&limit=&offset=
GET /api/v1/zapytanie/autor/?q=<djangoql>&limit=&offset=
GET /api/v1/zapytanie/autorzy/?q=<djangoql>&limit=&offset=
```

- DRF: bazowy `ZapytanieAPIBaseViewSet(GenericViewSet, ListModelMixin)` +
  3 cienkie podklasy (`ZapytanieRekordViewSet`, `…Autor…`, `…Autorzy…`),
  każda deklaruje `model`, `queryset`, `serializer_class`.
- Wspólne w bazie: `authentication_classes`, `permission_classes`, guardrail
  czasu, wykonanie `apply_search`, obsługa błędów, paginacja.
- Ścieżki per-model są self-describing → mapują się 1:1 na tooly MCP
  (`zapytanie_rekord`, `zapytanie_autor`, `zapytanie_autorzy`).
- Rejestracja w routerze `api_v1/urls.py` (basename `zapytanie_<model>`),
  pozycja w `CustomAPIRootView` (sekcja „search"/„zapytanie").

**Alternatywa odrzucona:** pojedynczy endpoint `/zapytanie/?model=rekord&q=…`
(jak web-widok). Per-model jest czytelniejsze w OpenAPI i dla tooli MCP.

## 2. Wykonanie zapytania

```python
qs = model.objects.all()
qs = apply_search(qs, q, schema=RekordLLMSchema).distinct()
```

- `.distinct()` — filtrowanie po relacjach „do wielu" (np.
  `autorzy.autor.nazwisko`) tworzy JOIN zwielokrotniający rekord; `.distinct()`
  zwija duplikaty (jak w web-widoku).
- **Puste `q`** → pusta lista (nie błąd), spójnie z zachowaniem `/szukaj/`.
- **Błąd DjangoQL** (`DjangoQLError`, `FieldError`, `ValidationError`,
  `ValueError`) → **HTTP 400** z ciałem `{error, line, column, mark}`.
  Wydzielić `_error_payload` / `_error_location` z `bpp/views/zapytanie.py`
  do wspólnego util (`bpp/djangoql_errors.py`) — **jedno źródło prawdy** dla
  web-widoku i API.

## 3. Guardrail wydajności (nowość względem web-edytora)

Web-edytor **nie ma** `statement_timeout` — bo to interaktywny człowiek, który
sam przerwie wolne zapytanie. API wyzwalane przez agenta to inny threat model
(pętle, patologiczne zapytania), więc:

- Owinąć wykonanie w `SET LOCAL statement_timeout` (~8 s), wzorzec z
  `powiazania_autorow/queries.py::_limit_czasu` (`transaction.atomic` +
  `SET LOCAL`).
- Przekroczenie → `OperationalError` → **HTTP 503** z komunikatem
  „Zapytanie trwało za długo — zawęź warunki".
- Paginacja: **LimitOffset** (spójnie z resztą `api_v1`, `PAGE_SIZE=10`),
  twardy cap `limit` (np. 100), żeby jedno żądanie nie ciągnęło całej bazy.

## 4. Kompaktowe projekcje (serializery)

Cel: agent dostaje płaski, gotowy obiekt — zero chodzenia po hyperlinkach.
Relacje jako `string` + URL (do detalu API), gdy potrzeba pełni.

- **Rekord** — **reuse `SzukajSerializer` z Fazy 0** (`api_v1/serializers/szukaj.py`):
  `id` ("`<ct>-<pk>`"), `tytul_oryginalny`, `rok`, `opis_bibliograficzny`,
  `rekord_url` (typowany detal), `absolute_url` (WWW). Dołożyć `doi`.
  Reuse spina Fazę 0 z tym API — jeden format rekordu, którego uczy się agent.
  Wymaga wstrzyknięcia `contenttype_to_viewname` do kontekstu (jak w
  `SzukajViewSet.get_serializer_context`).
- **Autor** — `id`, `slug`, `nazwisko`, `imiona`, `tytul` (skrot),
  `orcid`, `aktualna_jednostka` (nazwa), `autor_url` (detal API),
  `absolute_url` (profil WWW).
- **Autorzy** (through autor↔rekord) — `id`, `zapisany_jako` + `autor_url`,
  `rekord` (tytuł + `rekord_url`), `typ_odpowiedzialnosci` (skrot),
  `kolejnosc`, `jednostka` (nazwa), `dyscyplina` (nazwa).

Wszystkie pola-projekcje muszą mieścić się w allow-liście / być bezpieczne do
wystawienia gate'owanemu (staff) użytkownikowi.

## 5. Schemat walidacji — `RekordLLMSchema` dla wszystkich trzech korzeni

- `RekordLLMSchema` ma `include = SEARCH_ALLOWLIST` (zawiera Rekord/Autor/
  Autorzy), więc da się go zainstancjonować z każdym z trzech modeli jako
  korzeniem; walidacja przechodzi po tej samej allow-liście.
- Wybór `RekordLLMSchema` (a nie `BppQLSchemaOgraniczony`): endpoint jest
  **agent-facing**, nie ma edytora z autocomplete → pickery `<fk>__rel` są
  zbędne, a walidacja wobec **dokładnie tego schematu, którego uczymy agenta**
  (compact.txt) daje idealny round-trip i nie przyjmuje wirtualnych pól, o
  których agent nie wie.
- `fk_options` / `no_value_targets` w `RekordLLMSchema` dotyczą tylko **opisu**
  schematu (eksport/suggestions), nie wykonania `apply_search` — więc są
  nieszkodliwe przy użyciu jako schemat walidacji dla dowolnego korzenia.

## 6. Bezpieczeństwo

- **Read-only** (`ListModelMixin`, tylko `GET`) — brak drogi zapisu.
- **Gate** `user_can_use_query_editor` w `permission_classes` (własny
  `BasePermission` wołający ten predykat) — działa identycznie dla sesji i
  bearer (bo obie ścieżki dają `request.user`).
- **Allow-lista pól** = kontrakt `RekordLLMSchema` (nie goły `BppQLSchema`,
  który dla admina wystawia pełnię pól) → API nie stanie się boczną furtką do
  pól trzymanych tylko w adminie.
- **Throttling** — rozważyć prosty rate-limit (DRF `ScopedRateThrottle`) na tym
  endpoincie; DjangoQL jest droższy niż zwykły list. (Do potwierdzenia; reszta
  `api_v1` dziś nie throttluje.)
- **Multi-uczelnia** — czy wyniki zawężać per bieżąca uczelnia (jak `/szukaj/`
  przez `scope_rekord_do_uczelni` + ukryte statusy)? Web-edytor NIE zawęża (to
  narzędzie redakcyjne). **Otwarte** — patrz §8.

## 7. Zależności — SPEŁNIONE na `dev`

1. `RekordLLMSchema` (+ `SEARCH_ALLOWLIST`) — na `dev` po merge #524. ✅
2. `StrictOAuth2Authentication` — na `dev` po merge #526. ✅
3. `SzukajSerializer` (Faza 0) — na `dev` po merge #515. ✅

Gałąź `feat-api-zapytanie` odcięta od `dev` (`360d911a9`) z kompletem powyżej.

## 8. Otwarte punkty (do rozstrzygnięcia w planie implementacji)

- **Zawężanie multi-uczelnia** dla Rekord (jak `/szukaj/`) — tak/nie. Wpływa na
  spójność z anonimowym FTS. Wstępnie: **nie** (narzędzie redakcyjne, staff), z
  udokumentowaniem różnicy.
- **„Nauczony" schemat dla Autor/Autorzy.** Dziś compact-schemat generujemy
  tylko dla Rekord (`RekordLLMSchema`, korzeń Rekord). Żeby round-trip działał
  dla `zapytanie/autor` i `zapytanie/autorzy`, trzeba wygenerować/udokumentować
  ich schematy (rozszerzyć komendę `opisz_schemat_djangoql_dla_llm` o korzenie
  Autor/Autorzy albo opisać pola w skillu/MCP). **Follow-up**, nie blokuje
  samego wykonywania zapytań.
- **Throttling** — czy i jaki (§6).
- **Endpoint `/schema/`** (opcjonalnie) zwracający compact-opis schematu per
  model — self-describing dla agenta bez zaszywania go w skillu. Poza v1?

## 9. Kryteria akceptacji

- `GET /api/v1/zapytanie/rekord/?q=…` (i `autor`, `autorzy`) zwraca stronicowaną,
  kompaktową listę; niezalogowany/niespełniający gate → 403 (lub 401 dla złego
  bearer).
- Błędne DjangoQL → 400 z `{error[, line, column, mark]}`; puste `q` → pusta
  lista, nie 500.
- Zapytanie po relacji „do wielu" nie dubluje rekordów (`.distinct()`).
- Patologiczne zapytanie ubija się samo → 503 (statement_timeout), nie wisi.
- Zapytanie napisane wg `RekordLLMSchema` (compact.txt) jest poprawne wobec
  endpointu (round-trip) dla Rekord.
- Sesja (cookie zalogowanego staff) i bearer (user spełniający gate) — obie
  ścieżki działają na tym samym widoku.
- Testy pytest (`src/api_v1/tests/test_zapytanie.py`): happy path per model,
  403 dla anona/nie-staff, 400 błędne zapytanie, distinct, timeout→503 (albo
  mock), reuse `SzukajSerializer` dla Rekord. `model_bakery.baker` do fixtur.
- Newsfragment towncrier. Bez zmian schematu bazy → bez odświeżania baseline.

## 10. Poza zakresem (v1, świadomie)

- Zapis/modyfikacja przez API.
- Modele-korzenie inne niż Rekord/Autor/Autorzy.
- Fasety, konfigurowalne sortowania, agregacje w API (DjangoQL i tak wyraża
  warunki; sortowanie ewentualnie później).
- Generacja compact-schematu dla Autor/Autorzy (follow-up, §8).
