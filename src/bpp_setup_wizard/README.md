# bpp_setup_wizard

BPP-specific steps for the first-run setup wizard (3 kroki, FD#499):

1. Konto administratora — `AdminUserCreationStep` z pakietu (BPP-styled
   template override).
2. Dane uczelni — `UczelniaSetupStep` (nazwa, dopełniacz, skrót,
   wydziały). Bez pól PBN.
3. Integracja z PBN — `PbnSetupStep`, obsługiwany przez `PbnSetupView`
   pod `/setup/step/pbn/`. Można go pominąć.

The **wizard engine itself** (`SetupStep` base class, registry,
middleware, generic views, built-in admin-user creation step) lives in
the external package [`django-first-run-wizard`][pkg].

[pkg]: https://github.com/iplweb/django-first-run-wizard

## Architecture

| Concern | Lives in |
|---|---|
| Plugin registry, `SetupStep` ABC | `first_run_wizard` (PyPI) |
| Middleware that redirects on fresh install | `first_run_wizard.middleware.FirstRunWizardMiddleware`, subclassed as `bpp_setup_wizard.middleware.BppFirstRunWizardMiddleware` |
| Generic per-step `WizardStepView` + `StatusView` | `first_run_wizard.views` |
| Built-in `AdminUserCreationStep` (first superuser) | `first_run_wizard.builtin_steps` |
| **`UczelniaSetupStep`**, **`PbnSetupStep`** (this app) | `bpp_setup_wizard.steps` |
| `UczelniaSetupForm` + PBN auto-config | `bpp_setup_wizard.forms` |
| **`PbnSetupView`** + `PbnSetupForm` (krok 3) | `bpp_setup_wizard.views` / `.forms` |
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
4. Admin fills in name, dopełniacz, skrót and selects whether to use
   wydziały. On save:
   - `Uczelnia` row is created with the supplied data
   - PBN integration flags are flipped on by default
     (`pbn_integracja`, `pbn_kasuj_dyscypliny_selektywnie`, etc. — see
     `forms.py:save()`)
   - `Uczelnia.kreator_czeka_na_pbn` is set to `True`
   - `UczelniaSetupStep.get_success_url()` redirects to `/setup/step/pbn/`.
5. `/setup/step/pbn/` (`PbnSetupView`) asks „Czy masz już nazwę i token
   aplikacji z PBN?" (`?odpowiedz=tak|pozniej|nie-wiem`). Only „Tak"
   shows the PBN form; the other two answers explain where to fill the
   data later (Administracja → Uczelnia) and let the admin skip.
   Every path clears `kreator_czeka_na_pbn` and stamps
   `FirstRunWizardState.completed_at` — the wizard, including the PBN
   step, never comes back.

`PbnSetupStep.is_complete()` is "no `Uczelnia` has
`kreator_czeka_na_pbn=True`". The flag is persisted on purpose: an
earlier version closed the wizard on the first non-`/setup/` request,
and browsers fetch `/apple-touch-icon.png` / `/favicon.ico` on their own
right after rendering the PBN question — the step was gone before the
admin could click anything. Uczelnie created outside the wizard (admin,
dumps, demo data, pre-migration rows) default to `False`, so the
middleware's repair path never sends existing installs back into the
PBN step. If the admin leaves before answering, the middleware keeps
redirecting them to the PBN step until they answer.

`PbnSetupView` is routed at `setup/step/pbn/` *before* the engine's
`include`, so it shadows the generic `WizardStepView` for that step
(the question with three answers does not fit a plain form view).

Browser-initiated icon requests are also listed in
`FIRST_RUN_WIZARD_SKIP_PREFIXES` (`settings/base.py`), so they are
neither redirected to the wizard nor used to stamp completion.

## Configuration in `settings.py`

```python
INSTALLED_APPS = [
    # ...
    "first_run_wizard",  # engine
    "bpp_setup_wizard",  # this app — registers Uczelnia + PBN steps
    # ...
]

MIDDLEWARE = [
    # ...
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "bpp_setup_wizard.middleware.BppFirstRunWizardMiddleware",
    # ...
]
```

And in `urls.py`:

```python
(
    path(
        "setup/step/pbn/",
        include("bpp_setup_wizard.urls", namespace="bpp_setup_wizard"),
    ),
    path("setup/", include("first_run_wizard.urls", namespace="first_run_wizard")),
)
```

The steps are auto-registered in `apps.py`'s `ready()` hook — no manual
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
