# bpp_setup_wizard

BPP-specific steps for the first-run setup wizard. Two paths, chosen in
step 2:

| # | Ścieżka „Tak” (dane demo) | Ścieżka „Nie” (własna uczelnia) |
|---|---|---|
| 1 | Konto administratora | Konto administratora |
| 2 | Dane demonstracyjne: „Tak” + wybór motywu | Dane demonstracyjne: „Nie” |
| 3 | Generowanie danych (postęp na żywo) → BPP | Dane uczelni |
| 4 | — | Integracja z PBN (można pominąć) → BPP |

1. Konto administratora — `AdminUserCreationStep` z pakietu (BPP-styled
   template override).
2. Dane demonstracyjne — `DaneDemoSetupStep`, obsługiwany przez
   `DaneDemoView` pod `/setup/step/dane_demo/`.
3. Dane uczelni — `UczelniaSetupStep` (nazwa, dopełniacz, skrót,
   wydziały). Bez pól PBN.
4. Integracja z PBN — `PbnSetupStep`, obsługiwany przez `PbnSetupView`
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
| **`DaneDemoSetupStep`**, **`UczelniaSetupStep`**, **`PbnSetupStep`** (this app) | `bpp_setup_wizard.steps` |
| **`DaneDemoView`**, `DaneDemoPostepView` (JSON), `DaneDemoForm` | `bpp_setup_wizard.views` / `.forms` |
| Generowanie danych demo w tle, postęp, blokada podwójnego startu | `bpp_setup_wizard.dane_demo`, modele `GenerowanieDanychDemo` (liveops) i `KreatorDanychDemo` |
| Pasek „Krok N z M” zależny od ścieżki | `{% postep_kreatora %}` w `bpp_setup_wizard.templatetags` |
| `UczelniaSetupForm` + PBN auto-config | `bpp_setup_wizard.forms` |
| **`PbnSetupView`** + `PbnSetupForm` (krok „Integracja z PBN”) | `bpp_setup_wizard.views` / `.forms` |
| BPP-branded template `uczelnia_setup.html` + CSS | `bpp_setup_wizard.templates` / `.static` |

## Flow on a fresh database

1. Anonymous request to any URL → `FirstRunWizardMiddleware` sees the
   user table is empty → redirects to `/setup/step/admin_user/`
   (built-in step from the package).
2. Admin creates the first superuser; the package's
   `AdminUserCreationStep.on_complete()` auto-logs them in.
3. Next request → middleware sees admin exists but no `Uczelnia`, no
   answer about demo data and no demo generation → redirects the
   now-logged-in superuser to `/setup/step/dane_demo/` (`DaneDemoView`):
   „Utworzyć dane demo?” with a warning that the data is fictional.
   - **„Nie”** (POST `akcja=nie`) stores `KreatorDanychDemo.odpowiedz="nie"`
     → the middleware redirects to `/setup/step/uczelnia/` (point 4).
   - **„Tak”** (`?odpowiedz=tak`) shows every theme of
     `create_demo_data --motyw` (`THEMES`) with a short description
     (`dane_demo.OPISY_MOTYWOW`). POST `akcja=generuj` →
     `dane_demo.rozpocznij_generowanie()` (see „Dane demo” below) and the
     same URL now shows the progress page. When the generation finishes,
     the generator has created its own `Uczelnia` (with
     `kreator_czeka_na_pbn=False`), so „Dane uczelni” and „Integracja
     z PBN” are already complete, the middleware stamps
     `FirstRunWizardState.completed_at` and the admin lands in BPP.
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

`bpp_setup_wizard.urls` is included at `setup/step/` *before* the
engine's `include`, so `PbnSetupView` (`pbn/`) and `DaneDemoView`
(`dane_demo/`, plus `dane_demo/postep/`) shadow the generic
`WizardStepView` for those steps (questions with several answers and a
progress page do not fit a plain form view).

## Dane demo

`DaneDemoSetupStep.is_complete()`:

- generation queued/running → **no** (the step URL shows progress),
- generation finished OK, or failed and the admin acknowledged it → yes,
- failed and the partial data was removed → back to the question,
- failed and data stayed in the database → **no** (error page with the
  `cleanup_demo_data --manifest …` command and „Przejdź dalej”),
- answer „nie” → yes,
- otherwise: `Uczelnia.objects.exists()`. An uczelnia created outside the
  wizard — demo data generated from the console by bpp-wsl / bpp-vm
  (`bpp-ctl init --demo <motyw>`, `bpp-ctl demo`), a restored dump, an
  existing install — closes the step without asking, so demo data is
  never offered twice.

Safety (the console needs `--yes-i-am-sure --confirm-db <baza>`; the
wizard replaces that with):

- `rozpocznij_generowanie()` runs under `select_for_update` on the
  `KreatorDanychDemo` singleton: if a generation is already queued or
  running it returns it (double click, reload, second tab → one
  operation); it refuses (`GenerowanieNiedozwolone`) when the wizard is
  completed or the database is not empty (`Uczelnia`, `Autor`,
  `Wydawnictwo_Ciagle`, `Wydawnictwo_Zwarte`). The operation is enqueued
  on commit.
- The worker (`generuj_dane_demo`) claims the operation with a
  conditional `UPDATE … SET przejete=True` (a redelivered Celery task does
  not generate a second set) and checks the empty database again.
- Scale as in the bpp-wsl/bpp-vm installers (`PARAMETRY_GENERATORA`:
  200 authors, 1000 + 500 works), names prefixed with „Demo — ”, then
  `denorm_flush`. On error it runs `run_cleanup` with the manifest and
  records whether the database is empty again (`dane_usuniete`).

Progress: `GenerowanieDanychDemo` is a `django-liveops` operation (Celery
runner in production, eager in tests). `bpp.demo_data.progress` lets a
caller observe every `make_progress` bar (`obserwuj_postep`);
`dane_demo.RaportPostepu` maps bar names to weighted stages
(`ETAPY_GENERATORA`) and writes `percent` / `status_text` /
`postep_zaktualizowano` to the operation at most once a second. The
progress page polls `DaneDemoPostepView` (`/setup/step/dane_demo/postep/`,
JSON, superuser only) every 2 s — no WebSockets needed — and goes to `/`
on success or reloads the step on error. No progress for 30 minutes →
the page warns that the Celery worker may be down. Operations are visible
read-only in the Django admin.

Browser-initiated icon requests are also listed in
`FIRST_RUN_WIZARD_SKIP_PREFIXES` (`settings/base.py`), so they are
neither redirected to the wizard nor used to stamp completion.

## Configuration in `settings.py`

```python
INSTALLED_APPS = [
    # ...
    "first_run_wizard",  # engine
    "bpp_setup_wizard",  # this app — registers dane demo, Uczelnia, PBN steps
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
        "setup/step/",
        include("bpp_setup_wizard.urls", namespace="bpp_setup_wizard"),
    ),
    path("setup/", include("first_run_wizard.urls", namespace="first_run_wizard")),
)
```

The steps are auto-registered in `apps.py`'s `ready()` hook — no manual
registration call required.

## PBN integration

Auto-configured fields (always set to `True` during initial setup):

- `pbn_kasuj_dyscypliny_selektywnie`
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
uv run pytest src/bpp_setup_wizard/
```

The package's own engine tests live in the
[`django-first-run-wizard`][pkg] repo.
