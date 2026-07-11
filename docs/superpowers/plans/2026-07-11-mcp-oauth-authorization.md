# OAuth 2.1 dla serwera MCP — Implementation Plan (strona BPP)

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dodać do BPP warstwę OAuth 2.1 Authorization Server
(`django-oauth-toolkit`) + token-aware, read-only DRF, tak by serwer MCP
`bpp-mcp` mógł działać z uprawnieniami zalogowanego użytkownika BPP.

**Architecture:** BPP zostaje Authorization Serverem: `/o/authorize|token|
revoke` z DOT (`base_urlpatterns`), własny endpoint DCR (`/o/register/`) i własny
RFC 8414 metadata (`/.well-known/oauth-authorization-server`), bo DOT tego nie
shipuje. API `/api/v1/` przyjmuje `Bearer` przez `StrictOAuth2Authentication`
(rzuca 401 na nieważny token, nie degraduje do anona) i jest twardo read-only
przez middleware na prefiksie (nieobchodzone per-view). Endpoint `whoami`
pozwala `bpp-mcp` zrobić preflight tożsamości mapowany na HTTP 401.

**Tech Stack:** Django, DRF, `django-oauth-toolkit` (pinned), pytest +
model_bakery, testcontainers (PG+Redis).

**Spec:** `docs/superpowers/specs/2026-07-11-mcp-oauth-authorization-design.md`
(po review Fable #1 i #2). Odwołania „(§X)" wskazują sekcje speca.

## Global Constraints

- Max line length **88** (ruff). `uv run` przed KAŻDĄ komendą Python. Pytest
  only (no unittest.TestCase), `model_bakery.baker.make`, `@pytest.mark.django_db`.
- **NIE modyfikować istniejących migracji.** Nowe migracje `oauth2_provider` OK.
- **Baseline odświeżyć RAZ, przy scalaniu** (`make baseline-update`), NIE w
  trakcie ani w równoległych branchach.
- Django template comments per-line `{# … #}`. Admin=emoji, frontend=fi-icon.
- Read-only MVP: **żadnego scope `write`**, żadnych narzędzi zapisu.
- Issuer OAuth = **root hosta** (`https://host`, BEZ `/o`); URL-e budować przez
  `request.build_absolute_uri()` (nie sklejać ręcznie — `SECURE_PROXY_SSL_HEADER`).
- Wszystkie literały UI przez `{% trans %}` / `gettext` (LocaleMiddleware aktywne).

---

## File Structure

- `pyproject.toml` — dep `django-oauth-toolkit` (pinned).
- `src/django_bpp/settings/base.py` — `INSTALLED_APPS`, `OAUTH2_PROVIDER`,
  `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]`, `MIDDLEWARE`.
- `src/oauth_mcp/` — **nowa apka** (izolacja warstwy OAuth-MCP):
  - `authentication.py` — `StrictOAuth2Authentication`.
  - `middleware.py` — `ApiReadOnlyForBearerMiddleware`.
  - `views_metadata.py` — RFC 8414 metadata view.
  - `views_dcr.py` — RFC 7591 Dynamic Client Registration view.
  - `views_whoami.py` — `whoami` DRF view.
  - `signals.py` — revoke-on-password-change / is_active.
  - `urls.py` — well-known + `/o/register/` + montaż `base_urlpatterns`.
  - `apps.py`, `__init__.py`.
  - `templates/oauth2_provider/authorize.html` — ekran zgody (override DOT).
  - `tests/` — per-komponent.
- `src/django_bpp/urls.py` — include `oauth_mcp.urls`; fix Microsoft `next`.

> Dlaczego osobna apka `oauth_mcp`, nie `api_v1`: warstwa AS + auth + middleware
> to jedna odpowiedzialność (autoryzacja MCP), zmienia się razem, i trzyma
> `api_v1` czystym. Zgodne z „files that change together live together".

---

### Task 1: Instalacja i pin django-oauth-toolkit + apka `oauth_mcp`

**Files:**
- Modify: `pyproject.toml`
- Create: `src/oauth_mcp/__init__.py`, `src/oauth_mcp/apps.py`,
  `src/oauth_mcp/signals.py` (stub — wypełnia Task 9),
  `src/oauth_mcp/tests/__init__.py`
- Modify: `src/django_bpp/settings/base.py` (INSTALLED_APPS)
- Test: `src/oauth_mcp/tests/test_install.py`

**Interfaces:**
- Produces: apka `oauth_mcp` w INSTALLED_APPS; `oauth2_provider` migrowalny.

- [ ] **Step 1: Dodaj zależność (pinned)**

```bash
uv add "django-oauth-toolkit>=3.0,<4.0"
```

Zapisz w `pyproject.toml` dokładną wybraną wersję (np. `==3.0.1`) — patrz Step 6
weryfikacja.

- [ ] **Step 2: Utwórz apkę**

`src/oauth_mcp/__init__.py`: pusty.
`src/oauth_mcp/apps.py`:

```python
from django.apps import AppConfig


class OauthMcpConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "oauth_mcp"

    def ready(self):
        from oauth_mcp import signals  # noqa: F401  (rejestruje receivery)
```

**Utwórz też STUB `src/oauth_mcp/signals.py`** (inaczej `ready()` wywali
ImportError już przy Step 5 — B1):

```python
"""Receivery rewokacji tokenów — implementacja w Task 9."""
```

`src/oauth_mcp/tests/__init__.py`: pusty (unikamy kolizji nazw modułów pytest).

- [ ] **Step 3: INSTALLED_APPS (kolejność ma znaczenie)**

W `src/django_bpp/settings/base.py` dodaj (po `rest_framework`) **w tej
kolejności — `oauth_mcp` PRZED `oauth2_provider`**, bo app_directories loader
bierze szablon z pierwszej apki i tak `oauth_mcp` nadpisze `authorize.html`
(Task 8, W5):
`"oauth_mcp",` a następnie `"oauth2_provider",`.

- [ ] **Step 4: Test — apki załadowane, modele DOT migrowalne**

`src/oauth_mcp/tests/test_install.py`:

```python
import pytest
from django.apps import apps


def test_apki_zaladowane():
    assert apps.is_installed("oauth2_provider")
    assert apps.is_installed("oauth_mcp")


@pytest.mark.django_db
def test_modele_dot_dostepne():
    from oauth2_provider.models import get_access_token_model

    AccessToken = get_access_token_model()
    assert AccessToken.objects.count() == 0
```

- [ ] **Step 5: Uruchom migracje + test**

```bash
uv run python src/manage.py makemigrations --check --dry-run
uv run pytest src/oauth_mcp/tests/test_install.py -v
```

Expected: PASS (migracje `oauth2_provider` istnieją w pakiecie; nasz kod nie
tworzy modeli).

- [ ] **Step 6: Weryfikacja założeń wersji (BLOKUJE resztę planu)**

```bash
uv run python -c "import oauth2_provider, oauth2_provider.urls as u; \
print(oauth2_provider.VERSION); \
print('base_urlpatterns' in dir(u)); \
from oauth2_provider.contrib.rest_framework import OAuth2Authentication; \
print('OAuth2Authentication OK'); \
from oauth2_provider.models import get_access_token_model; print('token model OK')"
```

Expected: wersja wypisana, `base_urlpatterns` = True, importy OK. Jeśli
`base_urlpatterns` nie istnieje w tej wersji — zanotuj rzeczywistą nazwę i
dostosuj Task 2. **Potwierdź w komentarzu commita, że DOT NIE ma `/o/register/`
(DCR) ani czystego RFC 8414 — dlatego Task 6 i 7 piszą je od zera.**

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock src/oauth_mcp src/django_bpp/settings/base.py
git commit -m "feat(oauth_mcp): zainstaluj django-oauth-toolkit + apka oauth_mcp"
```

---

### Task 2: Montaż AS (`/o/`) + konfiguracja OAUTH2_PROVIDER

**Files:**
- Create: `src/oauth_mcp/urls.py`
- Modify: `src/django_bpp/settings/base.py` (OAUTH2_PROVIDER)
- Modify: `src/django_bpp/urls.py` (include)
- Test: `src/oauth_mcp/tests/test_authorize.py`

**Interfaces:**
- Produces: `/o/authorize/`, `/o/token/`, `/o/revoke_token/` (z DOT
  `base_urlpatterns`); ustawienia PKCE/scopes/refresh.
- Consumes: apka z Task 1.

- [ ] **Step 1: OAUTH2_PROVIDER w base.py**

```python
OAUTH2_PROVIDER = {
    "PKCE_REQUIRED": True,
    "DEFAULT_SCOPES": ["read"],
    "SCOPES": {"read": "Odczyt danych BPP w Twoim imieniu"},
    "ROTATE_REFRESH_TOKEN": True,
    "ACCESS_TOKEN_EXPIRE_SECONDS": 60 * 30,          # 30 min
    "REFRESH_TOKEN_EXPIRE_SECONDS": 60 * 60 * 24 * 7,  # 7 dni (NIE None!)
}
```

> NIE dodawaj `ALLOWED_GRANT_TYPES` — taki klucz nie istnieje w DOT
> (`OAUTH2_PROVIDER`) i zostałby po cichu zignorowany (W4). Granty kontroluje
> DCR (tworzy tylko public+authorization-code) i atrybut `Application`.

- [ ] **Step 2: urls.py apki — montaż base_urlpatterns**

`src/oauth_mcp/urls.py`:

```python
from django.urls import include, path
from oauth2_provider import urls as oauth2_urls

# BEZ `app_name` na tym module! Deklaracja `app_name="oauth_mcp"` zagnieżdżałaby
# namespace DOT (`oauth_mcp:oauth2_provider:authorize`) i psuła
# `{% url 'oauth2_provider:authorize' %}` w szablonie zgody → NoReverseMatch
# (B2). Zostawiamy `oauth2_provider:*` na top-levelu, jak w dokumentacji DOT.

# UWAGA: montujemy TYLKO base_urlpatterns (authorize/token/introspect/revoke),
# NIE management-views (/o/applications/ CRUD dostępne każdemu zalogowanemu).
urlpatterns = [
    path("o/", include((oauth2_urls.base_urlpatterns, "oauth2_provider"))),
]
```

- [ ] **Step 3: include w głównym urls.py**

W `src/django_bpp/urls.py` dodaj do `urlpatterns`:
`path("", include("oauth_mcp.urls")),`

- [ ] **Step 4: Test — authorize wymaga logowania, token wymaga PKCE**

`src/oauth_mcp/tests/test_authorize.py`:

```python
import pytest
from django.urls import reverse
from model_bakery import baker
from oauth2_provider.models import get_application_model


@pytest.mark.django_db
def test_authorize_niezalogowany_redirect_na_login(client):
    resp = client.get("/o/authorize/", {"response_type": "code"})
    assert resp.status_code == 302
    assert "/accounts/login/" in resp["Location"]


@pytest.mark.django_db
def test_pkce_wymagane(client, django_user_model):
    Application = get_application_model()
    user = baker.make(django_user_model)
    app = Application.objects.create(
        user=user,
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris="https://claude.ai/callback",
        name="test",
    )
    client.force_login(user)
    # authorize BEZ code_challenge → odrzucone (PKCE_REQUIRED)
    resp = client.get(
        "/o/authorize/",
        {
            "response_type": "code",
            "client_id": app.client_id,
            "redirect_uri": "https://claude.ai/callback",
        },
    )
    # DOT przy PKCE_REQUIRED i braku code_challenge zwraca redirectowalny błąd:
    # 302 z ?error=... na redirect_uri (nie 400) — D3.
    assert resp.status_code == 302
    assert "error=" in resp["Location"]
```

- [ ] **Step 5: Uruchom**

```bash
uv run pytest src/oauth_mcp/tests/test_authorize.py -v
```

Expected: PASS („bez PKCE nie przejdzie" = redirect z `error=`).

- [ ] **Step 6: Commit**

```bash
git add src/oauth_mcp/urls.py src/django_bpp/urls.py src/django_bpp/settings/base.py src/oauth_mcp/tests/test_authorize.py
git commit -m "feat(oauth_mcp): montaż AS /o/ (base_urlpatterns) + PKCE/scopes/refresh"
```

---

### Task 3: `StrictOAuth2Authentication` (401 na nieważny bearer, is_active)

**Files:**
- Create: `src/oauth_mcp/authentication.py`
- Modify: `src/django_bpp/settings/base.py` (DEFAULT_AUTHENTICATION_CLASSES)
- Test: `src/oauth_mcp/tests/test_authentication.py`

**Interfaces:**
- Produces: `oauth_mcp.authentication.StrictOAuth2Authentication`.
- Consumes: `/o/` z Task 2 (do wystawienia tokenów w testach).

- [ ] **Step 1: Implementacja**

`src/oauth_mcp/authentication.py`:

```python
from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from rest_framework.exceptions import AuthenticationFailed


class StrictOAuth2Authentication(OAuth2Authentication):
    """OAuth2 auth, która NIE degraduje po cichu do anonima.

    Standardowe ``OAuth2Authentication`` przy nieważnym bearerze zwraca
    ``None`` → DRF spada na Session/Basic → ``AnonymousUser`` → endpoint
    ``AnonReadOnly`` oddaje 200 publiczne. Chcemy twardego 401, gdy klient
    JAWNIE przysłał ``Authorization: Bearer`` (spec §5.4a / B-1). Dodatkowo
    odrzucamy nieaktywnych użytkowników (spec §5.7 / W-D).
    """

    def authenticate(self, request):
        result = super().authenticate(request)
        header = request.META.get("HTTP_AUTHORIZATION", "")
        bearer_obecny = header.lower().startswith("bearer ")
        if result is None:
            if bearer_obecny:
                raise AuthenticationFailed("Nieprawidłowy lub wygasły token.")
            return None
        user, token = result
        if not user or not user.is_active:
            raise AuthenticationFailed("Konto nieaktywne.")
        return user, token
```

- [ ] **Step 2: Wpisz pełną listę auth classes w base.py**

W `REST_FRAMEWORK` dodaj klucz (dziś go NIE ma — wypisz jawnie, OAuth2
pierwsze):

```python
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "oauth_mcp.authentication.StrictOAuth2Authentication",
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
```

> To niczego nie zmienia dla obecnych klientów (DRF domyślnie ma
> `[Session, Basic]`; CSRF przy sesji obowiązuje już dziś).

- [ ] **Step 3: Fixture wystawiający token (reużywalny)**

`src/oauth_mcp/tests/conftest.py`:

```python
import pytest
from model_bakery import baker
from oauth2_provider.models import get_access_token_model, get_application_model


@pytest.fixture
def access_token(db, django_user_model):
    def _make(scope="read", is_active=True):
        AccessToken = get_access_token_model()
        Application = get_application_model()
        user = baker.make(django_user_model, is_active=is_active)
        app = Application.objects.create(
            user=user,
            client_type=Application.CLIENT_PUBLIC,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris="https://claude.ai/callback",
            name="test-mcp",
        )
        from django.utils import timezone
        from datetime import timedelta

        tok = AccessToken.objects.create(
            user=user,
            application=app,
            token="tok-" + str(user.pk),
            expires=timezone.now() + timedelta(hours=1),
            scope=scope,
        )
        return user, tok

    return _make
```

- [ ] **Step 4: Testy**

`src/oauth_mcp/tests/test_authentication.py`:

```python
import pytest


@pytest.mark.django_db
def test_wazny_token_ustawia_usera(access_token, client):
    user, tok = access_token()
    resp = client.get(
        "/api/v1/whoami/", HTTP_AUTHORIZATION=f"Bearer {tok.token}"
    )
    # whoami powstaje w Task 5; tu sprawdzamy tylko że NIE ma 500/anon-degrade.
    assert resp.status_code in (200, 404)


@pytest.mark.django_db
def test_niewazny_bearer_daje_401_nie_anon(access_token, client):
    # dowolny anonimowy read-only endpoint api_v1 z GŁUPIM bearerem → 401
    resp = client.get(
        "/api/v1/wydawnictwo_ciagle/",
        HTTP_AUTHORIZATION="Bearer nieistniejacy-token",
    )
    assert resp.status_code == 401


@pytest.mark.django_db
def test_brak_bearera_dalej_anonimowo(client):
    resp = client.get("/api/v1/wydawnictwo_ciagle/")
    assert resp.status_code == 200  # AnonReadOnly bez zmian
```

- [ ] **Step 5: Uruchom**

```bash
uv run pytest src/oauth_mcp/tests/test_authentication.py -v
```

Expected: `test_niewazny_bearer_daje_401_nie_anon` i
`test_brak_bearera_dalej_anonimowo` PASS. (`test_wazny_token...` przejdzie w
pełni po Task 5 — dopuszczamy 404 tymczasowo.)

- [ ] **Step 6: Commit**

```bash
git add src/oauth_mcp/authentication.py src/django_bpp/settings/base.py src/oauth_mcp/tests/
git commit -m "feat(oauth_mcp): StrictOAuth2Authentication — 401 na nieważny bearer + is_active"
```

---

### Task 4: Middleware read-only na `/api/v1/`

**Files:**
- Create: `src/oauth_mcp/middleware.py`
- Modify: `src/django_bpp/settings/base.py` (MIDDLEWARE)
- Test: `src/oauth_mcp/tests/test_readonly_middleware.py`

**Interfaces:**
- Produces: `oauth_mcp.middleware.ApiReadOnlyForBearerMiddleware`.
- Consumes: `StrictOAuth2Authentication` (Task 3), fixture `access_token`.

> Dlaczego middleware, nie permission class: per-view `permission_classes`
> zastępują globalne (spec §5.4b / B-2 — `RaportSlotowUczelniaViewSet` to write
> z per-view auth). Middleware na prefiksie jest nieobchodzone.

- [ ] **Step 1: Implementacja**

`src/oauth_mcp/middleware.py`:

```python
from django.http import JsonResponse

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


class ApiReadOnlyForBearerMiddleware:
    """Blokuje mutacje `/api/v1/` wykonane tokenem OAuth (MVP read-only).

    Auth DRF biegnie w widoku (po middleware), więc tu wykrywamy bearer po
    nagłówku i sami weryfikujemy token, zamiast polegać na `request.auth`
    (jeszcze nieustawionym). To warstwa nieobchodzona przez per-view
    `permission_classes` (spec §5.4b / B-2).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.path.startswith("/api/v1/")
            and request.method not in SAFE_METHODS
            and self._ma_wazny_bearer(request)
        ):
            return JsonResponse(
                {"detail": "Zapis przez token MCP jest wyłączony (read-only)."},
                status=403,
            )
        return self.get_response(request)

    @staticmethod
    def _ma_wazny_bearer(request):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header.lower().startswith("bearer "):
            return False
        raw = header.split(" ", 1)[1].strip()
        from oauth2_provider.models import get_access_token_model

        AccessToken = get_access_token_model()
        tok = AccessToken.objects.filter(token=raw).first()
        return bool(tok and tok.is_valid())
```

- [ ] **Step 2: Dodaj do MIDDLEWARE**

W `src/django_bpp/settings/base.py` wstaw
`"oauth_mcp.middleware.ApiReadOnlyForBearerMiddleware",` **przed**
`"axes.middleware.AxesMiddleware"` (base.py ~331–333 dokumentuje invariant, że
AxesMiddleware musi zostać OSTATNIE — nie łam go, D1).

- [ ] **Step 3: Testy**

`src/oauth_mcp/tests/test_readonly_middleware.py`:

```python
import pytest


@pytest.mark.django_db
def test_post_z_bearerem_blokowany_403(access_token, client):
    user, tok = access_token()
    resp = client.post(
        "/api/v1/raport_slotow_uczelnia/",
        data={},
        HTTP_AUTHORIZATION=f"Bearer {tok.token}",
        content_type="application/json",
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_get_z_bearerem_przechodzi_przez_middleware(access_token, client):
    user, tok = access_token()
    resp = client.get(
        "/api/v1/wydawnictwo_ciagle/",
        HTTP_AUTHORIZATION=f"Bearer {tok.token}",
    )
    # middleware nie blokuje GET; sam endpoint może dać 200
    assert resp.status_code != 403


@pytest.mark.django_db
def test_post_bez_bearera_nietkniety(client):
    # bez tokenu middleware nie ingeruje; endpoint (per-view [Basic] +
    # IsAuthenticated) sam odrzuca anonima → 401 z DRF, NIE 403 z middleware.
    resp = client.post(
        "/api/v1/raport_slotow_uczelnia/", data={}, content_type="application/json"
    )
    assert resp.status_code == 401
```

- [ ] **Step 4: Uruchom**

```bash
uv run pytest src/oauth_mcp/tests/test_readonly_middleware.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/oauth_mcp/middleware.py src/django_bpp/settings/base.py src/oauth_mcp/tests/test_readonly_middleware.py
git commit -m "feat(oauth_mcp): middleware read-only /api/v1/ dla tokenów MCP"
```

---

### Task 5: Endpoint `GET /api/v1/whoami/`

**Files:**
- Create: `src/oauth_mcp/views_whoami.py`
- Modify: `src/api_v1/urls.py` (rejestracja ścieżki)
- Test: `src/oauth_mcp/tests/test_whoami.py`

**Interfaces:**
- Produces: `GET /api/v1/whoami/` → 200 `{id, username, is_staff, is_superuser}`
  dla ważnego tokenu; 401 dla braku/nieważnego (dzięki Task 3).
- Consumes: `StrictOAuth2Authentication` (Task 3).

- [ ] **Step 1: Widok**

`src/oauth_mcp/views_whoami.py`:

```python
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from oauth_mcp.authentication import StrictOAuth2Authentication


class WhoAmIView(APIView):
    """Preflight tożsamości dla bpp-mcp (spec §5.4d).

    Ważny token → 200 z tożsamością; brak/nieważny → 401 (transportowy,
    mapowalny przez klienta MCP na re-auth). Świadomie NIE dopuszczamy
    anonimowego 200.
    """

    authentication_classes = [StrictOAuth2Authentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        return Response(
            {
                "id": u.pk,
                "username": u.get_username(),
                "is_staff": u.is_staff,
                "is_superuser": u.is_superuser,
            }
        )
```

- [ ] **Step 2: Rejestracja ścieżki**

`src/api_v1/urls.py` importuje dziś tylko `re_path as url` — **dopisz import
`path`**. Realny kształt pliku to `urlpatterns = [url(r"^", include(router.urls))]`,
więc dołóż `path` PRZED wpięciem routera (kolejność ma znaczenie — `whoami/`
musi złapać przed catch-all routera):

```python
from django.urls import path                     # DOPISZ (jest tylko re_path)
from oauth_mcp.views_whoami import WhoAmIView
# ...
urlpatterns = [
    path("whoami/", WhoAmIView.as_view(), name="whoami"),
    url(r"^", include(router.urls)),             # istniejący wpis routera
]
```

- [ ] **Step 3: Testy**

`src/oauth_mcp/tests/test_whoami.py`:

```python
import pytest


@pytest.mark.django_db
def test_whoami_wazny_token(access_token, client):
    user, tok = access_token()
    resp = client.get("/api/v1/whoami/", HTTP_AUTHORIZATION=f"Bearer {tok.token}")
    assert resp.status_code == 200
    assert resp.json()["username"] == user.get_username()


@pytest.mark.django_db
def test_whoami_bez_tokenu_401(client):
    resp = client.get("/api/v1/whoami/")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_whoami_niewazny_token_401(client):
    resp = client.get("/api/v1/whoami/", HTTP_AUTHORIZATION="Bearer zly")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_whoami_nieaktywny_user_401(access_token, client):
    user, tok = access_token(is_active=False)
    resp = client.get("/api/v1/whoami/", HTTP_AUTHORIZATION=f"Bearer {tok.token}")
    assert resp.status_code == 401
```

- [ ] **Step 4: Uruchom**

```bash
uv run pytest src/oauth_mcp/tests/test_whoami.py -v
```

Expected: wszystkie PASS. (Domyka też `test_wazny_token_ustawia_usera` z Task 3.)

- [ ] **Step 5: Commit**

```bash
git add src/oauth_mcp/views_whoami.py src/api_v1/urls.py src/oauth_mcp/tests/test_whoami.py
git commit -m "feat(oauth_mcp): endpoint /api/v1/whoami/ (preflight tożsamości MCP)"
```

---

### Task 6: RFC 8414 metadata (`/.well-known/oauth-authorization-server`)

**Files:**
- Create: `src/oauth_mcp/views_metadata.py`
- Modify: `src/oauth_mcp/urls.py`
- Test: `src/oauth_mcp/tests/test_metadata.py`

**Interfaces:**
- Produces: `GET /.well-known/oauth-authorization-server` → JSON z issuer=host
  i endpointami; dołożone do `urlpatterns`.

- [ ] **Step 1: Widok**

`src/oauth_mcp/views_metadata.py`:

```python
from django.http import JsonResponse


def oauth_authorization_server_metadata(request):
    """RFC 8414 — DOT nie shipuje czystego wariantu, piszemy sami (spec §5.6).

    Issuer = ROOT hosta (bez /o); URL-e przez build_absolute_uri (poprawny
    scheme z SECURE_PROXY_SSL_HEADER, host per-request — wielo-domenowość).
    """
    issuer = request.build_absolute_uri("/").rstrip("/")
    return JsonResponse(
        {
            "issuer": issuer,
            "authorization_endpoint": request.build_absolute_uri("/o/authorize/"),
            "token_endpoint": request.build_absolute_uri("/o/token/"),
            "revocation_endpoint": request.build_absolute_uri("/o/revoke_token/"),
            "registration_endpoint": request.build_absolute_uri("/o/register/"),
            "scopes_supported": ["read"],
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
        }
    )
```

- [ ] **Step 2: URL**

W `src/oauth_mcp/urls.py` dodaj do `urlpatterns`:

```python
from oauth_mcp.views_metadata import oauth_authorization_server_metadata
# ...
    path(
        ".well-known/oauth-authorization-server",
        oauth_authorization_server_metadata,
        name="oauth-as-metadata",
    ),
```

- [ ] **Step 3: Testy**

`src/oauth_mcp/tests/test_metadata.py`:

```python
import pytest


@pytest.mark.django_db
def test_metadata_ksztalt(client):
    resp = client.get("/.well-known/oauth-authorization-server")
    assert resp.status_code == 200
    data = resp.json()
    assert data["issuer"].startswith("http")
    assert not data["issuer"].endswith("/o")  # issuer = ROOT
    assert data["authorization_endpoint"].endswith("/o/authorize/")
    assert data["registration_endpoint"].endswith("/o/register/")
    assert data["code_challenge_methods_supported"] == ["S256"]
    assert data["scopes_supported"] == ["read"]


@pytest.mark.django_db
def test_metadata_issuer_z_hosta(client):
    # Host MUSI być w ALLOWED_HOSTS (testy dziedziczą zamkniętą listę) — inaczej
    # DisallowedHost, nie 200 (B3). `test.unexistenttld` jest w ALLOWED_HOSTS.
    resp = client.get(
        "/.well-known/oauth-authorization-server", HTTP_HOST="test.unexistenttld"
    )
    assert "test.unexistenttld" in resp.json()["issuer"]
```

- [ ] **Step 4: Uruchom**

```bash
uv run pytest src/oauth_mcp/tests/test_metadata.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/oauth_mcp/views_metadata.py src/oauth_mcp/urls.py src/oauth_mcp/tests/test_metadata.py
git commit -m "feat(oauth_mcp): RFC 8414 metadata /.well-known/oauth-authorization-server"
```

---

### Task 7: DCR (`POST /o/register/`, RFC 7591, własny)

**Files:**
- Create: `src/oauth_mcp/views_dcr.py`
- Modify: `src/oauth_mcp/urls.py`
- Test: `src/oauth_mcp/tests/test_dcr.py`

**Interfaces:**
- Produces: `POST /o/register/` → 201 `{client_id, ...}` dla dozwolonego
  `redirect_uri`; 400 dla niedozwolonego/nie-HTTPS. `csrf_exempt`, ręczny
  rate-limit.

> DOT NIE ma DCR (spec §5.6/§12.1) — piszemy widok od zera.

- [ ] **Step 1: Widok**

`src/oauth_mcp/views_dcr.py`:

```python
import json
import re

from django.utils.decorators import method_decorator
from django.views import View
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from oauth2_provider.models import get_application_model

# Allowlista wzorców redirect_uri (spec §5.6): callbacki Claude + lokalne.
_ALLOWED_REDIRECT_PATTERNS = [
    re.compile(r"^https://claude\.ai/[^\s]*$"),
    re.compile(r"^https://[a-z0-9.-]+\.claude\.ai/[^\s]*$"),
    re.compile(r"^https://claude\.com/[^\s]*$"),
    re.compile(r"^http://localhost(:\d+)?/[^\s]*$"),
    re.compile(r"^http://127\.0\.0\.1(:\d+)?/[^\s]*$"),
]


def _dozwolony(uri: str) -> bool:
    return any(p.match(uri) for p in _ALLOWED_REDIRECT_PATTERNS)


@method_decorator(csrf_exempt, name="dispatch")
class DynamicClientRegistrationView(View):
    """RFC 7591 — rejestracja publicznego klienta MCP (public + PKCE).

    Otwarta rejestracja z twardymi limitami (spec §5.6/§8/W7): allowlista
    redirect_uri, bez auto-approve dla nieznanych wzorców. Rate-limit: patrz
    Step 2 (ręczny — to nie DRF view).
    """

    def post(self, request):
        try:
            payload = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "invalid_client_metadata"}, status=400)

        redirect_uris = payload.get("redirect_uris") or []
        if not redirect_uris or not all(_dozwolony(u) for u in redirect_uris):
            return JsonResponse(
                {"error": "invalid_redirect_uri"}, status=400
            )

        Application = get_application_model()
        app = Application.objects.create(
            name=(payload.get("client_name") or "mcp-client")[:255],
            client_type=Application.CLIENT_PUBLIC,
            authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
            redirect_uris=" ".join(redirect_uris),
        )
        return JsonResponse(
            {
                "client_id": app.client_id,
                "redirect_uris": redirect_uris,
                "token_endpoint_auth_method": "none",
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
            },
            status=201,
        )
```

- [ ] **Step 2: Rate-limit (ręczny, prosty licznik w cache)**

Dodaj na początku `post()` (przed parsowaniem):

```python
        from django.core.cache import cache

        ip = request.META.get("REMOTE_ADDR", "?")
        key = f"dcr-rate:{ip}"
        licznik = cache.get(key, 0)
        if licznik >= 20:  # 20 rejestracji / okno
            return JsonResponse({"error": "rate_limited"}, status=429)
        cache.set(key, licznik + 1, timeout=3600)  # okno 1h
```

> D5: za nginx-em `REMOTE_ADDR` to IP proxy → limit staje się globalny per
> instancja (20/h dla wszystkich). Zaakceptować (i tak bariera na zalew), albo
> czytać `X-Forwarded-For` zza zaufanego proxy. Świadoma decyzja — dla MVP
> globalny limit jest OK.

- [ ] **Step 3: URL**

W `src/oauth_mcp/urls.py` dodaj:

```python
from oauth_mcp.views_dcr import DynamicClientRegistrationView
# ...
    path("o/register/", DynamicClientRegistrationView.as_view(), name="dcr"),
```

- [ ] **Step 4: Testy**

`src/oauth_mcp/tests/test_dcr.py`:

```python
import json
import pytest


@pytest.mark.django_db
def test_dcr_dozwolony_redirect_201(client):
    resp = client.post(
        "/o/register/",
        data=json.dumps(
            {"client_name": "Claude", "redirect_uris": ["https://claude.ai/cb"]}
        ),
        content_type="application/json",
    )
    assert resp.status_code == 201
    assert resp.json()["client_id"]
    assert resp.json()["token_endpoint_auth_method"] == "none"


@pytest.mark.django_db
def test_dcr_niedozwolony_redirect_400(client):
    resp = client.post(
        "/o/register/",
        data=json.dumps({"redirect_uris": ["https://evil.example/cb"]}),
        content_type="application/json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_dcr_nie_https_400(client):
    resp = client.post(
        "/o/register/",
        data=json.dumps({"redirect_uris": ["http://evil.example/cb"]}),
        content_type="application/json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_dcr_bez_csrf_dziala():
    # Domyślny test client ma enforce_csrf_checks=False → nie dowiódłby niczego.
    # Wymuszamy CSRF, by realnie przetestować csrf_exempt (W3).
    from django.test import Client

    csrf_client = Client(enforce_csrf_checks=True)
    resp = csrf_client.post(
        "/o/register/",
        data=json.dumps({"redirect_uris": ["http://localhost:8765/cb"]}),
        content_type="application/json",
    )
    assert resp.status_code == 201
```

- [ ] **Step 5: Uruchom**

```bash
uv run pytest src/oauth_mcp/tests/test_dcr.py -v
```

- [ ] **Step 6: Commit**

```bash
git add src/oauth_mcp/views_dcr.py src/oauth_mcp/urls.py src/oauth_mcp/tests/test_dcr.py
git commit -m "feat(oauth_mcp): DCR /o/register/ (RFC 7591, allowlista redirect_uri, rate-limit)"
```

---

### Task 8: Ekran zgody (`authorize.html`, read-only, `{% trans %}`)

**Files:**
- Create: `src/oauth_mcp/templates/oauth2_provider/authorize.html`
- Test: `src/oauth_mcp/tests/test_consent.py`

**Interfaces:**
- Produces: nadpisany szablon zgody DOT z komunikatem read-only.

- [ ] **Step 1: Szablon**

`src/oauth_mcp/templates/oauth2_provider/authorize.html` (override DOT — apka
`oauth_mcp` przed `oauth2_provider` w INSTALLED_APPS zapewnia pierwszeństwo;
jeśli nie — patrz Step 3). Styl Foundation + `fi-icon`, literały `{% trans %}`:

```django
{% extends "base.html" %}
{% load i18n %}
{% block content %}
<div class="row">
  <div class="column">
    <h3><span class="fi-key"></span> {% trans "Autoryzacja aplikacji" %}</h3>
    {% if not error %}
    <p>
      {% blocktrans with name=application.name %}Aplikacja <strong>{{ name }}</strong>
      prosi o <strong>ODCZYT</strong> danych BPP w Twoim imieniu.{% endblocktrans %}
    </p>
    <p>{% trans "Zakres:" %}</p>
    <ul>
      {% for opis in scopes_descriptions %}<li>{{ opis }}</li>{% endfor %}
    </ul>
    <form method="post" action="{% url 'oauth2_provider:authorize' %}">
      {% csrf_token %}
      {% for field in form %}{{ field }}{% endfor %}
      <button type="submit" class="button alert" name="allow" value="">
        {% trans "Odmów" %}
      </button>
      <button type="submit" class="button success" name="allow" value="Authorize">
        {% trans "Zezwól na odczyt" %}
      </button>
    </form>
    {% else %}
    <p class="alert callout">{{ error.error }}: {{ error.description }}</p>
    {% endif %}
  </div>
</div>
{% endblock %}
```

- [ ] **Step 2: Test renderu**

`src/oauth_mcp/tests/test_consent.py`:

```python
import pytest
from model_bakery import baker
from oauth2_provider.models import get_application_model


@pytest.mark.django_db
def test_ekran_zgody_pokazuje_readonly(client, django_user_model):
    # base.html + context-processory BPP wolą mieć Uczelnia (D7).
    baker.make("bpp.Uczelnia")
    Application = get_application_model()
    user = baker.make(django_user_model)
    app = Application.objects.create(
        user=user,
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris="https://claude.ai/cb",
        name="Claude",
    )
    client.force_login(user)
    resp = client.get(
        "/o/authorize/",
        {
            "response_type": "code",
            "client_id": app.client_id,
            "redirect_uri": "https://claude.ai/cb",
            "code_challenge": "x" * 43,
            "code_challenge_method": "S256",
            "scope": "read",
        },
    )
    assert resp.status_code == 200
    assert b"ODCZYT" in resp.content
    assert b"Claude" in resp.content
```

- [ ] **Step 3: Uruchom (i ewentualna korekta pierwszeństwa szablonu)**

```bash
uv run pytest src/oauth_mcp/tests/test_consent.py -v
```

Jeśli render bierze szablon DOT zamiast naszego: upewnij się, że `oauth_mcp`
jest w INSTALLED_APPS **przed** `oauth2_provider` (APP_DIRS szuka po kolejności),
albo dodaj `DIRS` z `src/oauth_mcp/templates`. Sprawdź, że `base.html` istnieje
i dostarcza blok `content`.

- [ ] **Step 4: Commit**

```bash
git add src/oauth_mcp/templates src/oauth_mcp/tests/test_consent.py
git commit -m "feat(oauth_mcp): ekran zgody read-only (authorize.html, i18n)"
```

---

### Task 9: Revoke-on-password-change + is_active (signal)

**Files:**
- Create: `src/oauth_mcp/signals.py`
- Test: `src/oauth_mcp/tests/test_revoke_signals.py`

**Interfaces:**
- Produces: receiver kasujący tokeny usera po zmianie hasła.
- Consumes: `apps.ready()` z Task 1 (import `signals`).

- [ ] **Step 1: Implementacja**

`src/oauth_mcp/signals.py`:

```python
from django.contrib.auth import get_user_model
from django.db.models.signals import pre_save
from django.dispatch import receiver


@receiver(pre_save, sender=get_user_model())
def revoke_tokens_on_password_change(sender, instance, update_fields=None, **kwargs):
    """Zmiana hasła / dezaktywacja → skasuj tokeny OAuth usera (spec §5.7/W-D)."""
    if not instance.pk:
        return
    # Tani short-circuit (D6): np. `update last_login` przy każdym logowaniu
    # przekazuje update_fields={"last_login"} → nie ruszamy DB.
    if update_fields is not None and not (
        {"password", "is_active"} & set(update_fields)
    ):
        return
    try:
        stary = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    haslo_zmienione = stary.password != instance.password
    dezaktywowany = stary.is_active and not instance.is_active
    if haslo_zmienione or dezaktywowany:
        from oauth2_provider.models import (
            get_access_token_model,
            get_refresh_token_model,
        )

        get_access_token_model().objects.filter(user=instance).delete()
        get_refresh_token_model().objects.filter(user=instance).delete()
```

- [ ] **Step 2: Testy**

`src/oauth_mcp/tests/test_revoke_signals.py`:

```python
import pytest
from oauth2_provider.models import get_access_token_model


@pytest.mark.django_db
def test_zmiana_hasla_kasuje_tokeny(access_token):
    user, tok = access_token()
    AccessToken = get_access_token_model()
    assert AccessToken.objects.filter(user=user).exists()
    user.set_password("nowe-haslo-123")
    user.save()
    assert not AccessToken.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_dezaktywacja_kasuje_tokeny(access_token):
    user, tok = access_token()
    AccessToken = get_access_token_model()
    user.is_active = False
    user.save()
    assert not AccessToken.objects.filter(user=user).exists()
```

- [ ] **Step 3: Uruchom**

```bash
uv run pytest src/oauth_mcp/tests/test_revoke_signals.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/oauth_mcp/signals.py src/oauth_mcp/tests/test_revoke_signals.py
git commit -m "feat(oauth_mcp): revoke tokenów przy zmianie hasła / dezaktywacji"
```

---

### Task 10: Naprawa propagacji `next` przy logowaniu Microsoft

**Files:**
- Modify: `src/django_bpp/urls.py` (wariant `microsoft_auth`, ~472)
- Test: `src/oauth_mcp/tests/test_microsoft_next.py`

**Interfaces:**
- Produces: `?next=` przeżywa redirect na Microsoft (spec §4/W5).

- [ ] **Step 1: Dodaj `query_string=True`**

W `src/django_bpp/urls.py`, w bloku `elif apps.is_installed("microsoft_auth")`,
zmień:

```python
        url(
            r"^accounts/login/$",
            RedirectView.as_view(
                pattern_name="microsoft_auth:to-auth-redirect",
                query_string=True,
            ),
            name="login_form",
        ),
```

- [ ] **Step 2: Test (warunkowy — tylko gdy microsoft_auth aktywne)**

`src/oauth_mcp/tests/test_microsoft_next.py`:

```python
import pytest
from django.apps import apps


@pytest.mark.skipif(
    not apps.is_installed("microsoft_auth"),
    reason="wariant Microsoft nieaktywny w tej konfiguracji",
)
@pytest.mark.django_db
def test_login_zachowuje_next(client):
    resp = client.get("/accounts/login/?next=/o/authorize/%3Ffoo%3Dbar")
    assert resp.status_code == 302
    assert "next=" in resp["Location"]
```

> Jeśli `microsoft_auth` nie jest instalowane w środowisku testów, test się
> skipnie — to OK; naprawa i tak jest w kodzie. ORCID: weryfikacja manualna
> (spec §4), poza tym planem.

- [ ] **Step 3: Uruchom**

```bash
uv run pytest src/oauth_mcp/tests/test_microsoft_next.py -v
```

- [ ] **Step 4: Commit**

```bash
git add src/django_bpp/urls.py src/oauth_mcp/tests/test_microsoft_next.py
git commit -m "fix(auth): zachowaj ?next= przy logowaniu Microsoft (query_string=True)"
```

---

### Task 11: Pełny test tańca Auth Code + PKCE + refresh (integracja)

**Files:**
- Test: `src/oauth_mcp/tests/test_flow_integration.py`

**Interfaces:**
- Consumes: całość Task 1–8.

- [ ] **Step 1: Test end-to-end (bez przeglądarki)**

`src/oauth_mcp/tests/test_flow_integration.py`:

```python
import base64
import hashlib
import pytest
from model_bakery import baker
from oauth2_provider.models import get_application_model


def _pkce():
    verifier = "a" * 64
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    return verifier, challenge


@pytest.mark.django_db
def test_pelny_taniec_pkce_i_token(client, django_user_model):
    Application = get_application_model()
    user = baker.make(django_user_model, is_active=True)
    app = Application.objects.create(
        user=user,
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris="https://claude.ai/cb",
        name="Claude",
    )
    client.force_login(user)
    verifier, challenge = _pkce()
    resp = client.post(
        "/o/authorize/",
        {
            "response_type": "code",
            "client_id": app.client_id,
            "redirect_uri": "https://claude.ai/cb",
            "scope": "read",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "allow": "Authorize",
        },
    )
    assert resp.status_code == 302
    code = resp["Location"].split("code=")[1].split("&")[0]

    token_resp = client.post(
        "/o/token/",
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "https://claude.ai/cb",
            "client_id": app.client_id,
            "code_verifier": verifier,
        },
    )
    assert token_resp.status_code == 200
    body = token_resp.json()
    assert body["token_type"].lower() == "bearer"
    assert body["scope"] == "read"

    # token działa na whoami
    who = client.get(
        "/api/v1/whoami/", HTTP_AUTHORIZATION=f"Bearer {body['access_token']}"
    )
    assert who.status_code == 200
    assert who.json()["id"] == user.pk

    # rotacja refresh (spec §10/§13/W2)
    refresh = body["refresh_token"]
    r1 = client.post(
        "/o/token/",
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": app.client_id,
        },
    )
    assert r1.status_code == 200
    assert r1.json()["refresh_token"] != refresh  # ROTATE_REFRESH_TOKEN
    # stary refresh już nieważny
    r2 = client.post(
        "/o/token/",
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": app.client_id,
        },
    )
    assert r2.status_code == 400


@pytest.mark.django_db
def test_revoke_uniewaznia_token(access_token, client):
    """Revoke → kolejny request/whoami → 401 (spec §10/§13/W2)."""
    user, tok = access_token()
    resp = client.post(
        "/o/revoke_token/",
        {"token": tok.token, "client_id": tok.application.client_id},
    )
    assert resp.status_code == 200
    who = client.get(
        "/api/v1/whoami/", HTTP_AUTHORIZATION=f"Bearer {tok.token}"
    )
    assert who.status_code == 401
```

- [ ] **Step 2: Uruchom**

```bash
uv run pytest src/oauth_mcp/tests/test_flow_integration.py -v
```

Expected: PASS. Jeśli format redirectu/kodu różni się w wersji DOT — dostosuj
parsowanie `code`, zachowując intencję.

- [ ] **Step 3: Uruchom całość apki + ruff**

```bash
uv run pytest src/oauth_mcp/ -v
ruff format src/oauth_mcp; ruff check src/oauth_mcp
```

- [ ] **Step 4: Commit**

```bash
git add src/oauth_mcp/tests/test_flow_integration.py
git commit -m "test(oauth_mcp): pełny taniec Auth Code + PKCE + whoami"
```

---

### Task 12: Newsfragment + checklist scalenia

**Files:**
- Create: `newsfragments/<numer>.feature` (jeśli repo używa towncrier — sprawdź
  `newsfragments/` / `pyproject.toml`)
- Modify: ten plan (odhacz checklist)

- [ ] **Step 1: Newsfragment**

Sprawdź konwencję: `ls newsfragments/ 2>/dev/null | head`. Jeśli istnieje —
utwórz `newsfragments/<id>.feature`:

```text
Warstwa OAuth 2.1 (Authorization Server) dla serwera MCP: BPP wystawia
/o/authorize|token|register, RFC 8414 metadata i endpoint /api/v1/whoami/;
API przyjmuje token Bearer z uprawnieniami użytkownika (read-only).
```

- [ ] **Step 2: Checklist scalenia (NIE wykonywać w trakcie — przy merge do dev):**
  - [ ] `make baseline-update` (RAZ, po scaleniu — migracje `oauth2_provider`).
  - [ ] Jeśli scalane razem z Fazą 0 (`/szukaj/`): dołożyć test regresu
        „anonimowy `/szukaj/` działa" (tu nie ma tego endpointu).
  - [ ] Konfiguracja nginx `auth_request` (jeśli w deploymencie): wyłączyć
        `/o/*`, `/.well-known/*`, `/api/v1/*` spod bramki sesyjnej (spec §5.7/D6).
  - [ ] Weryfikacja manualna `next` dla ORCID (spec §4).
  - [ ] Rozważyć cron `cleartokens` (higiena DOT, spec §8/D3) ORAZ sprzątanie
        klientów DCR bez tokenów (spec §5.6).
  - [ ] Smoke na ŚWIEŻEJ bazie: `FirstRunWizardMiddleware` przekierowuje
        `/o/*` i `/.well-known/*` do kreatora, dopóki brak `Uczelnia` — testy
        tego nie łapią (`settings/test.py` usuwa ten middleware). Zweryfikuj na
        bazie z `Uczelnia`.

- [ ] **Step 3: Commit**

```bash
git add newsfragments/ docs/superpowers/plans/2026-07-11-mcp-oauth-authorization.md
git commit -m "docs(oauth_mcp): newsfragment + checklist scalenia"
```

---

## Poza tym planem (świadomie)

- **Dostęp bearer (odczyt) do `raport_slotow_*`** — te viewsety mają per-view
  `authentication_classes=[Basic]`, więc token MCP jest tam dziś ignorowany
  (odczyt niedostępny). Dołożenie `StrictOAuth2Authentication` do ich per-view
  list to osobny task, gdy pojawi się realna potrzeba (write i tak blokuje
  middleware z Task 4). Główny motywator (DjangoQL) tego nie wymaga — dlatego
  odraczamy (W1). NIE twierdzimy w tym planie, że raporty slotów działają przez
  token.
- Introspekcja z confidential clientem (§5.4c) — wariant alternatywny do
  `whoami`; dokładamy tylko gdy potrzebne. `/o/introspect/` jest zamontowany
  (base_urlpatterns), ale bez scope `introspection` pozostaje martwy — OK.
- `authorized_tokens` (cherry-pick management view, §5.2) — nice-to-have,
  osobny task gdy pojawi się potrzeba UI „moje autoryzacje".
- Cała strona `bpp-mcp` (§6) — osobny pakiet, osobna sesja, na gotowym BPP.
- RFC 8707 / audience binding — poza zakresem (DOT nie wspiera, §8/§11).

## Self-Review (wykonane przy pisaniu planu)

- **Spec coverage:** §5.1→T1, §5.2→T2, §5.3→T2, §5.4a→T3, §5.4b→T4, §5.4d→T5,
  §5.6 metadata→T6, §5.6 DCR→T7, §5.5→T8, §5.7 revoke→T9, §4 Microsoft→T10,
  przepływ §7→T11, §10 testy→rozproszone, checklist scalenia→T12. §5.4c
  (introspekcja) i §5.2 authorized_tokens świadomie odłożone (patrz wyżej).
- **Placeholdery:** brak „TBD"; każdy krok ma realny kod/komendę.
- **Type consistency:** `StrictOAuth2Authentication` (T3) używane w T5/T11;
  `access_token` fixture (T3 conftest) w T4/T5/T9; `get_access_token_model()`
  spójnie; issuer-root spójny T6↔spec.
