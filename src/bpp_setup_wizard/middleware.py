"""Middleware kreatora pierwszego uruchomienia w wersji BPP.

Silnik (``first_run_wizard``) przekierowuje do kolejnego kroku tylko wtedy,
gdy bieżący request ma do niego dostęp. Kroki „Dane uczelni" i „Integracja
z PBN" wymagają superusera, więc anonim (np. z nieważną sesją po resecie
bazy) albo zwykły użytkownik dostawał niedokonfigurowaną stronę główną.

BPP: dopóki kreator nie jest skończony (admin + uczelnia + odpowiedź o PBN),
nikt nie widzi strony — kto nie ma dostępu do kolejnego kroku, trafia na
logowanie admina, a po zalogowaniu z powrotem do kreatora.
"""

from __future__ import annotations

from django.contrib.auth.views import redirect_to_login
from django.urls import reverse
from first_run_wizard.middleware import FirstRunWizardMiddleware
from first_run_wizard.registry import registry


class BppFirstRunWizardMiddleware(FirstRunWizardMiddleware):
    def _maybe_redirect(self, request):
        response = super()._maybe_redirect(request)
        if response is not None or self._setup_complete:
            return response

        if registry.inspect(request).next_step is not None:
            # Request jest już na stronie kolejnego dostępnego kroku.
            return None

        # Kreator niedokończony, a bieżący użytkownik nie ma dostępu do
        # żadnego z pozostałych kroków — logowanie admina (pod /admin/, więc
        # pomijane przez middleware) z powrotem na pierwszy niedokończony krok.
        for step in registry.all_steps():
            if not step.is_complete():
                return redirect_to_login(
                    step.get_url(), login_url=reverse("admin:login")
                )
        return None
