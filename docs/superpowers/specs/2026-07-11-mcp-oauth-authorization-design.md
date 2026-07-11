# Autoryzacja OAuth 2.1 dla serwera MCP — delegacja tożsamości BPP

**Data:** 2026-07-11
**Gałąź:** `feat-mcp-oauth` (od `dev`)
**Status:** design (po rewizji review Fable #1 i #2)
**Powiązany spec:** `2026-07-10-api-szukaj-skill-mcp-design.md` (Fazy 0–2 —
API `/szukaj/`, skill `bpp-skills`, serwer `bpp-mcp`). Ten dokument dokłada
**Fazę 3 — autoryzację** i jest wobec tamtego samodzielny (tamten spec żyje
na gałęzi `feat-api-szukaj-skill-mcp`, nie na `dev`).

---

## 1. Cel i motywacja

Serwer MCP `bpp-mcp` (Faza 2) woła dziś API BPP **anonimowo** — widzi tylko
dane publiczne. Chcemy, żeby MCP mógł działać **z uprawnieniami konkretnego,
zalogowanego użytkownika BPP**, tak jakby ten użytkownik siedział przy
przeglądarce.

**Konkretny motywator (sprostowany po weryfikacji kodu):** wyszukiwanie DjangoQL
(„zapytanie": `src/bpp/views/zapytanie.py`) ma dostać w przyszłości endpoint API
i MCP ma umieć je odpalić **jako zalogowany użytkownik**. UWAGA: te widoki są
chronione `WprowadzanieDanychOrSuperuserMixin` (`zapytanie.py:287`,
`raise_exception=True`, `user_can_use_query_editor`) = **superuser LUB staff +
grupa „wprowadzanie danych"**. Realnymi beneficjentami tej funkcji są więc
**konta uprzywilejowane**. Ogólniejszy cel pozostaje: MCP widzi to, co dany
użytkownik (dane nie-publiczne, raporty slotów wg `GR_RAPORTY_WYSWIETLANIE`).

**Konsekwencja dla modelu zagrożeń (§8):** tokeny odblokowujące DjangoQL należą
do staff/superuserów → **krótki TTL, rotacja refresh, revoke, odrzucanie
`is_active=False` — obowiązkowe.**

**Wymagania jakościowe:**
- **Wszystkie metody logowania BPP** bez dodatkowej logiki auth (§4 — ale
  propagacja `next` per-backend wymaga weryfikacji/naprawy).
- Użytkownik **świadomie autoryzuje** serwer MCP (ekran zgody).
- **Read-only egzekwowane serwerowo** (§5.4), w warstwie nieobchodzonej per-view.

## 2. Kontekst — rzeczywistość ustalona z kodu

- **Wszystkie backendy auth zbiegają się w sesji Django** (`base.py`
  ~1171–1342). Fundament designu (§4).
- **DRF nie ma klucza `DEFAULT_AUTHENTICATION_CLASSES`** (`base.py:966`) — leci
  na defaultach DRF (Session + Basic). `DEFAULT_PERMISSION_CLASSES` =
  `DjangoModelPermissionsOrAnonReadOnly`. **Throttling globalnie wyłączony.**
- **`api_v1` MA write i per-view override'y** (kluczowe dla §5.4):
  - `RaportSlotowUczelniaViewSet` (`viewsets/raport_slotow_uczelnia.py:49`) to
    **`ModelViewSet` (write!)** z per-view `authentication_classes=[Basic]` +
    `permission_classes=[IsAuthenticated, IsGrupaRaportyWyswietlanie]`.
  - `recent_author_publications` / `recent_unit_publications` — per-view
    `permission_classes=[AllowAny]`.
  - **Wniosek:** globalna zmiana DRF **nie obowiązuje uniwersalnie** — per-view
    listy zastępują defaulty. Read-only guard MUSI żyć poza DRF-owym per-view.
- **`/api/v1/szukaj/` jest anonimowe** (FTS, Faza 0) — nie jest celem. **Nie
  istnieje na `feat-mcp-oauth`** (żyje na niescalonej `feat-api-szukaj-skill-mcp`)
  → wpływ na testy regresu (§10).
- **`django-oauth-toolkit` NIE zainstalowany** — dokładamy, **pinned**.
- **`bpp-mcp` to osobny pakiet** — §3.
- **`LOGIN_URL` default `/accounts/login/` istnieje** (nie wymaga zmiany), ale
  wariant Microsoft odbija `RedirectView(...)` **bez `query_string=True`**
  (`urls.py` ~472) → gubi `?next=` (§4). Wariant OIDC używa
  `InstitutionalLoginView._redirect_preserving_next` — Microsoft przez OIDC
  zachowuje `next` (dotyczy tylko wariantu „gołego" `microsoft_auth`).
- **`password_policies`** — request bearer na etapie middleware to
  `AnonymousUser` (DRF auth PO middleware, `middleware.py:12`) → pomijany.
- **`SECURE_PROXY_SSL_HEADER`** ustawiony (`base.py:588`, `production.py:123`) →
  metadata budować przez `request.build_absolute_uri()` (poprawny scheme).
- **Wielo-domenowość w jednym procesie** (`SiteResolutionMiddleware`) → issuer
  z `request` (§5.6). `/.well-known/` nie blokowane przez
  `MaliciousRequestBlockingMiddleware`.

## 3. Decyzje architektoniczne i podział własności

Cztery filary (NIE kwestionujemy kierunku):
1. **Pełny OAuth 2.1 z delegacją tożsamości.**
2. **Warstwa OAuth w BPP** — `django-oauth-toolkit` + token-aware DRF.
3. **Końcówka MCP osobno** — `bpp-mcp` (Resource Server).
4. **MVP: read-only**, egzekwowane serwerowo.

| Zakres | Repo | Kto | Kiedy |
|---|---|---|---|
| §5 OAuth AS + token-aware API | **BPP** (`feat-mcp-oauth`) | ta sesja | **najpierw** |
| §6 MCP resource server | **bpp-mcp** (osobny pakiet) | osobna sesja | **potem** |

Producent przed konsumentem. Ta sesja dostarcza tylko §5; §6 to kontrakt.

## 4. Idea nośna — „wszystkie metody logowania" (założenie z checklistą)

`authorize` DOT jest `@login_required` → niezalogowany trafia na `LOGIN_URL` =
strona logowania BPP z wszystkimi backendami. **Zysk nie jest darmowy
bezwarunkowo** — taniec zależy od tego, że `?next=/o/authorize/...` przeżyje
przekierowanie do IdP i powrót:
- **Hasło/lokalny** (`HTMXAwareLoginView`): `next` natywnie. ✅
- **OIDC/Keycloak/Microsoft-przez-OIDC** (`_redirect_preserving_next`,
  mozilla-django-oidc): OK, potwierdzić. ⚠️
- **Microsoft „goły"** (`RedirectView` bez `query_string=True`): **gubi `next`**
  → naprawić `query_string=True` + sprawdzić odtworzenie `next` po callbacku ze
  `state`. ❌→naprawa (zakres §5).
- **ORCID**: propagacja `next` — **niezweryfikowana**. ⚠️

§4 to **założenie z listą weryfikacji**; naprawa „gołego" Microsoftu w zakresie
tej sesji, reszta — testy manualne per-tenant.

## 5. Strona BPP — warstwa OAuth (zakres tej sesji)

### 5.1 Instalacja i modele
- `django-oauth-toolkit` (**wersja przypięta** — §12.1), `oauth2_provider` w
  `INSTALLED_APPS`, migracje nowej apki. Baseline `make baseline-update`
  **RAZ, po scaleniu**.

### 5.2 URL-e AS — cherry-pick, nie całe `urls`
Zamontować **`oauth2_provider.urls.base_urlpatterns`** pod `/o/` (NIE pełne
`urls` — wycina management-views `/o/applications/` CRUD dostępne każdemu
zalogowanemu, obejście DCR). Endpointy: `/o/authorize/`, `/o/token/`,
`/o/introspect/` (jeśli wariant z introspekcją — §5.4c), `/o/revoke_token/`.

`/o/authorized_tokens/` (user widzi/odwołuje swoje zgody) jest w DOT w
**`management_urlpatterns`, NIE w `base_urlpatterns`** — więc **cherry-pick
jawnie** `AuthorizedTokensListView`/`AuthorizedTokenDeleteView` + ostyluj ich
szablony (extendują `oauth2_provider/base.html`, nie frontend BPP), albo pomiń.
`/o/applications/` — jeśli w ogóle, superuser-only.

### 5.3 Konfiguracja `OAUTH2_PROVIDER`
- **PKCE wymagane** (`PKCE_REQUIRED = True`); brak implicit grant.
- **`DEFAULT_SCOPES = ["read"]`** (obowiązkowo — DOT domyślnie `["__all__"]`,
  co dałoby klientowi bez `scope` wszystkie scopes, w tym `introspection`).
- Scope `read` (jedyny wydawany userom). Scope **`introspection` definiować
  TYLKO w wariancie z introspekcją** (§5.4c) i wtedy ograniczyć go do
  confidential clienta (custom `SCOPES_BACKEND_CLASS` / per-app allowlista —
  DOT nie ma per-app allowlisty scopes out-of-the-box). `write` — nie definiujemy.
- Grant user-facing: **`authorization-code` + `refresh_token`** z
  **`ROTATE_REFRESH_TOKEN = True`** i **`REFRESH_TOKEN_EXPIRE_SECONDS`
  ustawionym** (default `None` = łańcuch refresh żyje wiecznie — W-D). Krótki
  `ACCESS_TOKEN_EXPIRE_SECONDS`.

### 5.4 Token-aware API + egzekwowanie read-only (dwie warstwy)

**(a) Własna, „ścisła" klasa auth — `StrictOAuth2Authentication`:**
Standardowe `OAuth2Authentication` przy **nieważnym** bearerze zwraca `None` →
DRF spada na Session/Basic → `AnonymousUser` → `AnonReadOnly` oddaje **200
publiczne** (cicha degradacja, brak 401, brak re-auth — B-1). Dlatego subklasa,
która:
- gdy nagłówek `Authorization: Bearer` **jest obecny, a token nieważny/wygasły/
  zrewokowany** → **`raise AuthenticationFailed`** (żadnego fallthrough na anona),
- odrzuca token, gdy `token.user.is_active is False` (W-D).

Wpisać jawnie pełną listę `DEFAULT_AUTHENTICATION_CLASSES`:
`[StrictOAuth2Authentication, SessionAuthentication, BasicAuthentication]`.
(To **niczego nie zmienia** dla obecnych klientów — DRF i tak domyślnie ma
`[Session, Basic]`, CSRF przy sesji obowiązuje już dziś, `/api/v1/api-auth/`
browsable-login działa dalej, POST-y raport_slotów mają per-view `[Basic]`.)

**(b) Read-only w warstwie nieobchodzonej per-view — middleware `/api/v1/`:**
Ponieważ per-view `authentication_classes`/`permission_classes` **zastępują**
defaulty (B-2: `RaportSlotowUczelniaViewSet` to write z per-view `[Basic]`),
globalna klasa permission NIE wystarczy. Dokładamy **middleware na prefiksie
`/api/v1/`**: jeśli request niesie bearer (`isinstance(request.auth,
get_access_token_model())` — model swappable, D-c) **i metoda nie-SAFE**
(POST/PUT/PATCH/DELETE) → **403**. To zamyka write dla tokenów niezależnie od
per-view. Dla raport_slotów: gdy plan dołoży tam OAuth2 do per-view listy,
middleware i tak zablokuje mutację tokenem.

**(c) Introspekcja — opcjonalna, wymaga client-auth (B1):**
`IntrospectTokenView` DOT wymaga scope `introspection` + uwierzytelnienia
klienta. Warianty:
- **Domyślny (rekomendowany): BEZ introspekcji.** `bpp-mcp` nie robi
  introspekcji; preflight tożsamości robi przez **endpoint `whoami`** (§5.4d).
- **Z introspekcją:** per-instancja ręcznie prowizjonowany **confidential
  `Application`** (grant `client-credentials`, scope `introspection`),
  credentials do konfiguracji `bpp-mcp` jako `BPP_MCP_CLIENT_ID/SECRET`.

**(d) Endpoint `whoami` — konieczny dla poprawnego re-auth MCP (W-C):**
Bez introspekcji `bpp-mcp` nie rozpozna **nieważnego** tokenu przed wywołaniem
narzędzia, a 401 z API złapany w środku tool-calla wraca do klienta jako **błąd
JSON-RPC**, który **NIE triggeruje re-autoryzacji** (klienci MCP re-auth robią
na **HTTP 401 transportu**). Dlatego BPP dostarcza tani endpoint
**`GET /api/v1/whoami/`** autoryzowany bearerem (przez `StrictOAuth2Authentication`
+ `IsAuthenticated`): ważny token → 200 `{username, id, ...}`; brak/nieważny →
**HTTP 401**. `bpp-mcp` woła go jako preflight i mapuje 401 na transportowy 401
przed dispatchem JSON-RPC. **Ten endpoint jest w zakresie tej sesji.**

### 5.5 Ekran zgody
Szablon `authorize.html` (Foundation, `fi-icon`, nie emoji), **literały przez
`{% trans %}`** (LocaleMiddleware aktywne, D-e): „Aplikacja <nazwa> prosi o
ODCZYT danych BPP w Twoim imieniu" + scope. Czytelnie read-only.

### 5.6 Glue do napisania (DOT tego nie shipuje — §12.1)
- **Metadata (RFC 8414):** issuer = **`{host}` (root, BEZ `/o`)**, dokument pod
  `/.well-known/oauth-authorization-server`; endpointy w środku `/o/...`. Budować
  URL-e przez **`request.build_absolute_uri()`** (poprawny scheme z
  `SECURE_PROXY_SSL_HEADER`, host per-request — wielo-domenowość, W2/D-d). DOT ma
  OIDC `openid-configuration`; czysty RFC 8414 zwykle dopisujemy sami.
- **DCR (RFC 7591):** `/o/register/` — **DOT NIE ma tego endpointu (również 3.x)
  → piszemy widok od zera** (JSON RFC 7591 → public `Application`+PKCE,
  `token_endpoint_auth_method:"none"`, `grant_types` z `refresh_token`).
  `csrf_exempt` (globalny `CsrfViewMiddleware`!). **Ręczny rate-limit** (to nie
  DRF view, throttling DRF nie działa). Polityka: **otwarty DCR + twarde
  limity** — allowlista wzorców `redirect_uri` (HTTPS + znane callbacki Claude,
  `http://localhost:*` / `http://127.0.0.1:*`), rate-limit `/o/register/`,
  sprzątanie klientów bez tokenów (celery/cron), **bez auto-approve** dla
  nieznanych wzorców. „initial access token" jest **martwy** dla Claude'a
  (rejestruje się bez poświadczeń) — NIE stosujemy.
- **`LOGIN_URL`** default OK; naprawa Microsoft `query_string=True` (§4).

### 5.7 Interakcje z istniejącymi mechanizmami
- **`axes`** — logowanie w `authorize` tą samą stroną → brute-force dziedziczony.
- **`password_policies`** — bearer-request na middleware to `AnonymousUser` →
  pomijany. User z wygasłym hasłem w `/o/authorize/` zostanie odesłany na zmianę
  hasła — sprawdzić powrót na `authorize` (`next`, D2).
- **Rewokacja przy zmianie hasła / dezaktywacji (W-D):** DOT nie sprawdza
  `is_active` (kryte w §5.4a) i nie rewokuje tokenów przy zmianie hasła — dołożyć
  **signal** (password-change / `is_active=False`) → revoke tokenów usera.
- **`loginas`** (`/login/user/<id>/`) — admin w impersonacji mógłby wydać token
  „w imieniu"; rozważyć blokadę consent przy aktywnym loginas (D4).
- **`auth_server.py`** — nie dotykamy. W deploymentach z nginx `auth_request`:
  `/o/*`, `/.well-known/*`, `/api/v1/*` (bearer, bez cookie) **wyłączyć spod
  bramki** (D6).
- **CORS** — przeglądarkowi klienci (MCP Inspector) potrzebują CORS na
  `/.well-known/*` i `/o/token/`; Claude server-side nie (D5, decyzja świadoma).
- **Caching** — brak cache-middleware; opaque token = +1 DB-hit/request
  (pomijalne). Gdyby nginx kiedyś cache'ował `/api/v1` → `Vary: Authorization`
  (D-f).

## 6. Strona bpp-mcp — kontrakt (zakres późniejszy)

`bpp-mcp` jako Resource Server:
- Serwuje `/.well-known/oauth-protected-resource` (RFC 9728) →
  `authorization_servers: ["{BPP_BASE_URL}"]` (issuer root, NIE `.../o/`).
- Bez tokenu → **401 + `WWW-Authenticate`** (discovery dance).
- **Preflight `whoami`** (§5.4d) na starcie/co token: nieważny → mapuj na
  **transportowy HTTP 401** (żeby klient re-autoryzował), nie na błąd JSON-RPC.
- **Forwarduje** `Authorization: Bearer` na `httpx` do API BPP; write i tak
  blokowany serwerowo (§5.4b).
- Wariant z introspekcją (opcjonalny) wymaga confidential clienta (§5.4c);
  wtedy `bpp-mcp` może sprawdzać `client_id` z introspekcji jako namiastkę
  audience (W3).
- Per-instancyjność: `BPP_BASE_URL` → API + AS; DCR i tokeny per-instancja (§9).

Przy realizacji §6 BPP dostarczy **kontrakt integracyjny** (URL-e, kształt
`whoami`/introspekcji, nagłówki, ewentualne credentials confidential clienta).

## 7. Przepływ end-to-end

1. Claude → `bpp-mcp` bez tokenu → **401** + `WWW-Authenticate` (URL metadata).
2. Claude: `oauth-protected-resource` (MCP) → `oauth-authorization-server`
   (BPP, issuer root) → **DCR** (`/o/register/`) → `client_id`.
3. Claude → przeglądarka → `/o/authorize/` (PKCE, scope `read`).
4. Niezalogowany → **strona logowania BPP** → user loguje się (§4 nt. `next`).
5. **Ekran zgody** → akceptacja.
6. `code` → `/o/token/` (PKCE) → **access token** (+ rotujący refresh).
7. Claude ponawia z `Bearer`; `bpp-mcp` preflightuje `whoami`, forwarduje →
   DRF `request.user` = user; metody nie-SAFE → 403 (§5.4b).
8. Token wygasa mid-session → `whoami` 401 → klient re-autoryzuje po cichu
   (refresh) lub ponawia taniec.

## 8. Bezpieczeństwo

- **Read-only egzekwowane w middleware `/api/v1/`** (§5.4b) — nieobchodzone
  per-view (B-2).
- **Nieważny bearer → 401, nie cicha degradacja do anona** (§5.4a, B-1).
- **Krótki TTL + rotacja refresh + `REFRESH_TOKEN_EXPIRE_SECONDS` + revoke +
  odrzucanie `is_active=False` + revoke-on-password-change** — obowiązkowe, bo
  realni posiadacze tokenów to staff/superuserzy (§1/W-D).
- **PKCE obowiązkowe**, brak implicit, HTTPS-only.
- **Token passthrough — jawne, udokumentowane odstępstwo od MCP MUST (W3):** DOT
  nie wspiera RFC 8707, token opaque bez `aud`. Odstępujemy świadomie
  (`bpp-mcp` i API = ta sama domena zaufania / dostawca IPLWEB). Mitygacje:
  jedyny scope `read`, twardy read-only, krótki TTL, opcjonalna kontrola
  `client_id`. Ryzyko rezydualne: dowolny token AS BPP będzie honorowany przez
  oba. RFC 8707 → §11.
- **DCR = największe wejście:** otwarta rejestracja z twardymi limitami (§5.6).
- **Management views wycięte** (`base_urlpatterns` only, W4).
- **Higiena DOT:** `cleartokens` periodycznie; tokeny w DB plaintext →
  ostrożność z backupami (D3).

## 9. Wielo-instancyjność

Każda instancja = własny AS (własne `/o/`, `Application`/tokeny w swojej bazie).
`bpp-mcp` z `BPP_BASE_URL` odkrywa AS tej instancji i **rejestruje się
per-instancja** (DCR osobno). Issuer budowany z `request` (wielo-domenowość).
Keycloak (gdzie wdrożony) pozostaje **backendem logowania** na `authorize`, nie
zastępuje AS BPP.

## 10. Testy

**BPP (pytest, ta sesja):**
- Ważny `Bearer` → `request.user` ustawiony; dane per-user.
- **`whoami`:** ważny token → 200; brak/nieważny/zrewokowany → **401** (nie 200
  anonimowe — B-1).
- **Read-only:** POST/PUT/PATCH/DELETE z bearerem na `/api/v1/*` → **403**
  (w tym na write-owym `raport_slotow` po dołożeniu tam OAuth2 — B-2).
- Anonimowy request → dalej `AnonReadOnly` (regres na **dowolnym anonimowym
  endpoincie `api_v1`**; `/szukaj/` nie na tej gałęzi → do checklisty scalenia).
- `code`→token z PKCE; **brak PKCE → odrzucone**.
- Ekran zgody renderuje i zapisuje `Grant`; scope na ekranie = tylko `read`
  (nie `introspection` — W-B).
- **Revoke** → kolejny request/`whoami` → 401.
- **DCR:** dozwolony `redirect_uri` → 201 `client_id`; nie-HTTPS/niedozwolony →
  odrzucone; `/o/register/` bez CSRF działa.
- **Metadata** zwraca issuer=host (per `request`) + endpointy.
- **Rotacja refresh:** użycie refresh → nowy refresh, stary nieważny.
- **`is_active=False`** → token odrzucony; **password-change** → tokeny usera
  zrewokowane.

**bpp-mcp (kontrakt, później):** 401 bez tokenu; metadata; `whoami` preflight;
bearer forward; mock (respx/httpx MockTransport).

**Smoke (opcjonalny):** pełny taniec OAuth wobec żywej instancji, per-backend (§4).

## 11. Poza zakresem (Faza 3)

- Zapis/import przez API (osobna, późniejsza faza).
- **RFC 8707 / audience binding** (DOT nie wspiera — świadome odstępstwo, §8/W3);
  token-exchange (RFC 8693).
- OIDC userinfo dla MCP (potrzebny tylko access token).
- Scope-gating narzędzi ponad `read` (razem z write).
- Końcówka MCP i narzędzia (`bpp-mcp` §6 — osobny pakiet, osobna sesja).

## 12. Otwarte kwestie do rozstrzygnięcia w planie

1. **Wersja `django-oauth-toolkit`** — przypiąć i zweryfikować **przed planem**:
   PKCE, `ROTATE_REFRESH_TOKEN`, `OAuth2Authentication`, brak DCR (piszemy sami),
   brak RFC 8414 (dopisujemy). DCR i RFC 8414 to **kod własny**, nie config.
2. Introspekcja vs `whoami` (§5.4c/d) — rekomendacja: `whoami`, bez introspekcji.
3. Dokładny kształt middleware read-only `/api/v1/` (§5.4b).
4. Allowlista `redirect_uri` Claude'a (§5.6).
5. Naprawa `next` Microsoft + weryfikacja ORCID (§4).
6. Mechanizm revoke-on-password-change (signal, §5.7/W-D).

## 13. Kryteria akceptacji Fazy 3 (strona BPP)

- `django-oauth-toolkit` (pinned) + migracje + baseline (przy scalaniu).
- Zamontowane **tylko** `base_urlpatterns` (+ cherry-pick `authorized_tokens`,
  własne well-known/DCR); management-CRUD niewystawione (lub superuser-only).
- `/o/authorize/`, `/o/token/`, `/o/revoke_token/`, `/o/register/` (własny),
  `/.well-known/oauth-authorization-server` (własny, issuer=host) działają;
  niezalogowany na `authorize` widzi login BPP; `next` przeżywa hasło+Microsoft.
- API: **ważny bearer → `request.user`**; **nieważny bearer → 401** (nie
  degradacja); **metody nie-SAFE z bearerem → 403** (także per-view write);
  `whoami` działa; anonimowe endpointy bez regresu.
- PKCE wymuszone; `DEFAULT_SCOPES=["read"]`; ekran zgody read-only, po polsku.
- Rotacja refresh + `REFRESH_TOKEN_EXPIRE_SECONDS` + revoke + `is_active` +
  revoke-on-password-change.
- Testy pytest zielone (read-only, PKCE, revoke, DCR-reject, whoami, is_active).
- `bpp-mcp` dostaje udokumentowany kontrakt integracyjny (§6).
