"""Strony operacji „Uzgodnij z PBN” (FD#477)."""

import logging

from django.contrib import messages
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView
from kombu.exceptions import OperationalError

from bpp import const
from bpp.models import Uczelnia
from pbn_downloader_app.views import group_required

from .forms import StartForm
from .models import UzgodnienieZPBN
from .raport import opis_roznic, pogrupuj, zbuduj_xlsx
from .silnik import ZGODNE, ZMIENIAJACE
from .tasks import uzgodnij_z_pbn

logger = logging.getLogger(__name__)

wymaga_uprawnien = method_decorator(
    group_required(const.GR_WPROWADZANIE_DANYCH), name="dispatch"
)


class _UczelniaMixin:
    """Wszystko dzieje się w obrębie uczelni z żądania (multi-hosted)."""

    def uczelnia(self):
        uczelnia = Uczelnia.objects.get_for_request(self.request)
        if uczelnia is None:
            raise Http404("Nie ustalono uczelni dla tego adresu.")
        return uczelnia

    def przebiegi(self):
        return UzgodnienieZPBN.objects.filter(uczelnia=self.uczelnia())

    def przebieg(self):
        # Cudzy przebieg (innej uczelni) = 404, nie 403 — nie zdradzamy istnienia.
        return get_object_or_404(self.przebiegi(), pk=self.kwargs["pk"])


def _powod_blokady(uczelnia, user):
    """Dlaczego nie da się teraz uruchomić uzgadniania (albo ``None``)."""
    if not uczelnia.pbn_integracja or not uczelnia.pbn_uid_id:
        return (
            "Uczelnia nie ma włączonej integracji z PBN albo nie ma ustawionego "
            "identyfikatora instytucji w PBN."
        )
    pbn_user = user.get_pbn_user()
    if not pbn_user.pbn_token:
        return "Nie jesteś zalogowany w PBN — najpierw wybierz „autoryzuj PBN API”."
    if not pbn_user.pbn_token_possibly_valid():
        return "Twoja autoryzacja w PBN wygasła — wybierz „autoryzuj PBN API”."
    return None


def _uruchom(request, uczelnia, **pola):
    """Tworzy przebieg i zleca zadanie w tle. Zwraca przebieg albo ``None``."""
    UzgodnienieZPBN.oznacz_przerwane(uczelnia)
    try:
        with transaction.atomic():
            przebieg = UzgodnienieZPBN.objects.create(
                uczelnia=uczelnia, user=request.user, **pola
            )
    except IntegrityError:
        # Constraint „jeden aktywny przebieg na uczelnię”.
        messages.error(
            request,
            "Uzgadnianie z PBN dla tej uczelni już trwa — poczekaj na jego "
            "zakończenie albo je anuluj.",
        )
        return None

    def zlec():
        try:
            uzgodnij_z_pbn.delay(przebieg.pk)
        except (OperationalError, RuntimeError):
            logger.exception("Nie udało się zlecić uzgodnienia z PBN #%s", przebieg.pk)
            przebieg.status = UzgodnienieZPBN.Status.BLAD
            przebieg.blad = "Nie udało się uruchomić zadania w tle."
            przebieg.zakonczono = timezone.now()
            przebieg.save()

    transaction.on_commit(zlec)
    return przebieg


@wymaga_uprawnien
class StronaGlownaView(_UczelniaMixin, TemplateView):
    template_name = "pbn_uzgadnianie/main.html"

    def get_context_data(self, **kwargs):
        kontekst = super().get_context_data(**kwargs)
        uczelnia = self.uczelnia()
        rok = timezone.now().year
        kontekst.update(
            form=StartForm(initial={"rok_od": rok, "rok_do": rok}),
            przebiegi=self.przebiegi().select_related("user")[:20],
            aktywny=self.przebiegi().filter(status__in=UzgodnienieZPBN.AKTYWNE).first(),
            powod_blokady=_powod_blokady(uczelnia, self.request.user),
        )
        return kontekst


@wymaga_uprawnien
class StartView(_UczelniaMixin, View):
    def post(self, request):
        uczelnia = self.uczelnia()
        powod = _powod_blokady(uczelnia, request.user)
        if powod:
            messages.error(request, powod)
            return redirect("pbn_uzgadnianie:main")

        form = StartForm(request.POST)
        if not form.is_valid():
            for blad in form.non_field_errors():
                messages.error(request, blad)
            for pole, bledy in form.errors.items():
                if pole != "__all__":
                    messages.error(request, f"{form[pole].label}: {'; '.join(bledy)}")
            return redirect("pbn_uzgadnianie:main")

        przebieg = _uruchom(request, uczelnia, **form.cleaned_data)
        if przebieg is None:
            return redirect("pbn_uzgadnianie:main")
        return redirect("pbn_uzgadnianie:szczegoly", pk=przebieg.pk)


def _link_do_rekordu(wpis):
    model, pk = wpis.get("bpp_model"), wpis.get("bpp_pk")
    if not model or not pk:
        return None
    try:
        return reverse(f"admin:bpp_{model}_change", args=[pk])
    except NoReverseMatch:
        return None


@wymaga_uprawnien
class SzczegolyView(_UczelniaMixin, TemplateView):
    template_name = "pbn_uzgadnianie/szczegoly.html"

    def get_context_data(self, **kwargs):
        kontekst = super().get_context_data(**kwargs)
        przebieg = self.przebieg()
        uczelnia = przebieg.uczelnia
        grupy = []
        for kod, etykieta, wpisy in pogrupuj(przebieg.wynik or []):
            for wpis in wpisy:
                wpis["bpp_url"] = _link_do_rekordu(wpis)
                wpis["roznice_opis"] = opis_roznic(wpis)
                if wpis.get("pbn_uid"):
                    wpis["pbn_url"] = const.LINK_PBN_DO_PUBLIKACJI.format(
                        pbn_api_root=uczelnia.pbn_api_root,
                        pbn_uid_id=wpis["pbn_uid"],
                    )
            grupy.append(
                {
                    "kod": kod,
                    "etykieta": etykieta,
                    "wpisy": wpisy,
                    "zwinieta": kod == ZGODNE,
                    "zmienia": kod in ZMIENIAJACE,
                }
            )
        kontekst.update(
            przebieg=przebieg,
            grupy=grupy,
            mozna_wykonac=(
                przebieg.to_podglad
                and przebieg.status == UzgodnienieZPBN.Status.ZAKONCZONE
            ),
            ile_zmian=sum(
                (przebieg.podsumowanie or {}).get(kod, 0) for kod in ZMIENIAJACE
            ),
        )
        return kontekst


@wymaga_uprawnien
class StanView(_UczelniaMixin, View):
    def get(self, request, pk):
        przebieg = self.przebieg()
        return JsonResponse(
            {
                "status": przebieg.status,
                "status_opis": przebieg.get_status_display(),
                "aktywne": przebieg.aktywne,
                "etap": przebieg.etap,
                "postep": przebieg.postep,
            }
        )


@wymaga_uprawnien
class AnulujView(_UczelniaMixin, View):
    def post(self, request, pk):
        przebieg = self.przebieg()
        zmieniono = (
            self.przebiegi()
            .filter(pk=przebieg.pk, status__in=UzgodnienieZPBN.AKTYWNE)
            .update(anuluj=True)
        )
        if zmieniono:
            messages.info(
                request,
                "Zlecono anulowanie — przebieg zatrzyma się po bieżącej pracy.",
            )
        return redirect("pbn_uzgadnianie:szczegoly", pk=przebieg.pk)


@wymaga_uprawnien
class WykonajPodgladView(_UczelniaMixin, View):
    """Wykonanie dokładnie tego, co pokazał zakończony podgląd."""

    def post(self, request, pk):
        podglad = self.przebieg()
        if (
            not podglad.to_podglad
            or podglad.status != UzgodnienieZPBN.Status.ZAKONCZONE
        ):
            messages.error(request, "Wykonać można tylko zakończony podgląd.")
            return redirect("pbn_uzgadnianie:szczegoly", pk=podglad.pk)
        powod = _powod_blokady(podglad.uczelnia, request.user)
        if powod:
            messages.error(request, powod)
            return redirect("pbn_uzgadnianie:szczegoly", pk=podglad.pk)

        przebieg = _uruchom(
            request,
            podglad.uczelnia,
            rok_od=podglad.rok_od,
            rok_do=podglad.rok_do,
            tryb=UzgodnienieZPBN.Tryb.WYKONANIE,
            na_podstawie=podglad,
        )
        if przebieg is None:
            return redirect("pbn_uzgadnianie:szczegoly", pk=podglad.pk)
        return redirect("pbn_uzgadnianie:szczegoly", pk=przebieg.pk)


@wymaga_uprawnien
class RaportXlsxView(_UczelniaMixin, View):
    def get(self, request, pk):
        przebieg = self.przebieg()
        odpowiedz = HttpResponse(
            zbuduj_xlsx(przebieg),
            content_type="application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet",
        )
        odpowiedz["Content-Disposition"] = (
            f'attachment; filename="uzgodnienie-z-pbn-{przebieg.rok_od}-'
            f'{przebieg.rok_do}-{przebieg.pk}.xlsx"'
        )
        return odpowiedz
