import json
import re

from cacheops import cached
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count
from django.http import JsonResponse
from django.utils import timezone

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

from django.db.models import Max, Min
from django.db.models.query_utils import Q
from django.http import Http404, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView, RedirectView, TemplateView
from multiseek.logic import AND, OR
from multiseek.util import make_field
from multiseek.views import MULTISEEK_SESSION_KEY, MULTISEEK_SESSION_KEY_REMOVED

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
    JednostkaQueryObject,
    NazwiskoIImieQueryObject,
    RokQueryObject,
    TypRekorduObject,
    WydzialQueryObject,
    ZakresLatQueryObject,
    ZrodloQueryObject,
)
from miniblog.models import Article

PUBLIKACJE = "publikacje"
STRESZCZENIA = "streszczenia"
INNE = "inne"
TYPY = [PUBLIKACJE, STRESZCZENIA, INNE]


@cached(timeout=60 * 60)  # Cache for 1 hour
def get_uczelnia_context_data(uczelnia, article_slug=None):
    """Shared function to get context data for uczelnia view."""
    context = {"object": uczelnia, "uczelnia": uczelnia}

    if article_slug:
        context["article"] = get_object_or_404(Article, slug=article_slug)
    else:
        context["miniblog"] = Article.objects.filter(status=Article.STATUS.published)[
            :5
        ]
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


class JednostkaView(DetailView):
    template_name = "browse/jednostka.html"
    model = Jednostka

    def get_context_data(self, **kwargs):
        return super().get_context_data(typy=TYPY, **kwargs)


class AutorView(DetailView):
    template_name = "browse/autor.html"
    model = Autor

    def get_context_data(self, **kwargs):
        return super().get_context_data(typy=TYPY, **kwargs)


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


class AutorzyView(Browser):
    template_name = "browse/autorzy_modern_bordered.html"
    model = Autor
    param = "search"
    literka_field = "nazwisko"
    paginate_by = 50

    def get_queryset(self):
        # Uwzględnia wybraną literkę etc
        ret = super().get_queryset()

        # Filter out hidden authors
        ret = ret.filter(pokazuj=True)

        uczelnia = Uczelnia.objects.get_for_request(self.request)
        if uczelnia is not None:
            if not uczelnia.pokazuj_autorow_obcych_w_przegladaniu_danych:
                ret = ret.annotate(
                    Count("autor_jednostka")
                )  # ilość jednostek dla każdego autora

                # Wyrzuć autorów przypisanych do Obca + Błędna
                ret = ret.exclude(
                    Q(
                        autor_jednostka__jednostka__pk=-1
                    )  # "BŁĄD: brak wpisanej jednostki"
                    & Q(autor_jednostka__jednostka__pk=uczelnia.obca_jednostka_id)
                    & Q(autor_jednostka__count__lte=2)
                )

                ret = ret.exclude(aktualna_jednostka=None, autor_jednostka__count=1)
                ret = ret.exclude(
                    aktualna_jednostka_id=uczelnia.obca_jednostka_id,
                    autor_jednostka__count=1,
                )

            if not uczelnia.pokazuj_autorow_bez_prac_w_przegladaniu_danych:
                # Nie pokazuj autorów bez prac
                ret = ret.exclude(autorzyview=None)

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

        # Calculate which letters have authors
        # Get base queryset (all visible authors, respecting uczelnia settings)
        base_qry = Autor.objects.filter(pokazuj=True)

        uczelnia = Uczelnia.objects.get_for_request(self.request)
        if uczelnia is not None:
            if not uczelnia.pokazuj_autorow_obcych_w_przegladaniu_danych:
                base_qry = base_qry.annotate(Count("autor_jednostka"))
                base_qry = base_qry.exclude(
                    Q(autor_jednostka__jednostka__pk=-1)
                    & Q(autor_jednostka__jednostka__pk=uczelnia.obca_jednostka_id)
                    & Q(autor_jednostka__count__lte=2)
                )
                base_qry = base_qry.exclude(
                    aktualna_jednostka=None, autor_jednostka__count=1
                )
                base_qry = base_qry.exclude(
                    aktualna_jednostka_id=uczelnia.obca_jednostka_id,
                    autor_jednostka__count=1,
                )

            if not uczelnia.pokazuj_autorow_bez_prac_w_przegladaniu_danych:
                base_qry = base_qry.exclude(autorzyview=None)

        # Check each letter for available authors
        available_letters = set()
        for literka in LITERKI:
            args = [literka]
            if literka in PODWOJNE:
                args = PODWOJNE[literka]

            qobj = Q(**{self.literka_field + "__istartswith": literka})
            for x in args[1:]:
                qobj |= Q(**{self.literka_field + "__istartswith": x})

            if base_qry.filter(qobj).exists():
                available_letters.add(literka)

        context["available_letters"] = available_letters
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

        # Check each letter for available sources
        available_letters = set()
        for literka in LITERKI:
            args = [literka]
            if literka in PODWOJNE:
                args = PODWOJNE[literka]

            qobj = Q(**{self.literka_field + "__istartswith": literka})
            for x in args[1:]:
                qobj |= Q(**{self.literka_field + "__istartswith": x})

            if base_qry.filter(qobj).exists():
                available_letters.add(literka)

        context["available_letters"] = available_letters
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

        # Check each letter for available units
        available_letters = set()
        for literka in LITERKI:
            args = [literka]
            if literka in PODWOJNE:
                args = PODWOJNE[literka]

            qobj = Q(**{self.literka_field + "__istartswith": literka})
            for x in args[1:]:
                qobj |= Q(**{self.literka_field + "__istartswith": x})

            if base_qry.filter(qobj).exists():
                available_letters.add(literka)

        context["available_letters"] = available_letters
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
        # Get all years that have publications, with counts
        years_data = []

        # Get min and max years from Rekord
        year_range = Rekord.objects.aggregate(min_year=Min("rok"), max_year=Max("rok"))

        if year_range["min_year"] and year_range["max_year"]:
            # Generate list of years from max to min (newest first)
            for year in range(year_range["max_year"], year_range["min_year"] - 1, -1):
                count = Rekord.objects.filter(rok=year).count()
                if count > 0:  # Only include years with publications
                    years_data.append({"year": year, "count": count})

        return years_data

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_publications"] = Rekord.objects.count()

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

        # Navigation to previous/next year
        context["prev_year"] = None
        context["next_year"] = None

        if Rekord.objects.filter(rok=year - 1).exists():
            context["prev_year"] = year - 1

        if Rekord.objects.filter(rok=year + 1).exists():
            context["next_year"] = year + 1

        # Get total count for the year
        context["total_count"] = Rekord.objects.filter(rok=year).count()

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
        url = uczelnia.deklaracja_dostepnosci_tekst

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

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
