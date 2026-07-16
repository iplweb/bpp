import logging
from decimal import Decimal
from urllib.parse import urlencode

import rollbar
from django.conf import settings
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import FormView

from ai_search import backends, budget, config, fx, pricing, translator
from ai_search.forms import AISearchForm
from ai_search.models import AISearchQuery
from bpp.views.zapytanie import WprowadzanieDanychOrSuperuserMixin

logger = logging.getLogger(__name__)


class ZapytanieAIView(WprowadzanieDanychOrSuperuserMixin, FormView):
    """Formularz „zapytaj po polsku" — tłumaczy pytanie na DjangoQL przez
    LLM i przekierowuje do istniejącego edytora zapytań z gotowym DSL-em."""

    template_name = "ai_search/zapytanie_ai.html"
    form_class = AISearchForm

    def get(self, request, *args, **kwargs):
        if not config.is_configured():
            return self._render_instrukcje()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not config.is_configured():
            return self._render_instrukcje()
        return super().post(request, *args, **kwargs)

    def _render_instrukcje(self):
        """Ekran instrukcji konfiguracji zamiast formularza, gdy AI nie jest
        skonfigurowane. Dostęp (login + staff/superuser) jest już wymuszony
        przez ``WprowadzanieDanychOrSuperuserMixin`` w ``dispatch()``, więc
        użytkownicy niezalogowani i bez uprawnień tu nie trafiają (dostają
        odpowiednio redirect na logowanie / 403) — instrukcję widzi tylko
        personel mogący korzystać z edytora zapytań."""
        return render(
            self.request,
            "ai_search/nieskonfigurowane.html",
            {"state": config.configuration_state()},
        )

    def form_valid(self, form):
        model_key = form.cleaned_data["model"]
        pytanie = form.cleaned_data["pytanie"].strip()
        is_anthropic = backends.active_backend_name() == "anthropic"

        if is_anthropic:
            status = budget.check_budget()
            if not status.ok:
                return self.render_to_response(
                    self.get_context_data(form=form, blad=status.reason)
                )

        try:
            result = translator.translate(
                pytanie,
                model_key,
                budget_check=budget.check_budget if is_anthropic else None,
            )
        except Exception:  # błędy SDK/sieci — log + generyczny komunikat
            rollbar.report_exc_info()
            logger.exception("Błąd tłumaczenia AI")
            return self.render_to_response(
                self.get_context_data(
                    form=form,
                    blad="Usługa AI jest chwilowo niedostępna. Spróbuj "
                    "później lub użyj „szukaj zapytaniem”.",
                )
            )

        self._log(result, model_key, pytanie)

        if result.budget_blocked:
            # Budżet wyczerpał się W TRAKCIE bounded-retry, po co najmniej
            # jednej płatnej próbie — w odróżnieniu od pre-checku wyżej
            # (tam: brak wywołania, brak logu), tu koszt już poniesiony
            # jest zalogowany przez self._log() powyżej.
            return self.render_to_response(
                self.get_context_data(form=form, blad=result.error)
            )

        if result.query:
            self.request.session["ai_search_last_question"] = pytanie
            params = urlencode({"model": model_key, "query": result.query})
            return HttpResponseRedirect(f"{reverse('bpp:zapytanie')}?{params}")

        return self.render_to_response(
            self.get_context_data(
                form=form,
                blad=result.error or "Nie udało się przetłumaczyć pytania.",
            )
        )

    def _log(self, result, model_key, pytanie):
        if backends.active_backend_name() == "anthropic":
            rate = fx.usd_to_pln_rate()
            try:
                cost_usd = pricing.cost_usd_from_usage(
                    result.usage, settings.BPP_AI_MODEL, timezone.localdate()
                )
            except KeyError:
                rollbar.report_exc_info()
                logger.error(
                    "Brak ceny dla modelu %s — koszt nieznany", settings.BPP_AI_MODEL
                )
                cost_usd = Decimal("0")
        else:
            # Backend lokalny (openai-compatible) — darmowy, brak cennika/FX.
            rate = Decimal("0")
            cost_usd = Decimal("0")
        AISearchQuery.objects.create(
            user=self.request.user if self.request.user.is_authenticated else None,
            model=settings.BPP_AI_MODEL,
            pytanie=pytanie,
            wygenerowany_query=result.query or "",
            wybrany_model_danych=model_key,
            input_tokens=result.usage.get("input_tokens", 0),
            output_tokens=result.usage.get("output_tokens", 0),
            cache_read_tokens=result.usage.get("cache_read_tokens", 0),
            cache_write_tokens=result.usage.get("cache_write_tokens", 0),
            cost_usd=cost_usd,
            fx_rate=rate,
            cost_pln=(cost_usd * rate).quantize(Decimal("0.0001")),
            success=bool(result.query),
            error=result.error,
            retried=result.retried,
        )
