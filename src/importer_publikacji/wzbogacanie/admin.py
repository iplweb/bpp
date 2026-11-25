"""Widok „Wzbogać z CrossRef / PBN” w module redagowania (FD#517, FD#518)."""

from django.contrib import messages
from django.contrib.admin.utils import quote, unquote
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, reverse
from django.utils.http import urlencode

from bpp.wersjonowanie import zmiana_rekordu

from . import zrodla
from .autorzy import porownaj_autorow
from .pola import porownaj, zastosuj


def komentarz_historii(dane, przeniesione):
    """Opis zmiany do historii rekordu: skąd i które pola."""
    pola = ", ".join(dict.fromkeys(w.etykieta for w in przeniesione))
    if dane.zrodlo == zrodla.PBN and dane.wczesniejsza_wersja:
        # FD#518: odtworzenie danych ze starszej wersji w PBN.
        return f"Odtworzono z PBN, wersja z dnia {dane.wersja.data_tekst}: pola {pola}"
    if dane.zrodlo == zrodla.PBN:
        return f"Wzbogacono z PBN (wersja {dane.wersja.opis}): pola {pola}"
    return f"Wzbogacono z {dane.nazwa}: pola {pola}"


class WzbogacanieRekorduAdminMixin:
    """Dodaje do admina publikacji widok porównania rekordu ze źródłem
    zewnętrznym i przenoszenia wybranych pól."""

    wzbogacanie_template = "admin/wzbogacanie/porownanie.html"

    def get_urls(self):
        opts = self.model._meta
        return [
            path(
                "<path:object_id>/wzbogac/<str:zrodlo>/",
                self.admin_site.admin_view(self.wzbogac_view),
                name=f"{opts.app_label}_{opts.model_name}_wzbogac",
            ),
            *super().get_urls(),
        ]

    def _wzbogac_url(self, obj, zrodlo, **parametry):
        opts = self.model._meta
        url = reverse(
            f"admin:{opts.app_label}_{opts.model_name}_wzbogac",
            args=(quote(obj.pk), zrodlo),
        )
        parametry = {k: v for k, v in parametry.items() if v}
        return f"{url}?{urlencode(parametry)}" if parametry else url

    def _pobierz_dane_zrodla(self, request, obj, zrodlo, wersja, odswiez):
        from bpp.models import Uczelnia

        if zrodlo == zrodla.CROSSREF:
            return zrodla.pobierz_z_crossref(obj)
        return zrodla.pobierz_z_pbn(
            obj,
            Uczelnia.objects.get_for_request(request),
            wersja=wersja,
            odswiez=odswiez,
        )

    def wzbogac_view(self, request, object_id, zrodlo):
        if zrodlo not in zrodla.NAZWY_ZRODEL:
            raise Http404("Nieznane źródło danych.")
        obj = self.get_object(request, unquote(object_id))
        if obj is None:
            raise Http404("Brak takiego rekordu w zakresie Twojej uczelni.")
        if not self.has_change_permission(request, obj):
            raise PermissionDenied
        if getattr(obj, "deleted_at", None) is not None:
            raise Http404("Rekord jest w koszu — najpierw przywróć go z kosza.")

        wersja = request.POST.get("wersja") or request.GET.get("wersja") or ""
        if request.method == "POST":
            return self._wzbogac_zastosuj(request, obj, zrodlo, wersja)

        dane = self._pobierz_dane_zrodla(request, obj, zrodlo, wersja, odswiez=True)
        return self._wzbogac_pokaz(request, obj, dane)

    def _wzbogac_zastosuj(self, request, obj, zrodlo, wersja):
        # Bez ponownego łączenia z PBN: stosujemy dane, które były na
        # podglądzie (lokalna kopia PBN; CrossRef ma własną pamięć podręczną).
        dane = self._pobierz_dane_zrodla(request, obj, zrodlo, wersja, odswiez=False)
        powrot = HttpResponseRedirect(self._wzbogac_url(obj, zrodlo, wersja=wersja))
        if dane.publikacja is None:
            messages.error(request, dane.blad)
            return powrot
        wybrane = request.POST.getlist("pole")
        if not wybrane:
            messages.warning(
                request, "Nie zaznaczono żadnego pola — nic nie zmieniono."
            )
            return powrot

        wiersze = porownaj(obj, dane.publikacja)
        with (
            transaction.atomic(),
            zmiana_rekordu(request.user, obj, "") as zmiana,
        ):
            przeniesione, pominiete = zastosuj(obj, wiersze, wybrane)
            if przeniesione:
                zmiana.komentarz = komentarz_historii(dane, przeniesione)
            else:
                zmiana.pomin = True

        if przeniesione:
            messages.success(
                request, f"{zmiana.komentarz}. Zmiana jest w historii rekordu."
            )
        if pominiete:
            messages.warning(
                request,
                "Nie przeniesiono (dane w źródle albo w rekordzie zmieniły się od "
                "podglądu — sprawdź porównanie ponownie): "
                + ", ".join(dict.fromkeys(w.etykieta for w in pominiete))
                + ".",
            )
        return powrot

    def _wzbogac_pokaz(self, request, obj, dane):
        opts = self.model._meta
        nazwa = f"admin:{opts.app_label}_{opts.model_name}"
        wiersze = porownaj(obj, dane.publikacja) if dane.publikacja else []
        rozne = [w for w in wiersze if w.rozni_sie]
        identyfikator_wersji = dane.wersja.identyfikator if dane.wersja else ""
        context = {
            **self.admin_site.each_context(request),
            "opts": opts,
            "app_label": opts.app_label,
            "title": f"Wzbogać z {dane.nazwa}: {obj}",
            "original": obj,
            "dane": dane,
            "wiersze": wiersze,
            "rozne": rozne,
            "do_przeniesienia": [w for w in wiersze if w.mozna_przeniesc],
            "tylko_w_bpp": [w for w in wiersze if w.status == "brak_w_zrodle"],
            "autorzy": (
                porownaj_autorow(obj, dane.publikacja.authors)
                if dane.publikacja
                else None
            ),
            "zakladki": [
                (
                    zrodla.NAZWY_ZRODEL[z],
                    self._wzbogac_url(obj, z),
                    z == dane.zrodlo,
                )
                for z in (zrodla.CROSSREF, zrodla.PBN)
            ],
            "wersje": [
                (
                    w,
                    self._wzbogac_url(obj, zrodla.PBN, wersja=w.identyfikator),
                    w is dane.wersja,
                )
                for w in dane.wersje
            ],
            "identyfikator_wersji": identyfikator_wersji,
            "changelist_url": reverse(f"{nazwa}_changelist"),
            "change_url": reverse(f"{nazwa}_change", args=(quote(obj.pk),)),
            "history_url": reverse(f"{nazwa}_history", args=(quote(obj.pk),)),
        }
        return render(request, self.wzbogacanie_template, context)
