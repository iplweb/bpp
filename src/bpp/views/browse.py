import json
import logging
import re

from cacheops import cached
from django.conf import settings
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Exists, OuterRef
from django.db.models.functions import Substr
from django.http import JsonResponse
from django.utils import timezone

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

from django.db.models.query_utils import Q
from django.http import Http404, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView, ListView, RedirectView, TemplateView
from multiseek.logic import AND, OR
from multiseek.util import make_field
from multiseek.views import MULTISEEK_SESSION_KEY, MULTISEEK_SESSION_KEY_REMOVED
from siteblog.models import Article

from bpp.models import (
    Autor,
    Jednostka,
    Rekord,
    Uczelnia,
    Wydawnictwo_Ciagle_Streszczenie,
    Wydzial,
    Zrodlo,
)
from bpp.multiseek_registry import (
    CharakterFormalnyQueryObject,
    JednostkaQueryObject,
    NazwiskoIImieQueryObject,
    RokQueryObject,
    TypRekorduObject,
    WydzialQueryObject,
    ZakresLatQueryObject,
    ZrodloQueryObject,
)

logger = logging.getLogger(__name__)

PUBLIKACJE = "publikacje"
STRESZCZENIA = "streszczenia"
INNE = "inne"
TYPY = [PUBLIKACJE, STRESZCZENIA, INNE]


def invalidate_uczelnia_cache_on_article_change(sender, instance, **kwargs):
    """Invalidate main page cache when a published Article is saved.

    Wired in ``bpp.apps.BppConfig.ready`` against ``siteblog.Article``.
    siteblog is a generic package and intentionally does not know about
    BPP's cache, so the receiver lives here.
    """
    if instance.status == sender.STATUS.published:
        get_uczelnia_context_data.invalidate()


@cached(timeout=60 * 60)  # Cache for 1 hour
def get_uczelnia_context_data(uczelnia, article_slug=None):
    """Shared function to get context data for uczelnia view."""
    context = {"object": uczelnia, "uczelnia": uczelnia}

    if article_slug:
        context["article"] = get_object_or_404(Article, slug=article_slug)
    else:
        context["news"] = Article.objects.filter(status=Article.STATUS.published)[:5]
        # Add 5 most recently updated records
        context["recently_updated"] = Rekord.objects.order_by("-ostatnio_zmieniony")[
            :12
        ]
        # Add 5 recent records with abstracts
        context["recent_abstracts"] = (
            Wydawnictwo_Ciagle_Streszczenie.objects.exclude(streszczenie__isnull=True)
            .exclude(streszczenie__exact="")
            .order_by("-rekord__ostatnio_zmieniony")[:5]
        )
        context["total_rekord_count"] = Rekord.objects.count()
        context["current_year"] = timezone.now().date().year

    return context


def conditional(**kwargs):
    """A wrapper around :func:`django.views.decorators.http.condition` that
    works for methods (i.e. class-based views).
    """
    from django.utils.decorators import method_decorator
    from django.views.decorators.http import condition

    return method_decorator(condition(**kwargs))


class UczelniaView(DetailView):
    model = Uczelnia
    template_name = "browse/uczelnia.html"

    def get_context_data(self, **kwargs):
        article_slug = self.kwargs.get("article_slug")
        context = get_uczelnia_context_data(self.object, article_slug)
        context["show_zglos_button"] = self.object.sprawdz_uprawnienie(
            "formularz_zglaszania_publikacji", self.request
        )
        context.update(kwargs)
        return super().get_context_data(**context)


class WydzialView(DetailView):
    template_name = "browse/wydzial.html"
    model = Wydzial

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        # Zbierz wszystkie jednostki z trzech kategorii
        aktualne = list(self.object.aktualne_jednostki())
        kola = list(self.object.kola_naukowe())
        historyczne = list(self.object.historyczne_jednostki())

        wszystkie = aktualne + kola + historyczne

        if len(wszystkie) == 1:
            jednostka = wszystkie[0]
            return redirect("bpp:browse_jednostka", slug=jednostka.slug)

        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)


class JednostkaView(DetailView):
    template_name = "browse/jednostka.html"
    model = Jednostka

    def get_context_data(self, **kwargs):
        return super().get_context_data(typy=TYPY, **kwargs)


class AutorView(DetailView):
    template_name = "browse/autor.html"
    model = Autor

    def get_context_data(self, **kwargs):
        from powiazania_autorow.models import AuthorConnection

        # Link do sieci pokazujemy tylko gdy (a) są jakieś powiązania ORAZ
        # (b) sieć jest włączona dla tego autora (per-autor nadpisuje
        # per-uczelnia). Ten sam warunek twardo bramkuje widoki sieci (404).
        # getattr — get_context_data bywa wołane w testach jednostkowych bez
        # request; get_for_request(None) degraduje do uczelni domyślnej.
        uczelnia = Uczelnia.objects.get_for_request(getattr(self, "request", None))
        ma_powiazania = (
            self.object.czy_pokazywac_siec_powiazan(uczelnia)
            and AuthorConnection.objects.filter(
                Q(primary_author=self.object) | Q(secondary_author=self.object)
            ).exists()
        )

        from bpp.profil_autora_dane import przygotuj_sekcje

        request = getattr(self, "request", None)
        return super().get_context_data(
            typy=TYPY,
            uczelnia=uczelnia,
            ma_powiazania=ma_powiazania,
            sekcje_profilu=przygotuj_sekcje(self.object, uczelnia, request),
            historia_zatrudnienia=self.object.historia_zatrudnienia(uczelnia),
            raport_links=self._raport_links(request),
            **kwargs,
        )

    def _raport_links(self, request):
        """Linki do raportu autora — tylko gdy raport jest widoczny dla
        oglądającego (reużycie ``DefinicjaRaportu.widoczny_dla``). Trzy linki:
        bieżący rok, ostatnie 4 lata oraz szczegółowy formularz."""
        if request is None:
            return []

        from nowe_raporty.models import DefinicjaRaportu

        for definicja in DefinicjaRaportu.objects.filter(slug="raport-autorow"):
            if definicja.widoczny_dla(request):
                break
        else:
            return []

        rok = timezone.now().date().year
        pk = self.object.pk
        return [
            {
                "label": f"Raport za rok {rok}",
                "url": reverse(
                    "nowe_raporty:raport_generuj",
                    args=["raport-autorow", pk, rok, rok],
                ),
            },
            {
                "label": "Raport za ostatnie 4 lata",
                "url": reverse(
                    "nowe_raporty:raport_generuj",
                    args=["raport-autorow", pk, rok - 3, rok],
                ),
            },
            {
                "label": "Raport szczegółowy…",
                # ?obiekt=<pk> → formularz raportu od razu z wybranym autorem
                # (RaportFormView.get_initial czyta ten parametr).
                "url": (
                    reverse("nowe_raporty:raport_form", args=["raport-autorow"])
                    + f"?obiekt={pk}"
                ),
            },
        ]


LITERKI = "ABCDEFGHIJKLMNOPQRSTUVWYXZ"

PODWOJNE = {
    "A": ["A", "Ą", "ą"],
    "C": ["C", "Ć", "ć"],
    "E": ["E", "Ę", "ę"],
    "L": ["L", "Ł", "ł"],
    "N": ["N", "Ń", "ń"],
    "O": ["O", "Ó", "ó"],
    "Z": ["Z", "Ź", "Ż", "ź", "ż"],
}


def _build_char_to_literka():
    """Map any first-char (incl. polish diacritics, both cases) to canonical
    letter from LITERKI. Built once at import time."""
    mapping = {}
    for literka in LITERKI:
        mapping[literka] = literka
        mapping[literka.lower()] = literka
    for literka, variants in PODWOJNE.items():
        for v in variants:
            mapping[v] = literka
            mapping[v.lower()] = literka
    return mapping


_CHAR_TO_LITERKA = _build_char_to_literka()


def get_available_letters(queryset, field_name):
    """Return the set of LITERKI for which queryset has at least one row.

    One DB query (DISTINCT first char) instead of 26+ .exists() probes.
    """
    first_chars = (
        queryset.annotate(_first_char=Substr(field_name, 1, 1))
        .exclude(_first_char="")
        .values_list("_first_char", flat=True)
        .distinct()
    )
    return {_CHAR_TO_LITERKA[ch] for ch in first_chars if ch and ch in _CHAR_TO_LITERKA}


class Browser(ListView):
    model = None
    param = None
    literka_field = None
    paginate_by = 40

    def get_search_string(self):
        return self.request.GET.get(self.param, "")

    def get_literka(self):
        return self.kwargs.get("literka")

    def get_queryset(self):
        literka = self.get_literka()
        sstr = self.get_search_string()

        if sstr:
            qry = self.model.objects.fulltext_filter(self.get_search_string())
        else:
            qry = self.model.objects.all()

        if literka:
            args = [literka]
            if literka in PODWOJNE:
                args = PODWOJNE[literka]

            qobj = Q(**{self.literka_field + "__istartswith": literka})
            for x in args[1:]:
                qobj |= Q(**{self.literka_field + "__istartswith": x})
            qry = qry.filter(qobj)  # **{self.param + "__istartswith": literka})

        return qry.distinct()

    def get_context_data(self, **kw):
        return super().get_context_data(
            flt=self.request.GET.get(self.param),
            literki=LITERKI,
            wybrana=self.kwargs.pop("literka", None),
            **kw,
        )

    def get(self, request, *args, **kwargs):
        """Handle GET request with graceful pagination error handling."""
        try:
            return super().get(request, *args, **kwargs)
        except Http404 as e:
            # Check if this is a pagination error
            # Django converts EmptyPage/PageNotAnInteger to Http404 in paginate_queryset()
            error_msg = str(e)
            # Check for pagination errors in both Polish and English
            pagination_error_markers = [
                "Invalid page",  # English
                "Page is not",  # English
                "Nieprawidłowy numer strony",  # Polish - EmptyPage
                "Ta strona nie zawiera",  # Polish - EmptyPage
                "nie można przekształcić na liczbę",  # Polish - PageNotAnInteger
            ]
            is_pagination_error = any(
                marker in error_msg for marker in pagination_error_markers
            )

            if is_pagination_error:
                # Build redirect URL preserving all query parameters except 'page'
                params = request.GET.copy()
                params.pop("page", None)
                params["page"] = "1"

                redirect_url = request.path
                if params:
                    redirect_url += "?" + params.urlencode()

                # Add warning message
                messages.warning(
                    request,
                    "Podana strona nie istnieje. Przekierowano na pierwszą stronę.",
                )

                return redirect(redirect_url)
            else:
                # Not a pagination error, re-raise
                raise


class AutorzyView(Browser):
    template_name = "browse/autorzy_modern_bordered.html"
    model = Autor
    param = "search"
    literka_field = "nazwisko"
    paginate_by = 50

    def _apply_uczelnia_filters(self, queryset):
        """Apply uczelnia-based author filtering.

        Filters out foreign authors and authors without publications
        based on uczelnia settings.
        """
        uczelnia = Uczelnia.objects.get_for_request(self.request)
        if uczelnia is None:
            return queryset

        if not uczelnia.pokazuj_autorow_obcych_w_przegladaniu_danych:
            from bpp.models import Autor_Jednostka

            sztuczne_jednostki = [-1]
            if uczelnia.obca_jednostka_id is not None:
                sztuczne_jednostki.append(uczelnia.obca_jednostka_id)

            przypisania = Autor_Jednostka.objects.filter(autor=OuterRef("pk"))

            queryset = queryset.annotate(
                _ma_przypisania=Exists(przypisania),
                _ma_prawdziwa_jednostke=Exists(
                    przypisania.exclude(jednostka_id__in=sztuczne_jednostki)
                ),
                # EXISTS(... OFFSET 1) == "ma co najmniej dwa przypisania"
                _ma_wiele_przypisan=Exists(przypisania.values("pk")[1:]),
            )

            # Wyrzuć autorów, których WSZYSTKIE przypisania to jednostki
            # sztuczne: skonfigurowana obca_jednostka lub pk=-1 ("Błędna"
            # z konwencji starych wdrożeń). Wcześniejszy zapis
            # Q(pk=-1) & Q(pk=obca_id) & Q(count<=2) w exclude() ukrywał
            # tylko autorów w OBU sztucznych naraz (exclude daje warunkom
            # wielowartościowym osobne joiny); autor wyłącznie w jednej
            # sztucznej jednostce pozostawał widoczny.
            queryset = queryset.exclude(
                _ma_przypisania=True, _ma_prawdziwa_jednostke=False
            )
            queryset = queryset.exclude(
                aktualna_jednostka=None,
                _ma_przypisania=True,
                _ma_wiele_przypisan=False,
            )
            queryset = queryset.exclude(
                aktualna_jednostka_id=uczelnia.obca_jednostka_id,
                _ma_przypisania=True,
                _ma_wiele_przypisan=False,
            )

        if not uczelnia.pokazuj_autorow_bez_prac_w_przegladaniu_danych:
            from bpp.models.cache import Autorzy

            # Exists po zmaterializowanej bpp_autorzy_mat (indeks po
            # autor_id) zamiast anti-joina po bpp_autorzy — to widok-unia
            # 5 tabel *_autor, nie zmaterializowany, wiec kazde zapytanie
            # skanowalo wszystkie tabele zrodlowe.
            queryset = queryset.filter(
                Exists(Autorzy.objects.filter(autor=OuterRef("pk")))
            )

        return queryset

    def get_queryset(self):
        ret = super().get_queryset().filter(pokazuj=True)
        ret = self._apply_uczelnia_filters(ret)
        return (
            ret.select_related("aktualna_jednostka", "aktualna_jednostka__wydzial")
            .only(
                "nazwisko",
                "imiona",
                "slug",
                "poprzednie_nazwiska",
                "aktualna_jednostka__nazwa",
                "aktualna_jednostka__wydzial__nazwa",
            )
            .order_by("nazwisko", "imiona")
        )

    def get_context_data(self, *args, **kw):
        context = super().get_context_data(*args, **kw)
        base_qry = Autor.objects.filter(pokazuj=True)
        base_qry = self._apply_uczelnia_filters(base_qry)
        context["available_letters"] = get_available_letters(
            base_qry, self.literka_field
        )
        return context


class ZrodlaView(Browser):
    template_name = "browse/zrodla.html"
    model = Zrodlo
    param = "search"
    literka_field = "nazwa"
    paginate_by = 70

    def get_queryset(self):
        qry = (
            super()
            .get_queryset()
            .only("nazwa", "poprzednia_nazwa", "slug", "pbn_uid__status")
            .order_by("nazwa")
        )

        uczelnia = Uczelnia.objects.get_for_request(self.request)
        if uczelnia is not None:
            if not uczelnia.pokazuj_zrodla_bez_prac_w_przegladaniu_danych:
                from bpp.models import Wydawnictwo_Ciagle

                qry = qry.filter(
                    pk__in=Wydawnictwo_Ciagle.objects.values_list(
                        "zrodlo_id", flat=True
                    ).distinct()
                )
        return qry

    def get_context_data(self, *args, **kw):
        context = super().get_context_data(*args, **kw)

        # Calculate which letters have sources
        # Get base queryset (all sources, respecting uczelnia settings)
        base_qry = Zrodlo.objects.all()

        uczelnia = Uczelnia.objects.get_for_request(self.request)
        if uczelnia is not None:
            if not uczelnia.pokazuj_zrodla_bez_prac_w_przegladaniu_danych:
                from bpp.models import Wydawnictwo_Ciagle

                base_qry = base_qry.filter(
                    pk__in=Wydawnictwo_Ciagle.objects.values_list(
                        "zrodlo_id", flat=True
                    ).distinct()
                )

        context["available_letters"] = get_available_letters(
            base_qry, self.literka_field
        )
        return context


class JednostkiView(Browser):
    template_name = "browse/jednostki.html"
    model = Jednostka
    param = "search"
    literka_field = "nazwa"
    paginate_by = 150

    def get_paginate_by(self, queryset):
        uczelnia = None

        if hasattr(self, "request") and self.request is not None:
            uczelnia = Uczelnia.objects.get_for_request(self.request)

        if uczelnia is None:
            uczelnia = Uczelnia.objects.get_default()

        if uczelnia is None:
            return self.paginate_by

        return uczelnia.ilosc_jednostek_na_strone

    def get_queryset(self):
        ordering = None

        qry = super().get_queryset().filter(widoczna=True)

        uczelnia = Uczelnia.objects.get_for_request(self.request)
        if uczelnia:
            if uczelnia.sortuj_jednostki_alfabetycznie:
                ordering = ("nazwa",)

            if uczelnia.pokazuj_tylko_jednostki_nadrzedne:
                qry = qry.filter(parent=None)

        ret = qry.only("nazwa", "slug", "wydzial").select_related("wydzial")

        if ordering:
            ret = ret.order_by(*ordering)

        return ret

    def get_context_data(self, *args, **kw):
        context = super().get_context_data(*args, **kw)

        # Calculate which letters have units
        # Get base queryset (all visible units, respecting uczelnia settings)
        base_qry = Jednostka.objects.filter(widoczna=True)

        uczelnia = Uczelnia.objects.get_for_request(self.request)
        if uczelnia and uczelnia.pokazuj_tylko_jednostki_nadrzedne:
            base_qry = base_qry.filter(parent=None)

        context["available_letters"] = get_available_letters(
            base_qry, self.literka_field
        )
        return context


class ZrodloView(DetailView):
    model = Zrodlo
    template_name = "browse/zrodlo.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Check if the source has any publications
        from bpp.models import Wydawnictwo_Ciagle

        context["has_publications"] = Wydawnictwo_Ciagle.objects.filter(
            zrodlo=self.object
        ).exists()
        return context


class LataView(ListView):
    template_name = "browse/lata.html"
    context_object_name = "years"
    paginate_by = None

    def get_queryset(self):
        return [
            {"year": row["rok"], "count": row["count"]}
            for row in Rekord.objects.values("rok")
            .annotate(count=Count("*"))
            .filter(count__gt=0)
            .order_by("-rok")
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Suma z policzonych juz count-ow per rok — bez drugiego skanu tabeli.
        context["total_publications"] = sum(
            year_data["count"] for year_data in context["years"]
        )

        # Add current year for reference
        context["current_year"] = timezone.now().year

        # Group years by decade for better navigation
        if context["years"]:
            decades = {}
            for year_data in context["years"]:
                decade = (year_data["year"] // 10) * 10
                if decade not in decades:
                    decades[decade] = []
                decades[decade].append(year_data)
            context["decades"] = dict(sorted(decades.items(), reverse=True))

        return context


class RokView(ListView):
    template_name = "browse/rok.html"
    model = Rekord
    context_object_name = "publications"
    paginate_by = 50

    def get_queryset(self):
        year = self.kwargs.get("rok")

        # Validate year
        try:
            year = int(year)
            if year < 1900 or year > 2100:
                raise ValueError
        except (ValueError, TypeError) as e:
            raise Http404("Nieprawidłowy rok") from e

        # Get publications for this year
        return Rekord.objects.filter(rok=year).order_by("-ostatnio_zmieniony")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        year = int(self.kwargs.get("rok"))
        context["year"] = year

        # Navigation to previous/next year (jedno zapytanie zamiast dwoch EXISTS)
        context["prev_year"] = None
        context["next_year"] = None

        sasiednie_lata = set(
            Rekord.objects.filter(rok__in=(year - 1, year + 1))
            .values_list("rok", flat=True)
            .distinct()
        )
        if year - 1 in sasiednie_lata:
            context["prev_year"] = year - 1
        if year + 1 in sasiednie_lata:
            context["next_year"] = year + 1

        # Paginator ListView policzyl juz COUNT dla tego roku — nie liczymy
        # drugi raz.
        context["total_count"] = context["paginator"].count

        return context


def zrob_box(values, name, qo):
    ret = []
    po = None
    for value in values:
        ret.append(make_field(qo, qo.ops[0], value, prev_op=po))
        po = OR
    return ret


def zrob_box_z_requestu(dct, name, qo):
    if dct.get(name):
        return zrob_box(dct.getlist(name), name, qo)
    return []


def zrob_formularz(*args):
    ret = [None]

    prev_op = None

    for arg in [x for x in args if x]:
        if len(arg) > 1:
            lst = [prev_op]
            lst.extend(arg)
            ret.append(lst)
        else:
            arg[0]["prev_op"] = prev_op
            ret.append(arg[0])

        prev_op = AND

    return json.dumps({"form_data": ret})


class BuildSearch(RedirectView):
    """Widok przyjmuje zmienne w request.GET i buduje w sesji formularz wyszukiwawczy
    dla multiseek."""

    def get_redirect_url(self, **kwargs):
        url = self.request.build_absolute_uri(reverse("multiseek:index"))
        scheme = self.request.META.get("HTTP_X_SCHEME", "").lower()
        if scheme == "https":
            url = url.replace("http://", "https://").replace("HTTP://", "HTTPS://")
        return url

    def post(self, *args, **kw):
        zrodla_box = zrob_box_z_requestu(self.request.POST, "zrodlo", ZrodloQueryObject)
        typy_box = zrob_box_z_requestu(self.request.POST, "typ", TypRekorduObject)
        lata_box = zrob_box_z_requestu(self.request.POST, "rok", RokQueryObject)
        jednostki_box = zrob_box_z_requestu(
            self.request.POST, "jednostka", JednostkaQueryObject
        )
        autorzy_box = zrob_box_z_requestu(
            self.request.POST, "autor", NazwiskoIImieQueryObject
        )

        # Klik w „Statystyki wg charakteru" na podstronie autora POST-uje nazwę
        # charakteru — CharakterFormalnyQueryObject.value_from_web rozwiązuje ją
        # po `nazwa` (z potomkami MPTT).
        charakter_box = zrob_box_z_requestu(
            self.request.POST, "charakter_formalny", CharakterFormalnyQueryObject
        )

        zakres_lat_box = zrob_box_z_requestu(
            self.request.POST, "zakres_lat", ZakresLatQueryObject
        )

        if getattr(settings, "DJANGO_BPP_UCZELNIA_UZYWA_WYDZIALOW", True):
            wydzialy_box = zrob_box_z_requestu(
                self.request.POST, "wydzial", WydzialQueryObject
            )

            self.request.session[MULTISEEK_SESSION_KEY] = zrob_formularz(
                zrodla_box,
                autorzy_box,
                typy_box,
                charakter_box,
                jednostki_box,
                wydzialy_box,
                lata_box,
                zakres_lat_box,
            )
        else:
            self.request.session[MULTISEEK_SESSION_KEY] = zrob_formularz(
                zrodla_box,
                autorzy_box,
                typy_box,
                charakter_box,
                jednostki_box,
                lata_box,
                zakres_lat_box,
            )

        self.request.session["MULTISEEK_TITLE"] = self.request.POST.get(
            "suggested-title", ""
        )

        # Usuń listę ręcznie wyrzuconych rekordów, ponieważ wchodzimy na świeże
        # wyszukiwanie (#325)
        self.request.session.pop(MULTISEEK_SESSION_KEY_REMOVED, None)

        return super().post(*args, **kw)


class PracaViewMixin:
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        if request.user.is_anonymous:
            # Jeżeli użytkownik jest anonimowy, to może obejmować go ukrywanie statusów
            uczelnia = Uczelnia.objects.get_for_request(request)

            if uczelnia is not None:
                statusy = uczelnia.ukryte_statusy("podglad")

                if self.object.status_korekty_id in statusy:
                    return HttpResponseForbidden("Brak uprawnień do rekordu")

        if (
            "slug" not in self.kwargs
            and hasattr(self.object, "slug")
            and self.object.slug
        ):
            return HttpResponseRedirect(
                reverse("bpp:browse_praca_by_slug", args=(self.object.slug,))
            )

        if (
            "slug" in self.kwargs
            and hasattr(self.object, "slug")
            and self.object.slug != self.kwargs["slug"]
        ):
            # Przy przekierowaniu z linku typu 'starytekst_32_4533'
            # (because cool URIs don't change!)
            return HttpResponseRedirect(
                reverse("bpp:browse_praca_by_slug", args=(self.object.slug,))
            )

        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)


END_NUMBER_REGEX = re.compile(r"(?P<content_type_id>\d+)-(?P<object_id>\d+)$")


class PracaViewBySlug(PracaViewMixin, DetailView):
    template_name = "browse/praca.html"
    model = Rekord

    def get_object(self):
        try:
            return Rekord.objects.get(slug=self.kwargs["slug"])
        except (Rekord.DoesNotExist, Rekord.MultipleObjectsReturned):
            # Sprawdź cyferki na końcu
            res = re.search(END_NUMBER_REGEX, self.kwargs["slug"])
            if res is not None:
                content_type_id, object_id = None, None
                try:
                    content_type_id, object_id = res.groups()
                except ValueError:
                    pass

                if content_type_id is not None and object_id is not None:
                    try:
                        obj = Rekord.objects.get(pk=[content_type_id, object_id])
                    except Rekord.DoesNotExist as e:
                        raise Http404 from e
                    except Rekord.MultipleObjectsReturned as e:
                        raise NotImplementedError("This should never happen") from e

                    return obj

        raise Http404


class PracaView(PracaViewMixin, DetailView):
    template_name = "browse/praca.html"
    model = Rekord

    def get_object(self, queryset=None):
        model = self.kwargs["model"]

        try:
            int(model)
        except ValueError:
            try:
                model = ContentType.objects.get_by_natural_key("bpp", model).pk
            except ContentType.DoesNotExist as e:
                raise Http404 from e

        try:
            obj = Rekord.objects.get(pk=[model, self.kwargs["pk"]])
        except Rekord.DoesNotExist as e:
            raise Http404 from e

        return obj


class OldPracaView(RedirectView):
    permanent = True

    def get_redirect_url(self, *args, **kwargs):
        return reverse(
            "bpp:browse_praca",
            args=(
                ContentType.objects.get(app_label="bpp", model=self.kwargs["model"]).pk,
                self.kwargs["pk"],
            ),
        )


class RekordToPracaView(RedirectView):
    model = Rekord

    def get_redirect_url(self, *args, **kw):
        return reverse(
            "bpp:browse_praca",
            args=(self.kwargs["content_type_id"], self.kwargs["object_id"]),
        )


class WyswietlDeklaracjeDostepnosci(TemplateView):
    template_name = "browse/deklaracja_dostepnosci.html"

    def get_context_data(self, **kwargs):
        uczelnia = Uczelnia.objects.get_for_request(self.request)
        if uczelnia is None:
            raise Http404

        tekst = uczelnia.deklaracja_dostepnosci_tekst
        url = uczelnia.deklaracja_dostepnosci_url

        return {"tekst": tekst, "url": url, "uczelnia": uczelnia}


def bibtex_view(request, model, pk):
    """
    AJAX endpoint to get BibTeX representation of a publication.

    Args:
        request: HTTP request
        model: Model name (content type name or ID)
        pk: Primary key of the publication

    Returns:
        JsonResponse with BibTeX content or error message
    """
    try:
        # Handle model parameter (can be name or ContentType ID)
        try:
            content_type_id = int(model)
        except ValueError:
            try:
                content_type = ContentType.objects.get_by_natural_key("bpp", model)
                content_type_id = content_type.pk
            except ContentType.DoesNotExist:
                return JsonResponse({"error": "Invalid model type"}, status=400)

        # Get the publication record
        try:
            rekord = Rekord.objects.get(pk=[content_type_id, pk])
        except Rekord.DoesNotExist:
            return JsonResponse({"error": "Publication not found"}, status=404)

        # Get the actual publication object
        praca = rekord.original

        # Generate BibTeX using the model's to_bibtex method
        if hasattr(praca, "to_bibtex"):
            bibtex_content = praca.to_bibtex()
            return JsonResponse(
                {
                    "bibtex": bibtex_content,
                    "title": getattr(praca, "tytul_oryginalny", "Publication"),
                }
            )
        else:
            return JsonResponse(
                {"error": "BibTeX export not available for this publication type"},
                status=400,
            )

    except Exception:
        logger.exception("BibTeX export failed for model=%s pk=%s", model, pk)
        return JsonResponse({"error": "Internal error generating BibTeX"}, status=500)
