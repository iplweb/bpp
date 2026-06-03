# Logowanie przez OpenID Connect (Keycloak) — design

Data: 2026-06-03
Status: spec dla **spike'a discovery** (faza 1). Reguły ról/deny dopisywane
po obejrzeniu realnych claimów.

## Cel

Umożliwić użytkownikom logowanie do BPP przez zewnętrzny serwer OpenID
Connect (Keycloak realm `KA` na `auth.uafm.edu.pl`), przepływem
**Authorization Code** (redirect). Hasła użytkowników nigdy nie dotykają
BPP — uwierzytelnia je Keycloak.

## Decyzje (ustalone z użytkownikiem)

- **Flow**: Authorization Code (redirect), nie ROPC.
- **Provisioning**: auto-tworzenie kont `BppUser` przy pierwszym logowaniu.
  (Faza 2 dołoży filtry/deny — patrz „Poza zakresem spike'a”.)
- **Biblioteka**: `mozilla-django-oidc`. Wybrana, bo jej udokumentowane
  hooki (`verify_claims`, `create_user`, `filter_users_by_claims`,
  `update_user`) mapują się 1:1 na wymagane reguły „kogo nie wpuszczamy /
  komu nie tworzymy kont / jak nadać role”.
- **Konfiguracja**: zmienne środowiskowe, kluczowane skrótem uczelni, z
  fallbackiem bez skrótu:

  | Zmienna (z prefiksem)                 | Fallback                        | Znaczenie     |
  |---------------------------------------|---------------------------------|---------------|
  | `DJANGO_BPP_OIDC_UAFM_CLIENT_ID`      | `DJANGO_BPP_OIDC_CLIENT_ID`     | client_id     |
  | `DJANGO_BPP_OIDC_UAFM_CLIENT_SECRET`  | `DJANGO_BPP_OIDC_CLIENT_SECRET` | client_secret |
  | `DJANGO_BPP_OIDC_UAFM_ISSUER`         | `DJANGO_BPP_OIDC_ISSUER`        | issuer URL    |

  `UAFM` = `Uczelnia.skrot`. Aktywny skrót wykrywany automatycznie: jeśli
  w środowisku jest dokładnie jeden komplet `DJANGO_BPP_OIDC_<X>_*`, brany
  jest on; warianty bez prefiksu nadpisują/uzupełniają. Twarde wiązanie z
  `Uczelnia.objects.get_default().skrot` z bazy — faza 2.

## Architektura

Nowa aplikacja `src/oidc_integration/` (wzorzec `src/orcid_integration/`):

- `conf.py` — `discover_oidc_config()`: czyta env wg reguły wyżej, zwraca
  `{client_id, client_secret, issuer}` albo `None` (gdy nie skonfigurowano).
  Z `issuer` wyprowadza 4 endpointy konwencją Keycloaka
  (`/protocol/openid-connect/{auth,token,userinfo,certs}`).
- `backends.py` — `BppOIDCBackend(OIDCAuthenticationBackend)`. W spike'u:
  `verify_claims()` **loguje cały dict claimów** (`logger.info`) i deleguje
  do `super()`. Wyraźny `# TODO faza 2`: gating po rolach/grupach,
  deny-lista, „nie twórz konta”.
- `apps.py`, `urls.py` (re-eksport `mozilla_django_oidc.urls`),
  `templates/` (przycisk „Zaloguj przez <skrót>”), `tests/`.

### Wpięcie w `settings/base.py`

Blok warunkowy à la `if MICROSOFT_AUTH_CLIENT_ID:` — aktywny tylko gdy
`discover_oidc_config()` zwróci konfigurację:

- dodaje `oidc_integration` do `INSTALLED_APPS`,
- ustawia `OIDC_RP_CLIENT_ID/SECRET`, `OIDC_OP_*_ENDPOINT`,
  `OIDC_RP_SIGN_ALGO="RS256"`, `OIDC_RP_SCOPES="openid email profile"`,
  `OIDC_CREATE_USER=True`,
- dopisuje `oidc_integration.backends.BppOIDCBackend` do
  `AUTHENTICATION_BACKENDS`.

### Pozostałe punkty wpięcia

- `external_auth.py` — dopisać ścieżkę backendu do `EXTERNAL_AUTH_BACKENDS`,
  żeby `ConditionalPasswordChangeMiddleware` pominął politykę haseł dla
  userów OIDC.
- `urls.py` — warunkowy montaż `oidc/` (jak `microsoft_auth`).
- Szablon logowania — przycisk inicjujący `oidc_authentication_init`.

## Przepływ danych

1. User klika „Zaloguj przez UAFM” → `oidc_authentication_init` →
   redirect do `authorization_endpoint` Keycloaka (z state, nonce, PKCE).
2. User uwierzytelnia się na Keycloaku → powrót na
   `oidc/callback/` z kodem.
3. `OIDCAuthenticationCallbackView` wymienia kod na tokeny (backchannel),
   waliduje `id_token` przez JWKS, pobiera userinfo.
4. `BppOIDCBackend.verify_claims()` — loguje claimy, przepuszcza.
5. Auto-tworzenie/pobranie `BppUser`, `login()`, sesja.

## Obsługa błędów

- Brak env → apka OIDC w ogóle się nie ładuje (no-op), zero wpływu na
  istniejące logowanie hasłem/Microsoft/ORCID.
- Walidacja tokenu/JWKS — po stronie `mozilla-django-oidc` (rzuca →
  redirect na stronę błędu logowania).
- Logowanie odmów/wyjątków przez `logger` (zgodnie z regułą: żadnego
  cichego `except: pass`).

## Testy

- `conf.py`: rozwiązywanie env (prefiks vs fallback, brak konfiguracji,
  wyprowadzanie endpointów z issuer) — czysty unit, bez sieci.
- `backends.py`: `verify_claims` loguje i deleguje; auto-create tworzy
  `BppUser` (z `@pytest.mark.django_db`, `baker`).
- Bez e2e przeciw realnemu Keycloakowi — to wymaga sekretów i sieci;
  testujemy ręcznie po wgraniu env.

## Poza zakresem spike'a (faza 2, po obejrzeniu claimów)

- Gating studentów: filtr po roli/grupie z tokenu („nie wpuszczamy” /
  „nie tworzymy kont”).
- Mapowanie ról/grup Keycloaka → grupy/uprawnienia Django.
- Powiązanie z istniejącym `Autor` przez claim `person_id`.
- Wylogowanie z Keycloaka (`end_session_endpoint`).
- Twarde wiązanie skrótu z `Uczelnia` z bazy zamiast auto-detekcji env.
- Przełączenie wyprowadzania endpointów z konwencji Keycloaka na fetch
  `.well-known/openid-configuration` z cache.

## Wymagania od administratora Keycloak (realm KA)

1. Confidential client → `client_id` + `client_secret` (mam).
2. Standard Flow ON; Valid Redirect URI: `https://bpp.<domena>/oidc/callback/`.
3. Potwierdzenie `client_secret_basic`/`post` (nie tylko private_key_jwt/mTLS).
4. Scope'y w tokenie: `openid profile email` + unikalny `email`, `sub`.
5. (Faza 2) rola/grupa odróżniająca pracowników od studentów.
