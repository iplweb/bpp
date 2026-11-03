"""BPP-specific first-run wizard step: Uczelnia configuration.

Built on top of django-first-run-wizard's `SetupStep` plugin API. The
generic admin-user creation step is provided by the package; this module
adds the BPP-specific "configure the university" step that runs once an
admin exists.

Krok 3 (integracja z PBN) jest pełnoprawnym krokiem silnika
(``PbnSetupStep``), ale obsługuje go własny widok
``bpp_setup_wizard.views.PbnSetupView`` — pytanie z trzema odpowiedziami nie
mieści się w generycznym widoku formularza. Krok jest ukończony, gdy żadna
uczelnia nie ma ustawionego ``kreator_czeka_na_pbn`` — flagę zapala krok 2
przy tworzeniu uczelni, a gasi odpowiedź na pytanie o PBN (FD#499).

Trwała flaga, a nie „kreator kończy się przy pierwszym requeście spoza
/setup/": przeglądarka sama pobiera np. ``/apple-touch-icon.png`` zaraz po
wyrenderowaniu pytania, co zamykało kreator, zanim admin cokolwiek kliknął.
"""

from __future__ import annotations

from django.urls import reverse
from first_run_wizard import SetupStep

from bpp.models import Uczelnia
from bpp_setup_wizard.forms import PbnSetupForm, UczelniaSetupForm


class UczelniaSetupStep(SetupStep):
    name = "uczelnia"
    verbose_name = "Dane uczelni"
    order = 100  # after AdminUserCreationStep (order=0)
    form_class = UczelniaSetupForm
    template_name = "bpp_setup_wizard/uczelnia_setup.html"
    requires_superuser = True

    def is_complete(self) -> bool:
        return Uczelnia.objects.exists()

    def get_context(self, request) -> dict:
        return {"subtitle": "Podstawowe dane instytucji"}

    def on_complete(self, form, request):
        # Multi-hosted: form needs request to auto-link uczelnia.site to
        # the current Site via get_current_site(request). Without it the
        # uczelnia would land without a Site FK and fail the NOT NULL
        # constraint added in migration 0417.
        return form.save(request=request)

    def get_success_url(self, request) -> str:
        # Krok 3 z 3 — integracja z PBN.
        return reverse("bpp_setup_wizard:pbn")


class PbnSetupStep(SetupStep):
    name = "pbn"
    verbose_name = "Integracja z PBN"
    order = 200  # after UczelniaSetupStep
    form_class = PbnSetupForm
    template_name = "bpp_setup_wizard/pbn_setup.html"
    requires_superuser = True

    def is_complete(self) -> bool:
        # Uczelnie utworzone poza kreatorem (admin, dumpy, demo) mają flagę
        # False, więc ścieżka naprawcza middleware'u nie otworzy im kroku PBN.
        return not Uczelnia.objects.filter(kreator_czeka_na_pbn=True).exists()

    def get_url(self) -> str:
        return reverse("bpp_setup_wizard:pbn")
