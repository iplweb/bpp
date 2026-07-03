"""Centralne, generyczne widoki live-operacji dla BPP.

Standardowy liveops zakłada, że każda aplikacja rejestruje własne URL-e pod
namespace ``liveops`` (patrz ``liveops/urls.py`` — celowo puste). W BPP mamy
jednak WIELE modeli operacji, a ``get_absolute_url()`` każdej z nich robi
``reverse("liveops:live", pk=...)`` — czyli musi istnieć DOKŁADNIE JEDEN
namespace ``liveops``.

Rozwiązanie: jeden centralny zestaw widoków (mount w root urlconf pod
``^live/``), które rozwiązują konkretny model operacji po UUID — tak jak robi
to ``liveops.consumers._find_operation``. UUID jest globalnie unikalny, więc
pk jednoznacznie wskazuje model.

Widoki per-aplikacja (formularz tworzenia, filtrowana tabela wyników, detal
wiersza) zostają w swoich aplikacjach — tu trafia tylko to, co współdzielone.
"""

from __future__ import annotations

from braces.views import GroupRequiredMixin
from django.apps import apps
from django.core.exceptions import ValidationError
from django.http import Http404
from liveops.models import LiveOperation
from liveops.views import CancelView, LiveOperationView, RestartView

# Grupa wymagana do obsługi operacji live (jak w long_running). Gating przez
# braces GroupRequiredMixin — zwalnia superuserów (LIVEOPS bez REQUIRED_GROUP,
# patrz komentarz w settings).
GROUP_REQUIRED = "wprowadzanie danych"


def resolve_operation(pk, user):
    """Znajdź instancję dowolnej konkretnej podklasy ``LiveOperation`` po UUID.

    Ograniczone do ``owner=user`` (zapobiega podglądaniu cudzych operacji —
    tak jak ``RestrictToOwnerMixin`` w starym ``long_running``). Zwraca
    ``None``, gdy nic nie pasuje.
    """
    for model in apps.get_models():
        if model is LiveOperation or not issubclass(model, LiveOperation):
            continue
        try:
            return model._default_manager.get(pk=pk, owner=user)
        except model.DoesNotExist:
            continue
        except (ValueError, ValidationError):
            # pk nie jest poprawnym UUID-em dla tego backendu — pomiń.
            continue
    return None


class ResolveOperationMixin:
    """Ustawia ``self.model`` i zwraca konkretną instancję operacji po UUID.

    Nadpisuje ``get_object`` tak, by generyczny widok działał bez
    zadeklarowanego ``model`` — model wynika z odnalezionej instancji.
    """

    def get_object(self, queryset=None):
        operation = resolve_operation(self.kwargs["pk"], self.request.user)
        if operation is None:
            raise Http404("Nie znaleziono operacji.")
        self.model = type(operation)
        return operation


class BppLiveView(GroupRequiredMixin, ResolveOperationMixin, LiveOperationView):
    """Strona-host live-operacji (postęp na żywo + wynik inline)."""

    group_required = GROUP_REQUIRED


class BppCancelView(GroupRequiredMixin, ResolveOperationMixin, CancelView):
    """POST: ustaw ``cancel_requested`` i wróć na stronę operacji."""

    group_required = GROUP_REQUIRED


class BppRestartView(GroupRequiredMixin, ResolveOperationMixin, RestartView):
    """POST: restart operacji — najpierw czyścimy rekordy-dzieci.

    ``liveops.views.RestartView`` resetuje wyłącznie pola bazowe operacji;
    nie wie o rekordach potomnych. Wołamy ``reset_children()`` PRZED
    ``super().post()`` (który resetuje stan i ponownie kolejkuje).
    """

    group_required = GROUP_REQUIRED

    def post(self, request, *args, **kwargs):
        operation = self.get_object()
        operation.reset_children()
        return super().post(request, *args, **kwargs)
