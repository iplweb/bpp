"""Mixin historii wersji (django-reversion) dla adminów BPP.

Stawiać w MRO tuż PRZED ``VersionAdmin``. Dokłada do widoków reversion:

* zapis stanu sprzed pierwszej zmiany (rekordy sprzed włączenia
  wersjonowania nie mają wersji, więc inaczej pierwszej edycji nie dałoby
  się cofnąć),
* kontrolę typu wersji i zakresu uczelni w podglądzie/przywracaniu
  wersji — reversion odwraca rewizję ZANIM ``changeform_view`` sprawdzi
  ``get_queryset``, a dla POST przekierowanie „brak obiektu" (302)
  uznałby za udany zapis, więc bez tej kontroli personel uczelni A
  mógłby cofnąć rekord uczelni B,
* odzyskiwanie usuniętych rekordów tylko dla superużytkownika (usuniętego
  rekordu nie da się przypisać do uczelni przez queryset),
* wpisy ``LogEntry`` sprzed włączenia wersjonowania na stronie „Historia"
  (reversion pokazuje wyłącznie wersje — starsza historia by zniknęła),
* akcje masowe oznaczone ``zapisuje_historie`` wykonują się BEZ rewizji
  otwieranej przez ``changelist_view`` — same zapisują wersję „przed”
  i „po” w osobnych rewizjach (w jednej rewizji stan „po” nadpisałby
  „przed”),
* zapamiętanie relacji śledzonych przez modele rejestrowane automatycznie
  (``FOLLOW_REVERSION``, do prefetchu przy hurtowym zapisie wersji).
"""

from contextlib import nullcontext

from django.contrib.admin.models import LogEntry
from django.contrib.admin.utils import unquote
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.http import Http404
from reversion.models import Version

from bpp.wersjonowanie import (
    FOLLOW_REVERSION,
    POLA_KOSZA,
    zapewnij_wersje_poczatkowa,
)


class HistoriaWersjiMixin:
    def change_view(self, request, object_id, form_url="", extra_context=None):
        if request.method == "POST":
            zapewnij_wersje_poczatkowa(self.get_object(request, unquote(object_id)))
        return super().change_view(request, object_id, form_url, extra_context)

    def revision_view(self, request, object_id, version_id, extra_context=None):
        obj = self.get_object(request, unquote(object_id))
        if obj is None:
            raise Http404("Brak takiego rekordu w zakresie Twojej uczelni.")
        # Soft-delete: przywrócenie wersji zapisuje CAŁY obiekt z wersji
        # (``DeserializedObject.save()``), więc pola kosza wracają do
        # wartości domyślnych i rekord po cichu wychodzi z kosza — z
        # pominięciem ``restore()`` (guard, SoftDeleteLog, kolejka PBN).
        # Najpierw przywróć z kosza, potem cofaj wersje.
        if getattr(obj, "deleted_at", None) is not None:
            raise PermissionDenied(
                "Rekord jest w koszu — najpierw przywróć go z kosza, "
                "potem przywracaj wcześniejsze wersje."
            )
        # reversion szuka wersji po pk i object_id, ale NIE po typie modelu —
        # bez tego przez URL autora dałoby się cofnąć rewizję innego modelu
        # (np. uczelni) o tym samym numerze ID.
        if (
            not Version.objects.get_for_model(self.model)
            .filter(pk=version_id, object_id=unquote(object_id))
            .exists()
        ):
            raise Http404("Brak takiej wersji tego rekordu.")
        return super().revision_view(request, object_id, version_id, extra_context)

    def recoverlist_view(self, request, extra_context=None):
        if not request.user.is_superuser:
            raise PermissionDenied
        return super().recoverlist_view(request, extra_context)

    def recover_view(self, request, version_id, extra_context=None):
        if not request.user.is_superuser:
            raise PermissionDenied
        return super().recover_view(request, version_id, extra_context)

    def history_view(self, request, object_id, extra_context=None):
        context = {
            "historia_sprzed_wersjonowania": self._historia_sprzed_wersjonowania(
                unquote(object_id)
            )
        }
        context.update(extra_context or {})
        return super().history_view(request, object_id, context)

    def _historia_sprzed_wersjonowania(self, object_id):
        """``LogEntry`` starsze niż najstarsza wersja (albo wszystkie, gdy
        rekord nie ma jeszcze wersji). Nowsze zmiany są już w wersjach —
        pokazanie ich drugi raz dublowałoby wpisy."""
        wpisy = LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(self.model),
            object_id=str(object_id),
        ).select_related("user")
        najstarsza = (
            Version.objects.get_for_object_reference(self.model, object_id)
            .order_by("revision__date_created")
            .values_list("revision__date_created", flat=True)
            .first()
        )
        if najstarsza is not None:
            wpisy = wpisy.filter(action_time__lt=najstarsza)
        return list(wpisy.order_by("-action_time"))

    def reversion_register(self, model, **kwargs):
        FOLLOW_REVERSION.setdefault(model, tuple(kwargs.get("follow", ())))
        if hasattr(model, "deleted_objects"):
            # Pola kosza nie wchodzą do wersji (patrz ``POLA_KOSZA``).
            kwargs["exclude"] = (*kwargs.get("exclude", ()), *POLA_KOSZA)
        super().reversion_register(model, **kwargs)

    def create_revision(self, request):
        if self._akcja_zapisuje_historie(request):
            return nullcontext()
        return super().create_revision(request)

    def _akcja_zapisuje_historie(self, request):
        """Czy ``request`` to POST listy rekordów uruchamiający akcję
        oznaczoną ``zapisuje_historie`` (patrz ``bpp.admin.actions``)."""
        if request.method != "POST" or "action" not in request.POST:
            return False
        dopasowanie = getattr(request, "resolver_match", None)
        opts = self.model._meta
        lista = f"{opts.app_label}_{opts.model_name}_changelist"
        if dopasowanie is None or dopasowanie.url_name != lista:
            return False
        # Jak ``ModelAdmin.response_action``: przy kilku formularzach akcji
        # na stronie ``index`` wskazuje, który wysłano.
        try:
            nazwa = request.POST.getlist("action")[int(request.POST.get("index", 0))]
        except (ValueError, IndexError):
            return False  # niepoprawny POST — ``response_action`` go odrzuci
        akcja = self.get_actions(request).get(nazwa)
        return akcja is not None and getattr(akcja[0], "zapisuje_historie", False)
