"""Konfigurator wyglądu: administrator wybiera kolory, czcionkę, styl menu
i przycisków, ogląda podgląd na prawdziwych stronach BPP i klika „Zastosuj”.

Podgląd kompiluje przeglądarka (``motyw-kompilator-worker.js``), a przy
„Zastosuj” ten sam kod JS uruchamia serwer (``bpp.motyw_kompilator``, V8)
i zapisuje wynik (``MotywWlasny``). Strony otwierane
w ramkach podglądu z ``?podglad_motywu=1`` mają zamiast motywu pusty
``<style>``, który wypełnia konfigurator (``bare.html``).

Ten sam konfig można też pobrać jako plik i wkompilować w obraz
(``src/bpp/static/scss/motywy/<nazwa>.json``, task Grunta ``motywy``).
"""

import base64
import binascii
import io
import json
import logging
import re

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import NoReverseMatch, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.timezone import localtime, now
from django.views.decorators.http import require_POST

from bpp import przymiarka_motywu as przymiarka
from bpp.models import (
    MOTYW_WLASNY,
    MotywWersja,
    MotywWlasny,
    MotywZapisany,
    Rekord,
)
from bpp.motyw_kompilator import (
    BRAK_KOMPILATORA,
    KOLEJKA,
    kompilator_dostepny,
    skompiluj,
    wstepna_walidacja,
)
from bpp.util.pliki_uczelni import MAKS_ROZMIAR_FAVICON, waliduj_favicon
from django_bpp.version import VERSION


def _adres(nazwa, *args):
    try:
        return reverse(nazwa, args=args)
    except NoReverseMatch:
        return None


def _podglady():
    """Strony do podglądu: (tytuł, adres, urządzenie)."""
    # Najnowsza publikacja z autorami — jej pierwszy autor i jednostka dają
    # strony z prawdziwą treścią, a nie puste profile.
    rekord = Rekord.objects.filter(autorzy__isnull=False).order_by("-rok").first()
    autor = jednostka = None
    if rekord is not None:
        wpis = rekord.autorzy.select_related("autor", "jednostka").first()
        autor, jednostka = wpis.autor, wpis.jednostka
    if jednostka is not None and not jednostka.widoczna:
        jednostka = None
    # Adres docelowy od razu — przekierowania z /rekord/<ct>,<id>/ gubią
    # parametr ?podglad_motywu.
    adres_rekordu = None
    if rekord is not None:
        adres_rekordu = (
            reverse("bpp:browse_praca_by_slug", args=(rekord.slug,))
            if rekord.slug
            else rekord.get_absolute_url()
        )

    strony = [
        ("Strona główna", "/", "komputer"),
        ("Wyszukiwarka", _adres("multiseek:index"), "komputer"),
        ("Autorzy", _adres("bpp:browse_autorzy"), "komputer"),
        ("Autor", autor and autor.get_absolute_url(), "komputer"),
        ("Publikacja", adres_rekordu, "komputer"),
        ("Jednostka", jednostka and jednostka.get_absolute_url(), "komputer"),
        ("Raporty", _adres("nowe_raporty:index"), "komputer"),
        (
            "Komunikaty i przyciski",
            _adres("bpp:konfigurator_wygladu_demo"),
            "komputer",
        ),
        ("Telefon: strona główna", "/", "telefon"),
        ("Telefon: autor", autor and autor.get_absolute_url(), "telefon"),
        ("Telefon: publikacja", adres_rekordu, "telefon"),
    ]
    return [
        {"tytul": tytul, "adres": adres, "urzadzenie": urzadzenie}
        for tytul, adres, urzadzenie in strony
        if adres
    ]


logger = logging.getLogger(__name__)

RE_FAVICON = re.compile(
    r"^data:image/(png|x-icon|vnd\.microsoft\.icon);base64,([A-Za-z0-9+/=]+)$"
)


def _favicon_z_data_url(data_url):
    """Data URL z konfiguratora → (ContentFile, None) albo (None, komunikat).

    Plik sprawdza waliduj_favicon (jak w adminie uczelni).
    """
    m = RE_FAVICON.match(data_url if isinstance(data_url, str) else "")
    if not m:
        return None, "Ikona strony musi być plikiem PNG albo ICO."
    # Szybkie odsianie przed dekodowaniem (base64 ≈ 4/3 rozmiaru).
    if len(m.group(2)) > MAKS_ROZMIAR_FAVICON * 4 // 3 + 4:
        return None, "Ikona strony jest za duża (maksymalnie 1 MB)."
    try:
        dane = base64.b64decode(m.group(2), validate=True)
    except binascii.Error:
        return None, "Ikona strony jest uszkodzona."
    rozszerzenie = ".png" if m.group(1) == "png" else ".ico"
    plik = ContentFile(dane, name="favicon" + rozszerzenie)
    try:
        waliduj_favicon(plik)
    except ValidationError:
        return None, "Ikona strony musi być poprawnym obrazkiem PNG albo ICO."
    return plik, None


def _zapisz_favicon(request, uczelnia, plik):
    """Favicon uczelni: pole Uczelnia.favicon_ico (/favicon.ico) i model
    Favicon biblioteki favicon (``<link>``-i w szablonie, per Site)."""
    from favicon.models import Favicon

    uczelnia.favicon_ico.save(plik.name, plik, save=False)
    uczelnia.save(update_fields=["favicon_ico"])

    if uczelnia.site_id:
        fav = Favicon.objects.filter(site=uczelnia.site, isFavicon=True).first()
        if fav is None:
            fav = Favicon(site=uczelnia.site, title=uczelnia.skrot or "BPP")
        plik.seek(0)
        fav.faviconImage.save(plik.name, plik, save=False)
        fav.isFavicon = True
        fav.save()

    # Cache faviconu unieważniają sygnały zapisu (bpp/favicon_wersja.py).


def _historia(uczelnia):
    """Lista ostatnich „Zastosuj” (bez konfigów — te pobiera się osobno)."""
    return [
        {
            "id": w.pk,
            "kiedy": localtime(w.zastosowano).strftime("%d.%m.%Y %H:%M"),
            "kto": str(w.zastosowal or ""),
        }
        for w in MotywWersja.objects.filter(uczelnia=uczelnia).select_related(
            "zastosowal"
        )
    ]


def _motyw_sprzed_konfiguratora(uczelnia):
    """Motyw (np. app-green), który uczelnia miała przed konfiguratorem."""
    przed = (
        MotywWersja.objects.filter(uczelnia=uczelnia)
        .exclude(motyw_przed__in=["", MOTYW_WLASNY])
        .values_list("motyw_przed", flat=True)
        .first()
    )
    if not przed:
        return None
    etykiety = dict(settings.BPP_THEMES)
    if przed not in etykiety:
        return None
    return {"wartosc": przed, "etykieta": etykiety[przed]}


def _odpowiedz_bledem_kompilacji(wynik):
    """Nieudana kompilacja → JSON. Komunikaty z WynikKompilacji są składane
    jawnie (walidacja ustawień albo ogólne teksty); szczegóły tylko w logu."""
    if wynik.rodzaj == KOLEJKA:
        odpowiedz = JsonResponse({"blad": wynik.blad}, status=429)
        odpowiedz["Retry-After"] = "5"
        return odpowiedz
    dane = {"blad": wynik.blad, "bledy": wynik.bledy}
    if wynik.rodzaj == BRAK_KOMPILATORA:
        # Konfigurator zaproponuje wtedy „Zapisz” zamiast „Zastosuj”.
        dane["niedostepny"] = True
    return JsonResponse(dane, status=400)


def _motywy_zapisane(uczelnia):
    return [
        {
            "id": m.pk,
            "nazwa": m.nazwa,
            "kto": str(m.zapisal or ""),
            "kiedy": localtime(m.zapisano).strftime("%d.%m.%Y %H:%M"),
        }
        for m in MotywZapisany.objects.filter(uczelnia=uczelnia).select_related(
            "zapisal"
        )
    ]


def _uczelnia(request):
    uczelnia = getattr(request, "_uczelnia", None)
    if uczelnia is None:
        raise Http404("Brak uczelni dla tej strony.")
    return uczelnia


@staff_member_required
def konfigurator_wygladu(request):
    uczelnia = _uczelnia(request)
    zapisany = (
        MotywWlasny.objects.filter(uczelnia=uczelnia)
        .select_related("roboczy_zapisal")
        .first()
    )
    roboczy = None
    if zapisany is not None and zapisany.konfig_roboczy:
        roboczy = {
            "konfig": zapisany.konfig_roboczy,
            "kto": str(zapisany.roboczy_zapisal or ""),
            "kiedy": localtime(zapisany.roboczy_zapisano).strftime("%d.%m.%Y %H:%M")
            if zapisany.roboczy_zapisano
            else "",
        }
    return render(
        request,
        "bpp/konfigurator_wygladu.html",
        {
            "podglady": _podglady(),
            "stan_serwera": {
                "mozna_zastosowac": request.user.is_superuser,
                "kompilator_dostepny": kompilator_dostepny(),
                "adres_zastosuj": reverse("bpp:konfigurator_wygladu_zastosuj"),
                "adres_zapisz": reverse("bpp:konfigurator_wygladu_zapisz"),
                "zapisany_konfig": zapisany.konfig if zapisany else None,
                "roboczy": roboczy,
                "historia": _historia(uczelnia),
                "motyw_sprzed": _motyw_sprzed_konfiguratora(uczelnia),
                "motyw_aktywny": uczelnia.theme_name,
                "adres_historia": reverse(
                    "bpp:konfigurator_wygladu_wersja", args=(0,)
                ).replace("/0/", "/{id}/"),
                "adres_przywroc": reverse("bpp:konfigurator_wygladu_przywroc"),
                "adres_przymierz": reverse("bpp:konfigurator_wygladu_przymierz"),
                "zapisany_aktywny": uczelnia.theme_name == MOTYW_WLASNY,
                "zapisany_w_wersji": zapisany.wersja_bpp if zapisany else None,
                "wersja_bpp": VERSION,
                "motywy_zapisane": _motywy_zapisane(uczelnia),
                "adres_motyw_zapisz": reverse("bpp:konfigurator_wygladu_motyw_zapisz"),
                "adres_motyw": reverse(
                    "bpp:konfigurator_wygladu_motyw", args=(0,)
                ).replace("/0/", "/{id}/"),
                "adres_motyw_usun": reverse(
                    "bpp:konfigurator_wygladu_motyw_usun", args=(0,)
                ).replace("/0/", "/{id}/"),
                "favicon_url": uczelnia.favicon_ico.url
                if uczelnia.favicon_ico
                else None,
            },
        },
    )


@staff_member_required
def konfigurator_wygladu_demo(request):
    """Strona demo do podglądu: wszystkie komunikaty, przyciski i pola."""
    for poziom, tekst in (
        (messages.INFO, "Informacja: import pracowników zakończył się."),
        (messages.SUCCESS, "Sukces: zapisano zmiany w rekordzie."),
        (messages.WARNING, "Ostrzeżenie: rekord nie ma przypisanej dyscypliny."),
        (messages.ERROR, "Błąd: nie udało się połączyć z PBN."),
    ):
        messages.add_message(request, poziom, tekst)
    return render(
        request,
        "bpp/konfigurator_wygladu_demo.html",
        {
            "komunikaty": [
                ("primary", "Komunikat w kolorze głównym."),
                ("info", "Informacja."),
                ("success", "Sukces — operacja zakończona."),
                ("warning", "Ostrzeżenie — sprawdź dane."),
                ("alert", "Błąd — operacja się nie powiodła."),
            ],
            "przyciski": [
                ("", "Główny"),
                ("secondary", "Drugorzędny"),
                ("success", "Potwierdzenie"),
                ("warning", "Ostrzeżenie"),
                ("alert", "Usuń"),
            ],
        },
    )


@require_POST
@staff_member_required
def konfigurator_wygladu_zastosuj(request):
    """Kompiluje motyw z przesłanych ustawień, zapisuje go i włącza dla uczelni.

    CSS buduje serwer (bpp.motyw_kompilator, ten sam kod co podgląd) —
    z przeglądarki przychodzą tylko ustawienia, sprawdzane przez
    BppMotywKonfig.waliduj. Mimo to tylko superużytkownik: zmiana dotyczy
    wszystkich odwiedzających.
    """
    if not request.user.is_superuser:
        raise PermissionDenied

    try:
        dane = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"blad": "Niepoprawne dane (JSON)."}, status=400)

    konfig = dane.get("konfig") if isinstance(dane, dict) else None
    favicon = None
    if isinstance(dane, dict) and dane.get("favicon"):
        favicon, blad = _favicon_z_data_url(dane["favicon"])
        if blad:
            return JsonResponse({"blad": blad}, status=400)
    wynik = skompiluj(konfig)
    if not wynik.ok:
        return _odpowiedz_bledem_kompilacji(wynik)
    css = wynik.css

    uczelnia = _uczelnia(request)
    motyw_przed = uczelnia.theme_name
    if favicon is not None:
        _zapisz_favicon(request, uczelnia, favicon)
    MotywWlasny.objects.update_or_create(
        uczelnia=uczelnia,
        defaults={
            "konfig": konfig,
            "css": css,
            "wersja_bpp": VERSION,
            "zmienil": request.user,
            "konfig_roboczy": None,
            "roboczy_zapisal": None,
            "roboczy_zapisano": None,
        },
    )

    if uczelnia.theme_name != MOTYW_WLASNY:
        uczelnia.theme_name = MOTYW_WLASNY
        uczelnia.save(update_fields=["theme_name"])

    MotywWersja.zapisz(uczelnia, konfig, motyw_przed, request.user, VERSION)
    _przebuduj_strony_bledu(uczelnia)
    return JsonResponse({"ok": True})


def _przebuduj_strony_bledu(uczelnia):
    """Statyczne strony 500 (nginx) w nowym motywie — od razu, nie dopiero
    przy następnym starcie kontenera."""
    try:
        call_command(
            "generate_500_page",
            domena=uczelnia.site.domain if uczelnia.site_id else None,
            stdout=io.StringIO(),
            stderr=io.StringIO(),
        )
    except Exception:
        # Strona błędu to dodatek: motyw jest już zastosowany, a strona 500
        # przebuduje się przy starcie kontenera. Logujemy z tracebackiem.
        logger.exception("Nie udało się przebudować strony 500 po zmianie motywu")


@require_POST
@staff_member_required
def konfigurator_wygladu_zapisz(request):
    """Zapisuje ustawienia BEZ stosowania (motyw roboczy).

    Gdy kompilator jest niedostępny albo zapisuje ktoś bez prawa „Zastosuj”.
    Strona się nie zmienia; motyw wczyta się w konfiguratorze i można go
    zastosować później. Pełną walidację (motyw-konfig.js) przejdzie przy
    „Zastosuj” — tu tylko wstępna.
    """
    try:
        dane = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"blad": "Niepoprawne dane (JSON)."}, status=400)
    konfig = dane.get("konfig") if isinstance(dane, dict) else None
    blad = wstepna_walidacja(konfig)
    if blad:
        return JsonResponse({"blad": blad}, status=400)

    MotywWlasny.objects.update_or_create(
        uczelnia=_uczelnia(request),
        defaults={
            "konfig_roboczy": konfig,
            "roboczy_zapisal": request.user,
            "roboczy_zapisano": now(),
        },
    )
    return JsonResponse({"ok": True})


MAKS_DLUGOSC_NAZWY_MOTYWU = 100


@require_POST
@staff_member_required
def konfigurator_wygladu_motyw_zapisz(request):
    """„Zapisz jako…” — motyw pod nazwą, do wczytania później. Ta sama nazwa
    nadpisuje wcześniejszy zapis. Strona się nie zmienia."""
    try:
        dane = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"blad": "Niepoprawne dane (JSON)."}, status=400)
    if not isinstance(dane, dict):
        return JsonResponse({"blad": "Niepoprawne dane (JSON)."}, status=400)
    nazwa = dane.get("nazwa")
    nazwa = nazwa.strip() if isinstance(nazwa, str) else ""
    if not nazwa or len(nazwa) > MAKS_DLUGOSC_NAZWY_MOTYWU:
        return JsonResponse({"blad": "Podaj nazwę motywu (do 100 znaków)."}, status=400)
    konfig = dane.get("konfig")
    blad = wstepna_walidacja(konfig)
    if blad:
        return JsonResponse({"blad": blad}, status=400)
    uczelnia = _uczelnia(request)
    motyw, _ = MotywZapisany.objects.update_or_create(
        uczelnia=uczelnia,
        nazwa=nazwa,
        defaults={"konfig": konfig, "zapisal": request.user},
    )
    return JsonResponse(
        {"ok": True, "id": motyw.pk, "motywy": _motywy_zapisane(uczelnia)}
    )


@staff_member_required
def konfigurator_wygladu_motyw(request, pk):
    motyw = get_object_or_404(MotywZapisany, pk=pk, uczelnia=_uczelnia(request))
    return JsonResponse({"nazwa": motyw.nazwa, "konfig": motyw.konfig})


@require_POST
@staff_member_required
def konfigurator_wygladu_motyw_usun(request, pk):
    uczelnia = _uczelnia(request)
    get_object_or_404(MotywZapisany, pk=pk, uczelnia=uczelnia).delete()
    return JsonResponse({"ok": True, "motywy": _motywy_zapisane(uczelnia)})


@staff_member_required
def konfigurator_wygladu_wersja(request, pk):
    """Ustawienia jednej wersji z historii — do wczytania w konfiguratorze."""
    wersja = get_object_or_404(MotywWersja, pk=pk, uczelnia=_uczelnia(request))
    return JsonResponse({"konfig": wersja.konfig})


@require_POST
@staff_member_required
def konfigurator_wygladu_przywroc(request):
    """Wraca do jednego z motywów BPP_THEMES (np. sprzed konfiguratora).

    Bez kompilacji — pliki tych motywów są w obrazie.
    """
    if not request.user.is_superuser:
        raise PermissionDenied
    try:
        motyw = json.loads(request.body).get("motyw")
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"blad": "Niepoprawne dane (JSON)."}, status=400)
    if motyw not in dict(settings.BPP_THEMES):
        return JsonResponse({"blad": "Nieznany motyw."}, status=400)
    uczelnia = _uczelnia(request)
    uczelnia.theme_name = motyw
    uczelnia.save(update_fields=["theme_name"])
    _przebuduj_strony_bledu(uczelnia)
    return JsonResponse({"ok": True})


@require_POST
@staff_member_required
def konfigurator_wygladu_przymierz(request):
    """Przymiarka: motyw widoczny na całej stronie tylko w tej sesji."""
    try:
        dane = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"blad": "Niepoprawne dane (JSON)."}, status=400)
    konfig = dane.get("konfig") if isinstance(dane, dict) else None
    wynik = skompiluj(konfig)
    if not wynik.ok:
        return _odpowiedz_bledem_kompilacji(wynik)
    przymiarka.rozpocznij(request, wynik.css)
    return JsonResponse({"ok": True, "adres": "/"})


@require_POST
@staff_member_required
def konfigurator_wygladu_przymiarka_koniec(request):
    przymiarka.zakoncz(request)
    nastepny = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(
        nastepny, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return HttpResponseRedirect(nastepny)
    return HttpResponseRedirect("/")


@staff_member_required
def motyw_przymiarka_css(request, skrot):
    tresc = przymiarka.css(skrot)
    if tresc is None:
        raise Http404
    odpowiedz = HttpResponse(tresc, content_type="text/css; charset=utf-8")
    # Prywatny (tylko ta sesja), ale skrót w adresie = treść się nie zmienia.
    odpowiedz["Cache-Control"] = "private, max-age=14400, immutable"
    return odpowiedz


def motyw_wlasny_css(request, skrot):
    """CSS motywu z konfiguratora. Skrót w adresie = treść się nie zmienia,
    więc przeglądarki mogą go trzymać w cache bez końca."""
    # Dwie uczelnie z identycznym CSS-em mają ten sam skrót — bierzemy dowolną.
    motyw = MotywWlasny.objects.filter(skrot=skrot).only("css").first()
    if motyw is None:
        raise Http404
    odpowiedz = HttpResponse(motyw.css, content_type="text/css; charset=utf-8")
    odpowiedz["Cache-Control"] = "public, max-age=31536000, immutable"
    return odpowiedz
