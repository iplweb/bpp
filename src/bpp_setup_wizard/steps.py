"""BPP-specific first-run wizard step: Uczelnia + PBN configuration.

Built on top of django-first-run-wizard's `SetupStep` plugin API. The
generic admin-user creation step is provided by the package; this module
adds the BPP-specific "configure the university" step that runs once an
admin exists.
"""

from __future__ import annotations

from first_run_wizard import SetupStep

from bpp.models import Uczelnia
from bpp_setup_wizard.forms import UczelniaSetupForm


class UczelniaSetupStep(SetupStep):
    name = "uczelnia"
    verbose_name = "Konfiguracja uczelni"
    order = 100  # after AdminUserCreationStep (order=0)
    form_class = UczelniaSetupForm
    template_name = "bpp_setup_wizard/uczelnia_setup.html"
    requires_superuser = True

    def is_complete(self) -> bool:
        return Uczelnia.objects.exists()

    def get_context(self, request) -> dict:
        return {"subtitle": "Podstawowe dane instytucji"}
