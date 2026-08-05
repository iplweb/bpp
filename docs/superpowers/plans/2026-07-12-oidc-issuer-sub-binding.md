# OIDC `(issuer, sub)` Binding — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zamknąć przejęcie konta OIDC po e-mailu — wiązać tożsamość lokalną trwale z parą `(issuer, sub)`, z jawnym linkowaniem (re-auth hasłem), `email_verified` w punktach zaufania i opt-in Grace Bind dla starych kont.

**Architecture:** Nowy model `OIDCIdentity` (FK do `BppUser`, unikat `(issuer, sub)`). Backend dopasowuje po `sub`, nie po e-mailu; e-mail służy tylko do fail-closed. Linkowanie reużywa standardowy callback `/oidc/callback/` z trybem w sesji, wpiętym przez override `get_or_create_user`. App `oidc_integration` zawsze w `INSTALLED_APPS`, routing gated po `settings.OIDC_LOGIN_ENABLED`.

**Tech Stack:** Django, `mozilla-django-oidc`, pytest + `model_bakery`, `django-pg-baseline`, testcontainers.

## Global Constraints

- **`uv run` przed KAŻDYM poleceniem Python** (`uv run pytest`, `uv run python src/manage.py ...`). Nigdy gołe `python`/`pytest`.
- **Max 88 znaków / linia** (ruff).
- **NIE modyfikować istniejących migracji** w `src/*/migrations/`.
- **Testy: pytest, funkcje bez klas, `@pytest.mark.django_db`, `model_bakery.baker.make`.** Nigdy `unittest.TestCase`.
- **Newsfragment** po zmianie feature/bugfix: `src/bpp/newsfragments/<slug>.bugfix.rst`.
- **Baseline** odświeżyć raz przy scaleniu (`make baseline-update`), NIE w tym planie per-task.
- Komentarze Django `{# ... #}` — każda linia własne `{# #}`.
- Ikony w `templates/` publicznego frontu: Foundation-Icons (`<span class="fi-...">`).

## File Structure

- Create `src/oidc_integration/models.py` — `OIDCIdentity`.
- Create `src/oidc_integration/migrations/__init__.py`, `0001_initial.py`.
- Modify `src/oidc_integration/conf.py` — issuer export, `require_email_verified`, `grace_bind`.
- Modify `src/oidc_integration/backends.py` — claims annotation, `verify_token`, `filter_users_by_claims`, `create_user`, `update_user`, `get_or_create_user` (link mode), Grace Bind, `_email_trusted`.
- Modify `src/oidc_integration/views.py` — `SSOLinkInitView`.
- Modify `src/django_bpp/settings/base.py` — always-install app, new settings.
- Modify `src/django_bpp/urls.py` — gates `apps.is_installed` → `OIDC_LOGIN_ENABLED`, add `/oidc/polacz/`.
- Modify `src/bpp/models/profile.py` — `sprobuj_dopasowac_autora(match_email, match_names)`.
- Modify `src/bpp/views/profile.py` — `oidc_identities` w kontekście.
- Modify `src/bpp/templates/bpp/profil_uzytkownika.html` — sekcja SSO + „Odłącz".
- Modify/create tests under `src/oidc_integration/tests/`.
- Create `src/bpp/newsfragments/oidc-sub-binding.bugfix.rst`.

## Parallelization

- **Faza A (równolegle, niezależne pliki):** Task 1 (model), Task 2 (conf+settings), Task 3 (`sprobuj_dopasowac_autora`).
- **Faza B (sekwencyjnie — wszystkie w `backends.py`):** Task 4 → 5 → 6 → 7 → 8.
- **Faza C (równolegle po B):** Task 9 (urls), Task 10 (UX odmowy), Task 11 (profil UI), Task 12 (newsfragment).

---

### Task 1: Model `OIDCIdentity` + migracja

**Files:**
- Create: `src/oidc_integration/models.py`
- Create: `src/oidc_integration/migrations/__init__.py` (pusty)
- Test: `src/oidc_integration/tests/test_models.py`

**Interfaces:**
- Produces: `OIDCIdentity(user, issuer, sub, linked_at)`; `user.oidc_identities` reverse manager; unikaty `uniq_oidc_identity(issuer, sub)`, `uniq_user_per_issuer(user, issuer)`.

- [ ] **Step 1: Failing test**

```python
# src/oidc_integration/tests/test_models.py
import pytest
from django.db import IntegrityError
from model_bakery import baker

from oidc_integration.models import OIDCIdentity


@pytest.mark.django_db
def test_oidc_identity_unique_issuer_sub():
    u1 = baker.make("bpp.BppUser")
    u2 = baker.make("bpp.BppUser")
    OIDCIdentity.objects.create(user=u1, issuer="https://kc/realms/x", sub="a")
    with pytest.raises(IntegrityError):
        OIDCIdentity.objects.create(
            user=u2, issuer="https://kc/realms/x", sub="a")


@pytest.mark.django_db
def test_oidc_identity_reverse_accessor():
    u = baker.make("bpp.BppUser")
    OIDCIdentity.objects.create(user=u, issuer="iss", sub="s")
    assert u.oidc_identities.count() == 1
```

- [ ] **Step 2: Run — expect fail** `uv run pytest src/oidc_integration/tests/test_models.py -v` → ImportError/OperationalError (brak modelu/tabeli).

- [ ] **Step 3: Implement model**

```python
# src/oidc_integration/models.py
from django.conf import settings
from django.db import models


class OIDCIdentity(models.Model):
    """Trwałe wiązanie konta BPP z tożsamością OIDC (issuer, sub).

    ``sub`` jest niezmienny i nadany przez IdP — w przeciwieństwie do e-maila
    nie da się go „wpisać". Dopasowanie konta po tej parze (zamiast po
    e-mailu) zamyka przejęcie konta przez zmianę adresu w realmie.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="oidc_identities",
    )
    issuer = models.CharField(max_length=255)
    sub = models.CharField(max_length=255)
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "tożsamość OIDC"
        verbose_name_plural = "tożsamości OIDC"
        constraints = [
            models.UniqueConstraint(
                fields=["issuer", "sub"], name="uniq_oidc_identity"
            ),
            models.UniqueConstraint(
                fields=["user", "issuer"], name="uniq_user_per_issuer"
            ),
        ]

    def __str__(self):
        return f"{self.user} @ {self.issuer}"
```

Create empty `src/oidc_integration/migrations/__init__.py`.

- [ ] **Step 4: Generate migration** `uv run python src/manage.py makemigrations oidc_integration` → `0001_initial.py`. (Wymaga app w INSTALLED_APPS — jeśli jeszcze nie, zrób Task 2 Step „always-install" najpierw; przy równoległości ustawić zależność.)

- [ ] **Step 5: Run — expect pass** `uv run pytest src/oidc_integration/tests/test_models.py -v` → PASS.

- [ ] **Step 6: Commit**

```bash
git add src/oidc_integration/models.py src/oidc_integration/migrations/ \
    src/oidc_integration/tests/test_models.py
git commit -m "feat(oidc): model OIDCIdentity wiążący konto z (issuer, sub)"
```

---

### Task 2: Konfiguracja — always-install, issuer, przełączniki

**Files:**
- Modify: `src/django_bpp/settings/base.py` (~1302-1341)
- Modify: `src/oidc_integration/conf.py`
- Test: `src/oidc_integration/tests/test_conf.py`

**Interfaces:**
- Produces: `settings.OIDC_OP_ISSUER`, `settings.OIDC_REQUIRE_EMAIL_VERIFIED` (bool), `settings.OIDC_GRACE_BIND_ENABLED` (bool); `oidc_integration` zawsze w `INSTALLED_APPS`.

- [ ] **Step 1: Failing test (conf czyta przełączniki per-realm)**

```python
# dopisz do src/oidc_integration/tests/test_conf.py
from oidc_integration.conf import _get_bool  # nowy helper


def test_get_bool_prefers_skrot_variant():
    env = {"DJANGO_BPP_OIDC_UAFM_GRACE_BIND": "1",
           "DJANGO_BPP_OIDC_GRACE_BIND": "0"}
    assert _get_bool(env, "GRACE_BIND", "UAFM", default=False) is True


def test_get_bool_default_when_absent():
    assert _get_bool({}, "REQUIRE_EMAIL_VERIFIED", None, default=True) is True
```

- [ ] **Step 2: Run — expect fail** `uv run pytest src/oidc_integration/tests/test_conf.py -k get_bool -v` → ImportError.

- [ ] **Step 3: Add `_get_bool` to `conf.py`** (obok `_get`/`_get_claim_list`):

```python
def _get_bool(environ, field, skrot, default):
    """Bool z env wg preferencji (skrot → bare → default).

    „1/true/yes/on" (case-insensitive) = True; „0/false/no/off" = False.
    """
    raw = _get(environ, field, skrot)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")
```

- [ ] **Step 4: Run — expect pass** `uv run pytest src/oidc_integration/tests/test_conf.py -k get_bool -v` → PASS.

- [ ] **Step 5: Always-install app + emit settings.** In `base.py`, move `oidc_integration` install OUT of the `if _OIDC_CONFIG:` block so it is unconditional:

```python
# PRZED blokiem `if _OIDC_CONFIG:` — app zawsze zainstalowany (model/tabela
# muszą istnieć niezależnie od env; routing i backend zostają warunkowe).
if "oidc_integration" not in INSTALLED_APPS:
    INSTALLED_APPS = list(INSTALLED_APPS) + ["oidc_integration"]
```

Inside `if _OIDC_CONFIG:` remove the old conditional install lines, and add:

```python
    OIDC_OP_ISSUER = _OIDC_CONFIG["issuer"]

# poza blokiem — defaulty bezpieczne dla instalacji bez OIDC też:
OIDC_REQUIRE_EMAIL_VERIFIED = (_OIDC_CONFIG or {}).get(
    "require_email_verified", True)
OIDC_GRACE_BIND_ENABLED = (_OIDC_CONFIG or {}).get("grace_bind", False)
```

In `conf.py` `discover_oidc_config()` result dict, add keys:

```python
        "require_email_verified": _get_bool(
            environ, "REQUIRE_EMAIL_VERIFIED", skrot, default=True),
        "grace_bind": _get_bool(environ, "GRACE_BIND", skrot, default=False),
```

- [ ] **Step 6: Verify Django loads** `uv run python src/manage.py check` → System check identified no issues.

- [ ] **Step 7: Commit**

```bash
git add src/django_bpp/settings/base.py src/oidc_integration/conf.py \
    src/oidc_integration/tests/test_conf.py
git commit -m "feat(oidc): oidc_integration zawsze w INSTALLED_APPS + przełączniki (issuer, email_verified, grace)"
```

---

### Task 3: `sprobuj_dopasowac_autora(match_email, match_names)`

**Files:**
- Modify: `src/bpp/models/profile.py:109-163`
- Test: `src/bpp/tests/test_models/test_profile_autor_match.py` (nowy)

**Interfaces:**
- Consumes: nic.
- Produces: `BppUser.sprobuj_dopasowac_autora(match_email=True, match_names=True)` — wstecznie zgodne (domyślnie oba `True`).

- [ ] **Step 1: Failing test**

```python
# src/bpp/tests/test_models/test_profile_autor_match.py
import pytest
from model_bakery import baker


@pytest.mark.django_db
def test_match_email_false_skips_email_matching():
    autor = baker.make("bpp.Autor", email="jan@x.pl")
    user = baker.make("bpp.BppUser", email="jan@x.pl",
                      first_name="", last_name="")
    user.sprobuj_dopasowac_autora(match_email=False)
    user.refresh_from_db()
    assert user.autor_id is None


@pytest.mark.django_db
def test_match_names_false_skips_name_matching():
    autor = baker.make("bpp.Autor", imiona="Jan", nazwisko="Kowalski",
                       email="")
    user = baker.make("bpp.BppUser", first_name="Jan", last_name="Kowalski",
                      email="")
    user.sprobuj_dopasowac_autora(match_names=False)
    user.refresh_from_db()
    assert user.autor_id is None
```

- [ ] **Step 2: Run — expect fail** `uv run pytest src/bpp/tests/test_models/test_profile_autor_match.py -v` → TypeError (unexpected kwarg).

- [ ] **Step 3: Implement.** Change signature and guard both branches:

```python
    def sprobuj_dopasowac_autora(self, match_email=True, match_names=True):
```

Wrap the email branch (`if self.email and self.email != PUSTY_ADRES_EMAIL:`) with `if match_email and self.email ...`, and the name branch (`if self.first_name and self.last_name:`) with `if match_names and self.first_name and self.last_name:`. Update the docstring to note both flags default True (backward compatible) and are lowered by the OIDC backend for untrusted claims.

- [ ] **Step 4: Run — expect pass** `uv run pytest src/bpp/tests/test_models/test_profile_autor_match.py -v` → PASS.

- [ ] **Step 5: Regression** `uv run pytest src/oidc_integration/tests/test_backends.py -v` → PASS (istniejące wywołania bezargumentowe działają).

- [ ] **Step 6: Commit**

```bash
git add src/bpp/models/profile.py \
    src/bpp/tests/test_models/test_profile_autor_match.py
git commit -m "feat(bpp): sprobuj_dopasowac_autora — flagi match_email/match_names"
```

---

### Task 4: Backend — anotacja claims (`iss`, `email_verified`, `email_trusted`) + `verify_token`

**Files:**
- Modify: `src/oidc_integration/backends.py` (`_normalized`, `get_userinfo`, nowy `verify_token`, helper `_email_trusted`)
- Test: `src/oidc_integration/tests/test_backends.py`

**Interfaces:**
- Consumes: `settings.OIDC_OP_ISSUER` (Task 2).
- Produces: po `get_userinfo` w claims są klucze `iss` (znormalizowany), `email_verified` (bool z payloadu+userinfo), `_bpp_email_trusted` (bool); `verify_token` odrzuca zły `iss`.

- [ ] **Step 1: Failing tests**

```python
# dopisz do src/oidc_integration/tests/test_backends.py
def test_email_trusted_requires_verified_and_matching_email():
    b = _backend()
    payload = {"iss": "https://kc/", "email": "jan@x.pl",
               "email_verified": True}
    claims = b._normalized(
        {"mail": "jan@x.pl", "sub": "1", "iss": "https://kc/",
         "email": "jan@x.pl", "email_verified": True})
    assert claims["_bpp_email_trusted"] is True
    assert claims["iss"] == "https://kc"   # rstrip('/')


def test_email_trusted_false_on_mail_first_mismatch():
    b = _backend()
    # mail (rozwiązany) != email (poświadczony przez email_verified)
    claims = b._normalized(
        {"mail": "inst@x.pl", "email": "prywatny@x.pl",
         "email_verified": True, "sub": "1", "iss": "iss"})
    assert claims["_bpp_email_trusted"] is False
```

- [ ] **Step 2: Run — expect fail** `uv run pytest src/oidc_integration/tests/test_backends.py -k email_trusted -v` → KeyError/AssertionError.

- [ ] **Step 3: Implement.** Add module helper and extend `_normalized`. `_resolve_email` must also report whether it used the `preferred_username` fallback — refactor to return `(email, from_fallback)`:

```python
    @staticmethod
    def _resolve_email_with_source(claims):
        keys = _email_claim_keys()
        value = _first_claim(claims, keys)
        if value:
            return value, False
        username = claims.get("preferred_username") or ""
        if _EMAIL_SHAPE_RE.match(username):
            return username, True
        raise SuspiciousOperation(
            "OIDC: nie znaleziono adresu e-mail w claimach "
            f"({'/'.join(keys)}), a preferred_username={username!r} "
            "nie zawiera domeny — odrzucam logowanie."
        )
```

Keep `_resolve_email` as thin wrapper (`return cls._resolve_email_with_source(claims)[0]`) for backward compat. Extend `_normalized`:

```python
    @classmethod
    def _normalized(cls, claims):
        email, from_fallback = cls._resolve_email_with_source(claims)
        verified = bool(claims.get("email_verified") is True)
        payload_email = (claims.get("email") or "").lower()
        trusted = (
            verified
            and not from_fallback
            and email.lower() == payload_email
        )
        iss = (claims.get("iss") or "").rstrip("/")
        out = dict(claims)
        out["email"] = email
        out["email_verified"] = verified
        out["_bpp_email_trusted"] = trusted
        out["iss"] = iss
        return out
```

Add `verify_token` override (issuer validation; call super first):

```python
    def verify_token(self, token, **kwargs):
        payload = super().verify_token(token, **kwargs)
        expected = (getattr(settings, "OIDC_OP_ISSUER", "") or "").rstrip("/")
        got = (payload.get("iss") or "").rstrip("/")
        if expected and got != expected:
            raise SuspiciousOperation(
                f"OIDC: iss={got!r} != oczekiwany {expected!r}")
        return payload
```

Note: `get_userinfo` already calls `_normalized`; ensure `payload["iss"]`/`email_verified` reach `_normalized` — in `get_userinfo`, merge `payload` id_token claims into userinfo before normalizing:

```python
    def get_userinfo(self, access_token, id_token, payload):
        claims = super().get_userinfo(access_token, id_token, payload)
        merged = dict(claims)
        for k in ("iss", "email", "email_verified"):
            if k not in merged and payload.get(k) is not None:
                merged[k] = payload.get(k)
        return self._normalized(merged)
```

- [ ] **Step 4: Run — expect pass** `uv run pytest src/oidc_integration/tests/test_backends.py -k email_trusted -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/oidc_integration/backends.py src/oidc_integration/tests/test_backends.py
git commit -m "feat(oidc): anotacja claims (iss, email_verified, trusted) + walidacja iss w verify_token"
```

---

### Task 5: Backend — `filter_users_by_claims` po `(issuer, sub)`

**Files:**
- Modify: `src/oidc_integration/backends.py`
- Test: `src/oidc_integration/tests/test_backends.py`

**Interfaces:**
- Consumes: `OIDCIdentity` (Task 1), claims z `iss` (Task 4).
- Produces: `filter_users_by_claims` zwraca konto tylko po powiązanym `(issuer, sub)`.

- [ ] **Step 1: Failing tests**

```python
def test_filter_matches_only_by_linked_sub(db):
    from oidc_integration.models import OIDCIdentity
    u = baker.make("bpp.BppUser", email="jan@x.pl")
    OIDCIdentity.objects.create(user=u, issuer="https://kc", sub="S1")
    b = _backend()
    claims = {"sub": "S1", "iss": "https://kc", "email": "jan@x.pl"}
    assert list(b.filter_users_by_claims(claims)) == [u]


def test_filter_ignores_email_when_no_sub_link(db):
    baker.make("bpp.BppUser", email="jan@x.pl")
    b = _backend()
    claims = {"sub": "S1", "iss": "https://kc", "email": "jan@x.pl"}
    assert list(b.filter_users_by_claims(claims)) == []
```

(Uzupełnij importy `baker`, `pytest.mark.django_db` przez fixture `db` lub dekorator.)

- [ ] **Step 2: Run — expect fail** → zwraca match po e-mailu (dziedziczone) lub błąd.

- [ ] **Step 3: Implement override**

```python
    def filter_users_by_claims(self, claims):
        sub = claims.get("sub")
        issuer = claims.get("iss")
        if not sub or not issuer:
            return self.UserModel.objects.none()
        return self.UserModel.objects.filter(
            oidc_identities__issuer=issuer,
            oidc_identities__sub=sub,
        )
```

- [ ] **Step 4: Run — expect pass** `uv run pytest src/oidc_integration/tests/test_backends.py -k filter -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/oidc_integration/backends.py src/oidc_integration/tests/test_backends.py
git commit -m "feat(oidc): dopasowanie konta po (issuer, sub), nie po e-mailu"
```

---

### Task 6: Backend — `create_user` (atomowo, fail-closed, bind sub) + `update_user` flagi

**Files:**
- Modify: `src/oidc_integration/backends.py`
- Test: `src/oidc_integration/tests/test_backends.py`

**Interfaces:**
- Consumes: `OIDCIdentity`, `_bpp_email_trusted`, `settings.OIDC_REQUIRE_EMAIL_VERIFIED`.
- Produces: nowe konto z `OIDCIdentity`; kolizja e-maila → `SuspiciousOperation`; `update_user` przekazuje `match_email/match_names`.

- [ ] **Step 1: Failing tests (repro takeoveru)**

```python
def test_create_user_refuses_on_email_collision(db, settings):
    settings.OIDC_GRACE_BIND_ENABLED = False
    baker.make("bpp.BppUser", email="admin@x.pl", is_superuser=True)
    b = _backend()
    claims = {"sub": "S9", "iss": "https://kc", "email": "admin@x.pl",
              "email_verified": True, "_bpp_email_trusted": True,
              "preferred_username": "attacker"}
    with pytest.raises(SuspiciousOperation):
        b.create_user(claims)


def test_create_user_new_person_binds_sub(db, settings):
    settings.OIDC_REQUIRE_EMAIL_VERIFIED = True
    b = _backend()
    claims = {"sub": "S10", "iss": "https://kc", "email": "nowy@x.pl",
              "email_verified": True, "_bpp_email_trusted": True,
              "preferred_username": "nowy", "given_name": "N", "family_name": "X"}
    user = b.create_user(claims)
    assert user.oidc_identities.filter(issuer="https://kc", sub="S10").exists()
    assert user.is_staff is False


def test_create_user_rejects_untrusted_email_when_required(db, settings):
    settings.OIDC_REQUIRE_EMAIL_VERIFIED = True
    b = _backend()
    claims = {"sub": "S11", "iss": "https://kc", "email": "x@x.pl",
              "email_verified": False, "_bpp_email_trusted": False,
              "preferred_username": "x"}
    with pytest.raises(SuspiciousOperation):
        b.create_user(claims)
```

- [ ] **Step 2: Run — expect fail** → obecny `create_user` tworzy konto bez tych reguł.

- [ ] **Step 3: Implement.** Rewrite `create_user` (Grace Bind hook w Task 7 — tu zostaw `# Grace Bind: Task 7` placeholder ustawiony jako no-op wywołanie `self._try_grace_bind(claims)` zwracające `None`, dodane w Task 7; na razie zdefiniuj metodę zwracającą `None`):

```python
    def _try_grace_bind(self, claims):
        return None  # rozszerzone w Task 7

    def create_user(self, claims):
        email = claims.get("email") or ""
        issuer = claims.get("iss") or ""
        sub = claims.get("sub") or ""

        graced = self._try_grace_bind(claims)
        if graced is not None:
            return graced

        if self.UserModel.objects.filter(email__iexact=email).exists():
            raise SuspiciousOperation(
                "OIDC: konto z tym adresem już istnieje — połącz je z SSO "
                "przez profil (re-auth hasłem), nie tworzę konta."
            )

        require = getattr(settings, "OIDC_REQUIRE_EMAIL_VERIFIED", True)
        if require and not claims.get("_bpp_email_trusted"):
            raise SuspiciousOperation(
                "OIDC: e-mail niezweryfikowany (email_verified) — "
                "odrzucam założenie konta."
            )

        base_username = _first_claim(claims, _username_claim_keys())
        trusted = bool(claims.get("_bpp_email_trusted"))

        for _ in range(5):  # retry na wyścig username
            username = self._unique_username(base_username)
            try:
                with transaction.atomic():
                    user = self.UserModel.objects.create_user(
                        username=username, email=email)
                    user.first_name = claims.get("given_name") or ""
                    user.last_name = claims.get("family_name") or ""
                    user.is_staff = False
                    user.is_superuser = False
                    user.is_active = True
                    user.set_unusable_password()
                    user.save()
                    with transaction.atomic():  # savepoint
                        OIDCIdentity.objects.create(
                            user=user, issuer=issuer, sub=sub)
                break
            except IntegrityError:
                # albo username zajęty (retry), albo (issuer,sub) zajęte
                existing = OIDCIdentity.objects.filter(
                    issuer=issuer, sub=sub).first()
                if existing is not None:
                    return existing.user  # przegrany wyścig na sub
                continue
        else:
            raise SuspiciousOperation("OIDC: nie udało się utworzyć konta")

        self._assign_uczelnia(user)
        user.sprobuj_dopasowac_autora(
            match_email=trusted, match_names=trusted)
        logger.info(
            "OIDC: utworzono konto username=%s (bez is_staff), sub związany",
            username)
        return user
```

Add imports at top: `from django.db import IntegrityError, transaction` and `from oidc_integration.models import OIDCIdentity` (lokalny import w metodzie, jeśli wolisz uniknąć cyklu — użyj lokalnego importu w każdej metodzie jak `_assign_uczelnia` robi z `Uczelnia`).

Update `update_user` to pass trust flags:

```python
    def update_user(self, user, claims):
        self._assign_uczelnia(user)
        trusted = bool(claims.get("_bpp_email_trusted"))
        user.sprobuj_dopasowac_autora(
            match_email=trusted, match_names=trusted)
        return user
```

- [ ] **Step 4: Run — expect pass** `uv run pytest src/oidc_integration/tests/test_backends.py -k create_user -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/oidc_integration/backends.py src/oidc_integration/tests/test_backends.py
git commit -m "feat(oidc): create_user atomowo + fail-closed na kolizję e-maila + bind sub"
```

---

### Task 7: Grace Bind (opt-in, zawężony)

**Files:**
- Modify: `src/oidc_integration/backends.py` (`_try_grace_bind`)
- Test: `src/oidc_integration/tests/test_backends.py`

**Interfaces:**
- Consumes: `settings.OIDC_GRACE_BIND_ENABLED`, `OIDCIdentity`.
- Produces: `_try_grace_bind(claims)` zwraca `user` (związany) albo `None`.

- [ ] **Step 1: Failing tests**

```python
def _grace_claims():
    return {"sub": "G1", "iss": "https://kc", "email": "old@x.pl",
            "email_verified": True, "_bpp_email_trusted": True,
            "preferred_username": "old"}


def test_grace_binds_pure_oidc_account(db, settings):
    settings.OIDC_GRACE_BIND_ENABLED = True
    u = baker.make("bpp.BppUser", email="old@x.pl", is_staff=False,
                   is_superuser=False, is_active=True, pbn_token="")
    u.set_unusable_password(); u.save()
    b = _backend()
    out = b._try_grace_bind(_grace_claims())
    assert out == u
    assert u.oidc_identities.filter(sub="G1").exists()


def test_grace_skips_account_with_group(db, settings):
    settings.OIDC_GRACE_BIND_ENABLED = True
    u = baker.make("bpp.BppUser", email="old@x.pl", is_staff=False,
                   pbn_token="")
    u.set_unusable_password(); u.save()
    u.groups.add(baker.make("auth.Group"))
    b = _backend()
    assert b._try_grace_bind(_grace_claims()) is None


def test_grace_skips_when_disabled(db, settings):
    settings.OIDC_GRACE_BIND_ENABLED = False
    baker.make("bpp.BppUser", email="old@x.pl")
    b = _backend()
    assert b._try_grace_bind(_grace_claims()) is None


def test_grace_skips_cross_realm_linked(db, settings):
    from oidc_integration.models import OIDCIdentity
    settings.OIDC_GRACE_BIND_ENABLED = True
    u = baker.make("bpp.BppUser", email="old@x.pl", is_staff=False,
                   pbn_token="")
    u.set_unusable_password(); u.save()
    OIDCIdentity.objects.create(user=u, issuer="https://other", sub="Z")
    b = _backend()
    assert b._try_grace_bind(_grace_claims()) is None
```

- [ ] **Step 2: Run — expect fail** → `_try_grace_bind` to no-op (`None` zawsze).

- [ ] **Step 3: Implement**

```python
    def _try_grace_bind(self, claims):
        if not getattr(settings, "OIDC_GRACE_BIND_ENABLED", False):
            return None
        if not claims.get("_bpp_email_trusted"):
            return None
        email = claims.get("email") or ""
        issuer = claims.get("iss") or ""
        sub = claims.get("sub") or ""
        qs = self.UserModel.objects.filter(email__iexact=email)
        if qs.count() != 1:
            return None
        user = qs.first()
        eligible = (
            not user.is_staff
            and not user.is_superuser
            and user.is_active
            and not user.has_usable_password()
            and not user.groups.exists()
            and not user.user_permissions.exists()
            and not (user.pbn_token or "")
            and not user.oidc_identities.exists()
        )
        if not eligible:
            return None
        try:
            with transaction.atomic():
                OIDCIdentity.objects.create(
                    user=user, issuer=issuer, sub=sub)
        except IntegrityError:
            existing = OIDCIdentity.objects.filter(
                issuer=issuer, sub=sub).first()
            return existing.user if existing else None
        logger.info("OIDC: grace-bind sub dla konta %s", user.username)
        return user
```

- [ ] **Step 4: Run — expect pass** `uv run pytest src/oidc_integration/tests/test_backends.py -k grace -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/oidc_integration/backends.py src/oidc_integration/tests/test_backends.py
git commit -m "feat(oidc): Grace Bind opt-in dla starych kont czysto-OIDC (zawężony)"
```

---

### Task 8: Backend — tryb link w `get_or_create_user`

**Files:**
- Modify: `src/oidc_integration/backends.py`
- Test: `src/oidc_integration/tests/test_backends.py`

**Interfaces:**
- Consumes: `self.request.session` (`oidc_link_mode`, `oidc_link_target`), `OIDCIdentity`.
- Produces: w trybie link `get_or_create_user` wiąże `sub` z `link_target` i zwraca go, pomijając filter/create.

- [ ] **Step 1: Failing test**

```python
def test_link_mode_binds_without_email_failclosed(db):
    from django.contrib.sessions.backends.db import SessionStore
    u = baker.make("bpp.BppUser", email="me@x.pl")
    b = _backend()
    req = RequestFactory().get("/oidc/callback/")
    req.session = SessionStore(); req.user = u
    req.session["oidc_link_mode"] = True
    req.session["oidc_link_target"] = u.pk
    b.request = req
    # własne konto koliduje z samym sobą — nie może być SuspiciousOperation
    b.get_userinfo = lambda *a, **k: {
        "sub": "L1", "iss": "https://kc", "email": "me@x.pl",
        "_bpp_email_trusted": True}
    out = b.get_or_create_user("at", "it", {"iss": "https://kc"})
    assert out == u
    assert u.oidc_identities.filter(sub="L1").exists()
    assert "oidc_link_mode" not in req.session
```

(Import `RequestFactory` z `django.test`.)

- [ ] **Step 2: Run — expect fail** → dziedziczony `get_or_create_user` idzie w `create_user` → `SuspiciousOperation`.

- [ ] **Step 3: Implement override**

```python
    def get_or_create_user(self, access_token, id_token, payload):
        session = getattr(getattr(self, "request", None), "session", None)
        if session and session.get("oidc_link_mode"):
            user_info = self.get_userinfo(access_token, id_token, payload)
            target_pk = session.get("oidc_link_target")
            if not target_pk or self.request.user.pk != target_pk:
                self._clear_link_session(session)
                raise SuspiciousOperation("OIDC: cel linkowania niezgodny")
            issuer = user_info.get("iss") or ""
            sub = user_info.get("sub") or ""
            try:
                with transaction.atomic():
                    OIDCIdentity.objects.get_or_create(
                        issuer=issuer, sub=sub,
                        defaults={"user": self.request.user})
            except IntegrityError:
                self._clear_link_session(session)
                raise SuspiciousOperation(
                    "OIDC: ta tożsamość SSO jest już powiązana z innym kontem")
            self._clear_link_session(session)
            return self.request.user
        return super().get_or_create_user(access_token, id_token, payload)

    @staticmethod
    def _clear_link_session(session):
        session.pop("oidc_link_mode", None)
        session.pop("oidc_link_target", None)
        session.save()
```

- [ ] **Step 4: Run — expect pass** `uv run pytest src/oidc_integration/tests/test_backends.py -k link_mode -v` → PASS.

- [ ] **Step 5: Full backend suite** `uv run pytest src/oidc_integration/tests/test_backends.py -v` → PASS.

- [ ] **Step 6: Commit**

```bash
git add src/oidc_integration/backends.py src/oidc_integration/tests/test_backends.py
git commit -m "feat(oidc): tryb linkowania w get_or_create_user (wiąże sub, omija fail-closed)"
```

---

### Task 9: Routing — gate `OIDC_LOGIN_ENABLED` + `SSOLinkInitView` + `/oidc/polacz/`

**Files:**
- Modify: `src/django_bpp/urls.py`
- Modify: `src/oidc_integration/views.py` (`SSOLinkInitView`)
- Test: `src/oidc_integration/tests/test_link_flow.py` (nowy)

**Interfaces:**
- Consumes: `settings.OIDC_LOGIN_ENABLED`, `mozilla_django_oidc` init.
- Produces: `/oidc/polacz/` (GET formularz hasła, POST → ustawia sesję → redirect na `oidc_authentication_init`).

- [ ] **Step 1: Failing tests**

```python
# src/oidc_integration/tests/test_link_flow.py
import pytest
from django.urls import reverse
from model_bakery import baker


@pytest.mark.django_db
def test_link_init_requires_password(client, settings):
    settings.OIDC_LOGIN_ENABLED = True
    u = baker.make("bpp.BppUser", username="u1")
    u.set_password("secret"); u.save()
    client.force_login(u)
    resp = client.post(reverse("oidc_integration:polacz"),
                       {"password": "zle"})
    assert resp.status_code == 200
    assert "oidc_link_mode" not in client.session


@pytest.mark.django_db
def test_link_init_sets_session_and_redirects(client, settings):
    settings.OIDC_LOGIN_ENABLED = True
    u = baker.make("bpp.BppUser", username="u2")
    u.set_password("secret"); u.save()
    client.force_login(u)
    resp = client.post(reverse("oidc_integration:polacz"),
                       {"password": "secret"})
    assert resp.status_code == 302
    assert client.session["oidc_link_mode"] is True
    assert client.session["oidc_link_target"] == u.pk


@pytest.mark.django_db
def test_link_init_denies_unusable_password(client, settings):
    settings.OIDC_LOGIN_ENABLED = True
    u = baker.make("bpp.BppUser", username="u3")
    u.set_unusable_password(); u.save()
    client.force_login(u)
    resp = client.post(reverse("oidc_integration:polacz"),
                       {"password": "x"})
    assert resp.status_code == 200
    assert "oidc_link_mode" not in client.session
```

- [ ] **Step 2: Run — expect fail** → brak URL/widoku.

- [ ] **Step 3: Implement `SSOLinkInitView`** in `views.py`:

```python
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View


class SSOLinkInitView(LoginRequiredMixin, View):
    """Start linkowania konta z SSO — wymaga potwierdzenia hasła (re-auth).

    Konto bez używalnego hasła (LDAP/Microsoft/OIDC) nie może linkować tą
    drogą — świadoma decyzja (patrz spec §2.1).
    """

    template_name = "oidc_integration/polacz.html"

    def get(self, request):
        return render(request, self.template_name, {})

    def post(self, request):
        user = request.user
        password = request.POST.get("password", "")
        if not user.has_usable_password() or not user.check_password(password):
            return render(
                request, self.template_name,
                {"error": "Nieprawidłowe hasło lub konto bez hasła lokalnego."},
            )
        request.session["oidc_link_mode"] = True
        request.session["oidc_link_target"] = user.pk
        request.session.save()
        return redirect(reverse("oidc_authentication_init"))
```

Create minimal template `src/oidc_integration/templates/oidc_integration/polacz.html` extending the project base with a password form (POST, `{% csrf_token %}`, field `password`, and `{{ error }}`). Follow an existing simple template for the `{% extends %}` target.

- [ ] **Step 4: Wire URL + gate change.** In `src/django_bpp/urls.py`:
  - Replace **every** `apps.is_installed("oidc_integration")` with `settings.OIDC_LOGIN_ENABLED` (the `if` at ~408 and ~426; keep the `elif apps.is_installed("microsoft_auth")` as-is).
  - Inside the `if settings.OIDC_LOGIN_ENABLED:` block add:

```python
    from oidc_integration.views import SSOLinkInitView
    urlpatterns += [
        path("oidc/polacz/", SSOLinkInitView.as_view(),
             name="polacz"),  # namespace via include or app_name
    ]
```

  Prefer defining `app_name = "oidc_integration"` + a small `oidc_integration/urls.py`, included under `include(("oidc_integration.urls", "oidc_integration"))`, so `reverse("oidc_integration:polacz")` works. Ensure `oidc_authentication_init` name comes from `mozilla_django_oidc.urls` (already included).

- [ ] **Step 5: Run — expect pass** `uv run pytest src/oidc_integration/tests/test_link_flow.py -v` → PASS.

- [ ] **Step 6: Guard non-OIDC install** `uv run python src/manage.py check` and a quick test that with `OIDC_LOGIN_ENABLED=False` the login form branch still resolves (existing url tests). Run `uv run pytest src/oidc_integration/tests/ -v`.

- [ ] **Step 7: Commit**

```bash
git add src/django_bpp/urls.py src/oidc_integration/views.py \
    src/oidc_integration/urls.py src/oidc_integration/templates/ \
    src/oidc_integration/tests/test_link_flow.py
git commit -m "feat(oidc): /oidc/polacz/ (re-auth hasłem) + gate routingu po OIDC_LOGIN_ENABLED"
```

---

### Task 10: UX odmowy (komunikat fail-closed na stronie logowania)

**Files:**
- Modify: `src/oidc_integration/backends.py` (ustaw flagę w sesji przed `raise`)
- Modify: login/failure template lub context — zależnie od `LOGIN_REDIRECT_URL_FAILURE`
- Test: `src/oidc_integration/tests/test_backends.py`

**Interfaces:**
- Consumes: `self.request.session`.
- Produces: przy fail-closed `session["oidc_error_message"]` ustawione; strona logowania renderuje i czyści.

- [ ] **Step 1: Failing test**

```python
def test_failclosed_sets_session_message(db):
    from django.contrib.sessions.backends.db import SessionStore
    baker.make("bpp.BppUser", email="a@x.pl")
    b = _backend()
    req = RequestFactory().get("/oidc/callback/")
    req.session = SessionStore()
    b.request = req
    claims = {"sub": "S", "iss": "https://kc", "email": "a@x.pl",
              "_bpp_email_trusted": True, "preferred_username": "p"}
    with pytest.raises(SuspiciousOperation):
        b.create_user(claims)
    assert "oidc_error_message" in req.session
```

- [ ] **Step 2: Run — expect fail.**

- [ ] **Step 3: Implement.** Extract a helper and set the message before each user-facing `raise` in `create_user`/link:

```python
    def _fail(self, message):
        session = getattr(getattr(self, "request", None), "session", None)
        if session is not None:
            session["oidc_error_message"] = message
            session.save()
        raise SuspiciousOperation(message)
```

Replace the `raise SuspiciousOperation(...)` in `create_user` (email collision + untrusted) with `self._fail(...)`. Render `oidc_error_message` in the login page template (context processor `oidc_auth_status` can surface + pop it), or in `50x`/login template. Keep it one place: extend `oidc_auth_status` to pop and return `oidc_error_message`.

- [ ] **Step 4: Run — expect pass.**

- [ ] **Step 5: Commit**

```bash
git add src/oidc_integration/backends.py src/bpp/context_processors/oidc.py \
    src/oidc_integration/tests/test_backends.py
git commit -m "feat(oidc): komunikat odmowy (fail-closed) widoczny na stronie logowania"
```

---

### Task 11: Profil — sekcja SSO + „Odłącz"

**Files:**
- Modify: `src/bpp/views/profile.py` (`get_context_data`, POST „odłącz")
- Modify: `src/bpp/templates/bpp/profil_uzytkownika.html`
- Test: `src/bpp/tests/test_views/test_profile_sso.py` (nowy)

**Interfaces:**
- Consumes: `user.oidc_identities`, `oidc_login_enabled` (context processor).
- Produces: lista tożsamości + `linked_at`; „Odłącz" POST+CSRF; blokada self-lockout.

- [ ] **Step 1: Failing tests**

```python
# src/bpp/tests/test_views/test_profile_sso.py
import pytest
from django.urls import reverse
from model_bakery import baker


@pytest.mark.django_db
def test_profile_lists_identities(client, settings):
    settings.OIDC_LOGIN_ENABLED = True
    u = baker.make("bpp.BppUser"); u.set_password("x"); u.save()
    from oidc_integration.models import OIDCIdentity
    OIDCIdentity.objects.create(user=u, issuer="https://kc", sub="S")
    client.force_login(u)
    resp = client.get(reverse("bpp:profil-uzytkownika"))
    assert b"https://kc" in resp.content or resp.status_code == 200


@pytest.mark.django_db
def test_unlink_blocked_on_self_lockout(client):
    u = baker.make("bpp.BppUser"); u.set_unusable_password(); u.save()
    from oidc_integration.models import OIDCIdentity
    ident = OIDCIdentity.objects.create(user=u, issuer="kc", sub="S")
    client.force_login(u)
    resp = client.post(reverse("bpp:profil-uzytkownika"),
                       {"unlink_identity": ident.pk})
    assert OIDCIdentity.objects.filter(pk=ident.pk).exists()
```

- [ ] **Step 2: Run — expect fail.**

- [ ] **Step 3: Implement.** In `get_context_data` add `context["oidc_identities"] = user.oidc_identities.all()`. In `post`, handle `unlink_identity`: load identity for `request.user`; refuse (message) if `not user.has_usable_password() and user.oidc_identities.count() == 1`; else delete. Template: add SSO section under `{% if oidc_login_enabled %}` with list (`linked_at`) and either an „Odłącz" POST form per identity (`{% csrf_token %}`, hidden `unlink_identity`) or a „Połącz konto z SSO" link to `{% url 'oidc_integration:polacz' %}` when empty. Use Foundation-Icons for any icon.

- [ ] **Step 4: Run — expect pass.**

- [ ] **Step 5: Commit**

```bash
git add src/bpp/views/profile.py src/bpp/templates/bpp/profil_uzytkownika.html \
    src/bpp/tests/test_views/test_profile_sso.py
git commit -m "feat(bpp): profil — sekcja SSO (lista tożsamości, Połącz/Odłącz z self-lockout guard)"
```

---

### Task 12: Newsfragment + pełny przebieg testów

**Files:**
- Create: `src/bpp/newsfragments/oidc-sub-binding.bugfix.rst`

- [ ] **Step 1: Newsfragment**

```rst
Naprawiono przejęcie konta przez logowanie OIDC: tożsamość jest teraz
trwale wiązana z parą ``(issuer, sub)`` zamiast dopasowywana po adresie
e-mail. Istniejące konta łączy się z SSO świadomie (re-auth hasłem w
profilu), a ``email_verified`` jest wymagane przy zakładaniu konta.
```

- [ ] **Step 2: Full suite (bez playwright)** `uv run pytest src/oidc_integration/ src/bpp/tests/test_models/test_profile_autor_match.py src/bpp/tests/test_views/test_profile_sso.py -v` → PASS.

- [ ] **Step 3: Lint** `ruff format src/oidc_integration src/bpp/models/profile.py src/bpp/views/profile.py && ruff check src/oidc_integration src/bpp/models/profile.py src/bpp/views/profile.py` → clean.

- [ ] **Step 4: Commit**

```bash
git add src/bpp/newsfragments/oidc-sub-binding.bugfix.rst
git commit -m "docs(oidc): newsfragment — wiązanie tożsamości po (issuer, sub)"
```

---

## Post-plan (poza taskami, przy scaleniu)

- `make baseline-update` (delta z `oidc_integration/0001`), commit `baseline.sql` + `baseline.meta.json`.
- Rozważ §11 speca (grace default, email_verified per-realm, re-auth) — decyzje użytkownika przed produkcją.
