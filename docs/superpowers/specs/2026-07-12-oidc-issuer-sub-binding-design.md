# OIDC: trwałe wiązanie tożsamości po `(issuer, sub)`

**Data:** 2026-07-12
**Status:** projekt po 2 rundach review (Fable), do przeglądu użytkownika
**Dotyczy:** `src/oidc_integration/`, `src/bpp/models/profile.py`,
`src/bpp/views/profile.py`, `src/bpp/templates/bpp/profil_uzytkownika.html`,
`src/django_bpp/settings/base.py`, `src/django_bpp/urls.py`

## 1. Problem

Backend OIDC (`BppOIDCBackend`) dopasowuje konta **wyłącznie po adresie e-mail**
(dziedziczone `filter_users_by_claims` → `email__iexact`) i sprawdza jedynie
**obecność** claimu `email`, nie `email_verified`. Brak trwałego związania konta
z tożsamością IdP.

**Skutek (przejęcie konta / eskalacja uprawnień):** e-mail w OIDC to atrybut,
który podmiot realmu często sam ustawia (Account Console Keycloaka). Gdy claim
e-mail zbiegnie się z adresem istniejącego konta BPP, podmiot OIDC loguje się
**jako to konto**. Mitygacja „nowe konta bez `is_staff`" nie chroni — dla
istniejącego konta idzie gałąź `update_user`, która uprawnień nie zdejmuje.

**Cel:** wiązać tożsamość lokalną trwale i unikalnie z parą `(issuer, sub)`.
`sub` jest niezmienny i nadany przez IdP. Po świadomym powiązaniu zmiana e-maila
w Keycloaku nie ma znaczenia i nikt nie przejmie cudzego konta.

## 2. Decyzje projektowe (ustalone)

1. **Pierwsze wiązanie istniejącego konta = jawne linkowanie z re-auth
   hasłem.** Auto-dopasowanie po e-mailu do istniejących kont **wyłączone**.
   „Re-auth hasłem" oznacza **faktyczne potwierdzenie hasła** w formularzu
   linkowania, NIE samo `login_required` (§5) — sesja założona przez
   ORCID/Microsoft/LDAP spełniłaby `login_required` bez hasła.
2. **Nowe osoby (brak konta) = auto-provisioning + `sub` związany atomowo od
   razu.** Zostaje `OIDC_CREATE_USER=True`; świeże konto bez `is_staff`. Gate
   „kto z realmu w ogóle dostaje konto" — poza zakresem.
3. **`email_verified` w punktach zaufania, konfigurowalne** (§4.3).
4. **Magazyn: model `OIDCIdentity` w `oidc_integration`**, unikalność
   `(issuer, sub)`.
5. **Punkt wejścia linkowania: strona profilu**, sekcja per-uczelnia przez
   `oidc_login_enabled`.
6. **Grace Bind dla starych kont OIDC: opt-in, default OFF, twardo zawężony**
   (§7, §11).

## 3. Model danych i rejestracja aplikacji

### 3.1 Model

`src/oidc_integration/models.py` + `src/oidc_integration/migrations/`:

```python
class OIDCIdentity(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="oidc_identities",
    )
    issuer = models.CharField(max_length=255)   # znormalizowany iss (§4.0)
    sub = models.CharField(max_length=255)      # subject z id_token (niezmienny)
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["issuer", "sub"],
                                    name="uniq_oidc_identity"),
            models.UniqueConstraint(fields=["user", "issuer"],
                                    name="uniq_user_per_issuer"),
        ]
```

### 3.2 Rejestracja aplikacji — app ZAWSZE, routing WARUNKOWO

Dziś `oidc_integration` jest w `INSTALLED_APPS` **warunkowo** (`base.py:1309`),
a `src/django_bpp/urls.py` gate’uje OIDC na **`apps.is_installed(
"oidc_integration")`** w kilku miejscach (linie ~408, ~426, z `elif
apps.is_installed("microsoft_auth")` ~457, oraz montaż
`include("mozilla_django_oidc.urls")` ~410).

Żeby tabela `OIDCIdentity` istniała zawsze (baseline, brak migracji
post-hoc), **app rejestrujemy bezwarunkowo**, ale **routing i backend
odpinamy od `is_installed` i wiążemy z `settings.OIDC_LOGIN_ENABLED`**:

- W `base.py`: `oidc_integration` zawsze w `INSTALLED_APPS`; warunkowe
  zostaje tylko `AUTHENTICATION_BACKENDS += BppOIDCBackend`, `OIDC_RP_*`,
  endpointy.
- W `urls.py`: **każdy** gate `apps.is_installed("oidc_integration")` →
  `settings.OIDC_LOGIN_ENABLED`. Inaczej po zmianie z §3.2:
  `mozilla_django_oidc.urls` zamontowałby się wszędzie (`/oidc/authenticate/`
  bez konfiguracji → `ImproperlyConfigured`/500), a łańcuch `if oidc /
  elif microsoft / else formularz` zabiłby gałąź Microsoft-only (utrata
  `MicrosoftLogoutView`). Nowe trasy `/oidc/polacz/*` też pod
  `OIDC_LOGIN_ENABLED` (`BppOIDCBackend()` w link-view rzuci
  `ImproperlyConfigured` bez konfiguracji — `__init__` biblioteki czyta
  `OIDC_OP_TOKEN_ENDPOINT` bez defaultu).
- **Efekt uboczny (zamierzony, do odnotowania):** `OidcIntegrationConfig.
  ready()` instaluje guard easyaudit gdy `easyaudit` jest zainstalowane —
  po zmianie zadziała na wszystkich instalacjach z easyaudit (nie tylko
  OIDC). Ten sam `KeyError('username')` dotyczy Microsoft/ORCID, więc
  szersze działanie jest pożądane; odnotowane świadomie.

## 4. Logika dopasowania (`BppOIDCBackend`)

### 4.0 Kanoniczny `issuer` — jedno źródło, walidacja `iss`

Issuer do zapisu i do filtrowania musi być identyczny. Zasady:

- Kanoniczny issuer = `payload["iss"]` ze **zweryfikowanego id_token**,
  znormalizowany `rstrip("/")`.
- **Nośnik: `claims`, nie stan na `self`.** `get_userinfo` już zwraca kopię
  claims (`_normalized`, `backends.py:167-181`) — tam dokładamy
  `claims["iss"] = normalize(payload["iss"])`; `filter_users_by_claims`
  czyta z `claims`. (Instancja backendu jest per-`authenticate()`, ale kopia
  w claims jest czystsza i jawna.)
- Dołożyć `settings.OIDC_OP_ISSUER = _OIDC_CONFIG["issuer"]` (`base.py`).
- **Walidacja w override `verify_token`** (payload dostępny, `auth.py:194`):
  `normalize(payload["iss"]) == normalize(settings.OIDC_OP_ISSUER)`, inaczej
  `SuspiciousOperation`. Tam też tanio dołożyć sprawdzenie `aud` (biblioteka
  ma `verify_aud=False`). Pokrywa też ścieżkę linkowania (woła `verify_token`).

### 4.1 `filter_users_by_claims` — dopasowanie tylko po `(issuer, sub)`

```python
def filter_users_by_claims(self, claims):
    sub = claims.get("sub")
    issuer = claims.get("iss")   # wstrzyknięty w get_userinfo (§4.0)
    if not sub or not issuer:
        return self.UserModel.objects.none()
    return self.UserModel.objects.filter(
        oidc_identities__issuer=issuer, oidc_identities__sub=sub)
```

### 4.2 `create_user` — atomowo, fail-closed na kolizję e-maila

`create_user` woła się tylko, gdy dopasowanie po `sub` nic nie zwróciło.
**Cały override w `transaction.atomic()`** (biblioteczny `get_or_create_user`
NIE jest w transakcji, więc atomic zakładamy tu). Kolejność:

1. **Grace Bind** (jeśli włączony, §7) — przed fail-closed.
2. **Kolizja e-maila z istniejącym kontem** (bez grace) → `SuspiciousOperation`
   (fail closed), NIE twórz konta-cienia. E-mail wraca do gry **wyłącznie by
   ODMÓWIĆ**, nigdy by przyznać dostęp. (Komunikat dociera do usera przez
   mechanizm z §4.5 — samo `SuspiciousOperation` trafia tylko do logu.)
3. **Osoba nowa** → wymagaj zaufanego e-maila (§4.3), utwórz zwykłe konto,
   zwiąż tożsamość — odpornie na wyścig:

   ```python
   with transaction.atomic():
       user = self.UserModel.objects.create_user(username=..., email=email)
       ...  # is_staff=False, unusable password
       try:
           with transaction.atomic():  # savepoint
               OIDCIdentity.objects.create(user=user, issuer=issuer, sub=sub)
       except IntegrityError:
           raise _RaceLost()   # savepoint wycofany
   ```

   Przy `_RaceLost` (przegrany wyścig na `uniq_oidc_identity`): zewnętrzny
   `atomic` wycofuje też świeżego usera; **po** transakcji re-fetch
   `OIDCIdentity(issuer, sub)` zwycięzcy i zwróć jego `user`. `_unique_username`
   (`backends.py:229`) to check-then-create → obsłużyć też `IntegrityError` na
   `username` (retry z kolejnym sufiksem).

### 4.3 `email_verified` — źródło, zaufanie, punkty użycia

- **Źródło:** `email_verified` w Keycloaku jest w **id_token (payload)**,
  userinfo często je pomija. W `get_userinfo` (chokepoint) scalamy do
  `claims["email_verified"]` z `payload` (pierwszeństwo) i userinfo (fallback).
- **Warunek zaufania e-mailowi** (jedno miejsce, anotowane w `_normalized`):

  ```
  email_trusted = (
      email_verified is True
      and not email_from_preferred_username_fallback   # backends.py:157-159
      and resolved_email.lower() == (payload.get("email") or "").lower()
  )
  ```

  Trzeci warunek jest kluczowy: BPP jest **mail-first**
  (`DEFAULT_EMAIL_CLAIMS=("mail","email",...)`, `conf.py:30`), więc rozwiązany
  adres często pochodzi z claimu `mail`, a `email_verified` poświadcza claim
  `email`. Jeśli się różnią — `email_verified` dotyczy INNEGO adresu → nie ufamy.
  `_normalized` anotuje kopię claims: `claims["email_verified"]`,
  `claims["_bpp_email_trusted"]`, `claims["iss"]` — jeden nośnik.
- **`create_user`:** wymagaj `email_trusted`, gdy `OIDC_REQUIRE_EMAIL_VERIFIED`.
- **Wiązanie autora — WSZYSTKIE ścieżki backendu OIDC** (`create_user` **i**
  `update_user`, `backends.py:226,269`): `sprobuj_dopasowac_autora` matchuje po
  e-mailu **oraz po imieniu/nazwisku** (`profile.py:143-163`); `given_name`/
  `family_name` z realmu też są edytowalne przez usera. Rozszerzamy sygnaturę:
  `sprobuj_dopasowac_autora(match_email=True, match_names=True)` (domyślnie
  zgodna wstecz). Backend OIDC przekazuje **oba** flagi = `email_trusted`
  (niezaufany e-mail → nie matchuj autora ani po e-mailu, ani po nazwisku).
  Wywołanie z `ProfilUzytkownikaView.get` (`views/profile.py:24`) zostaje
  domyślne.

### 4.4 Konfiguracja (`base.py` / `conf.py`)

- `OIDC_REQUIRE_EMAIL_VERIFIED` (default `True`).
- `OIDC_OP_ISSUER` (= `_OIDC_CONFIG["issuer"]`).
- `OIDC_GRACE_BIND_ENABLED` (**default `False`**).
- Per-realm env: `DJANGO_BPP_OIDC_<SKROT>_REQUIRE_EMAIL_VERIFIED`,
  `DJANGO_BPP_OIDC_<SKROT>_GRACE_BIND` (i warianty bez skrótu), czytane w
  `conf.py` analogicznie do `EMAIL_CLAIMS`.

### 4.5 UX odmowy (fail-closed musi dotrzeć do usera)

`SuspiciousOperation` z `create_user` jest łapane w `authenticate` (`auth.py:
319`) → `None` → callback robi ciche `login_failure` (redirect). Instrukcja
„najpierw połącz konto…" wylądowałaby tylko w logu. Dlatego przed `raise`
ustawiamy w sesji flagę z komunikatem (np. `oidc_error_message`), a szablon
strony logowania / `LOGIN_REDIRECT_URL_FAILURE` ją renderuje i czyści. To
kluczowe dla ścieżki migracji istniejących userów.

## 5. Jawne linkowanie (jeden callback, tryb w sesji)

Biblioteka prowadzi wymianę tokenu w `backend.authenticate` (`auth.py:278`),
a `redirect_uri` w wymianie kodu jest **na sztywno** = URL standardowego
callbacku (`auth.py:302`, `absolutify(reverse(OIDC_AUTHENTICATION_CALLBACK_URL))`).
Osobny callback linkowania wymagałby innego `redirect_uri` (niedopasowanie w
token exchange + rejestracja nowego URI w Keycloaku). Dlatego **reużywamy
standardowy callback `/oidc/callback/`** i rozgałęziamy po fladze w sesji.

Tryb link **nie może** przejść przez `get_or_create_user` normalnie: po sub
`filter_users_by_claims` zwróci pustkę → `create_user` → fail-closed na kolizji
e-maila z **własnym kontem** usera → odmowa. Więc branchujemy w
`get_or_create_user`.

**Przepływ:**
1. Zalogowany user wchodzi na `/oidc/polacz/` (`SSOLinkInitView`,
   `login_required`).
2. **Re-auth hasłem:** formularz potwierdzenia hasła (`check_password` na
   `request.user`). Konto z nieużywalnym hasłem → odmowa linkowania tą drogą
   (komunikat: „to konto nie ma hasła lokalnego").
3. Po poprawnym haśle: zapis w sesji `oidc_link_mode=True`,
   `oidc_link_target=request.user.pk`, `request.session.save()`; redirect na
   **standardowy** init OIDC (`redirect_uri=/oidc/callback/`).
4. Keycloak wraca na `/oidc/callback/`; `request.user` to nadal ten sam user.
5. Override `get_or_create_user` (backend) wykrywa `self.request.session[
   "oidc_link_mode"]` (backend ma `self.request`, `auth.py:281`):
   - waliduje `request.user.pk == session["oidc_link_target"]`,
   - `OIDCIdentity.objects.get_or_create(issuer, sub, defaults={"user":
     target})` w atomic; jeśli trafi istniejącą innego usera → komunikat
     „tożsamość już powiązana",
   - **czyści flagi sesji**, zwraca `target` (re-login jako on sam —
     nieszkodliwe), pomijając `filter_users_by_claims`/`create_user`.
6. Kolizje łapie baza (`uniq_oidc_identity`, `uniq_user_per_issuer`).

Zwykłe logowanie (bez flagi) idzie standardową ścieżką — bez zmian zachowania.

## 6. Punkt wejścia w profilu

`ProfilUzytkownikaView` (`bpp/profil_uzytkownika.html`):

- `get_context_data` dokłada `oidc_identities = user.oidc_identities.all()`
  (tabela istnieje zawsze, §3.2).
- Szablon: sekcja „Logowanie SSO" tylko gdy `oidc_login_enabled`
  (context processor `oidc_auth_status`, per-uczelnia). Lista powiązań +
  `linked_at`, albo przycisk „Połącz konto z SSO" → `/oidc/polacz/`.
- **„Odłącz"**: **POST + CSRF** (nie GET-link); **zablokowane, gdy konto ma
  nieużywalne hasło i to jego jedyna tożsamość** (self-lockout — ta sama
  pułapka co w §7).

## 7. Grace Bind (opt-in, default OFF, zawężony)

**Pułapka:** stare konta OIDC mają **nieużywalne hasło** — po wdrożeniu bez
`sub` nie zalogują się przez OIDC, hasłem też nie, i nie użyją linkowania
(wymaga hasła).

**Ale predykat „nieużywalne hasło + `is_staff=False`" NIE identyfikuje kont
czysto-OIDC** — spełniają go też konta **LDAP** (receiver `populate_bppuser`
zeruje `is_staff`, `profile.py:235`) i **Microsoft-auth**, mające uprawnienia
z **grup**, `pbn_token`, powiązanego `autora`. Dlatego Grace Bind jest
**opt-in (default OFF)** i wiąże `sub` jednorazowo tylko, gdy WSZYSTKIE:
- nie znaleziono konta po `sub`, oraz
- `email_trusted` (§4.3), oraz kolizja e-maila trafia w **dokładnie jedno**
  konto (`email__iexact` może zwrócić >1 — wtedy odmowa), które:
  - `is_staff=False`, `is_superuser=False`, `is_active=True`, oraz
  - `has_usable_password() == False`, oraz
  - `groups.exists() == False` i brak `user_permissions`, oraz
  - `pbn_token` pusty, oraz
  - `oidc_identities.exists() == False` (blokuje **cross-realm takeover**).

Ustanowienie atomowo (jak §4.2).

**Residual risk (§11):** nawet zawężony grace ufa `email_verified` realmu;
konto z powiązanym `autorem` (bez grup/pbn/staff) nadal może zostać raz
przejęte przy fałszywym `email_verified`. Stąd default OFF. **Alternatywa bez
grace:** management command wiążący `OIDCIdentity` dla znanych kont ręcznie.

## 8. Testy (repro-first, TDD)

1. **Takeover (staff)** — superuser e-mail `X`; login OIDC inny `sub` + e-mail
   `X` → odmowa.
2. **Takeover (grupa/pbn)** — `is_staff=False` ale w grupie z uprawnieniami /
   z `pbn_token`; ten sam wektor → odmowa także przy włączonym grace.
3. **Cross-realm** — konto z `OIDCIdentity(issuer=A)`; login z realmu B → odmowa.
4. **Zmiana e-maila** — konto powiązane po `sub`; realm zmienia e-mail → login
   trafia w to samo konto.
5. **Nowa osoba** — brak konta/kolizji → konto + tożsamość; `email_verified`
   tylko w id_token (brak w userinfo) → akceptacja; brak → odmowa (przy require).
6. **Mail-first mismatch** — `mail` != claim `email`, `email_verified=true` na
   `email` → e-mail NIEzaufany (create odrzucony, autor nie matchowany).
7. **Fallback preferred_username** — e-mail z `preferred_username` → niezaufany.
8. **Autor po nazwisku** — niezaufany e-mail + kolizja `imiona/nazwisko` →
   autor NIE dopięty (dowód `match_names=False`).
9. **Linkowanie** — user re-auth hasłem łączy własne konto (e-mail koliduje z
   samym sobą) → `OIDCIdentity` powstaje bez `SuspiciousOperation`; konto z
   nieużywalnym hasłem → odmowa re-auth; `request.user != link_target` →
   odmowa; ten sam `sub` do drugiego konta → odmowa (unique).
10. **Współbieżność** — dwa równoległe pierwsze loginy tym samym `sub` → jedno
    konto, jedna tożsamość, brak sieroty; wyścig na `username` obsłużony.
11. **Issuer/aud** — `payload["iss"]` != `OIDC_OP_ISSUER` → odmowa; normalizacja
    trailing slash; zły `aud` → odmowa.
12. **UX odmowy** — fail-closed ustawia komunikat widoczny na stronie logowania.
13. **Grace** — happy-path (konto czysto-OIDC, wszystkie warunki) wiąże raz;
    `OIDC_GRACE_BIND_ENABLED=False` → odmowa; `email__iexact` >1 kont → odmowa.
14. **Profil** — sekcja tylko przy `oidc_login_enabled`; „Odłącz" wymaga POST;
    self-lockout zablokowany.

## 9. Poza zakresem (świadomie)

- Gate „kto z realmu dostaje konto" (rola/grupa) — osobny TODO.
- Mapowanie ról Keycloaka na grupy/uprawnienia.
- SSO dla kont uprzywilejowanych bez jawnego linkowania (odrzucone).

## 10. Migracje, urls i baseline

- `oidc_integration` **zawsze** w `INSTALLED_APPS`; gate’y w `urls.py`
  przepięte `apps.is_installed` → `settings.OIDC_LOGIN_ENABLED` (§3.2).
- `oidc_integration/migrations/0001_initial.py` (tworzy `OIDCIdentity`).
- `sprobuj_dopasowac_autora` — zmiana sygnatury, bez migracji `bpp`.
- Po scaleniu: `make baseline-update` (delta), raz przy merge’u.
- Newsfragment towncrier (`*.bugfix.rst`).
- Dezaktywacja konta odcina SSO (biblioteka sprawdza `is_active` w callbacku).

## 11. Punkty do przeglądu (decyzje otwarte)

1. **Grace Bind default OFF + residual risk (§7)** — akceptowalny kompromis,
   czy wolisz w ogóle bez grace (odzysk tylko management-command)?
2. **`email_verified` default `True`** — czy realmy (UAFM LDAP itd.) emitują
   `email_verified` w id_token i czy `mail` == `email`? Jeśli nie, per-realm
   `REQUIRE_EMAIL_VERIFIED=0`.
3. **Re-auth hasłem przy linkowaniu (§2.1/§5)** — potwierdź, że konta bez hasła
   lokalnego (LDAP/Microsoft/ORCID) świadomie NIE mogą linkować tą drogą.
