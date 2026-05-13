# bpp_setup_wizard

BPP-specific step for the first-run setup wizard. Hosts the
`UczelniaSetupStep` which configures the initial `Uczelnia` (university)
record and PBN integration on a fresh BPP install.

The **wizard engine itself** (`SetupStep` base class, registry,
middleware, generic views, built-in admin-user creation step) lives in
the external package [`django-first-run-wizard`][pkg].

[pkg]: https://github.com/iplweb/django-first-run-wizard

## Architecture

| Concern | Lives in |
|---|---|
| Plugin registry, `SetupStep` ABC | `first_run_wizard` (PyPI) |
| Middleware that redirects on fresh install | `first_run_wizard.middleware.FirstRunWizardMiddleware` |
| Generic per-step `WizardStepView` + `StatusView` | `first_run_wizard.views` |
| Built-in `AdminUserCreationStep` (first superuser) | `first_run_wizard.builtin_steps` |
| **`UczelniaSetupStep`** (this app) | `bpp_setup_wizard.steps` |
| `UczelniaSetupForm` + PBN auto-config | `bpp_setup_wizard.forms` |
| BPP-branded template `uczelnia_setup.html` + CSS | `bpp_setup_wizard.templates` / `.static` |

## Flow on a fresh database

1. Anonymous request to any URL → `FirstRunWizardMiddleware` sees the
   user table is empty → redirects to `/setup/step/admin_user/`
   (built-in step from the package).
2. Admin creates the first superuser; the package's
   `AdminUserCreationStep.on_complete()` auto-logs them in.
3. Next request → middleware sees admin exists but
   `Uczelnia.objects.exists() == False` → redirects the now-logged-in
   superuser to `/setup/step/uczelnia/`.
4. Admin fills in name, dopełniacz, skrót, optionally PBN credentials,
   selects whether to use wydziały. On save:
   - `Uczelnia` row is created with the supplied data
   - PBN integration flags are flipped on by default
     (`pbn_integracja`, `pbn_api_kasuj_przed_wysylka`, etc. — see
     `forms.py:save()`)
5. Middleware sees both steps done → no more redirects; the site is live.

## Configuration in `settings.py`

```python
INSTALLED_APPS = [
    # ...
    "first_run_wizard",   # engine
    "bpp_setup_wizard",   # this app — registers UczelniaSetupStep
    # ...
]

MIDDLEWARE = [
    # ...
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "first_run_wizard.middleware.FirstRunWizardMiddleware",
    # ...
]
```

And in `urls.py`:

```python
path("setup/", include("first_run_wizard.urls", namespace="first_run_wizard")),
```

The step is auto-registered in `apps.py`'s `ready()` hook — no manual
registration call required.

## PBN integration

Auto-configured fields (always set to `True` during initial setup):

- `pbn_api_kasuj_przed_wysylka`
- `pbn_api_nie_wysylaj_prac_bez_pk`
- `pbn_api_afiliacja_zawsze_na_uczelnie`
- `pbn_wysylaj_bez_oswiadczen`
- `pbn_integracja`
- `pbn_aktualizuj_na_biezaco`

These can be later toggled in the admin. See `PBN_INTEGRACJA.md` for
the full integration workflow (registering an application in PBN,
obtaining the token, switching between testowe/produkcyjne).

## Tests

```bash
uv run pytest src/bpp_setup_wizard/tests.py
```

The package's own engine tests live in the
[`django-first-run-wizard`][pkg] repo.
