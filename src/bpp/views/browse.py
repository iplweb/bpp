import json
import re

from django.db.models import Count

from django.contrib.contenttypes.models import ContentType

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

from django.db.models.query_utils import Q
from django.http import Http404, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView, ListView, RedirectView, TemplateView
from multiseek.logic import AND, OR
from multiseek.util import make_field
from multiseek.views import MULTISEEK_SESSION_KEY, MULTISEEK_SESSION_KEY_REMOVED

from miniblog.models import Article

from bpp.models import Autor, Jednostka, Rekord, Uczelnia, Wydzial, Zrodlo
from bpp.multiseek_registry import (
    JednostkaQueryObject,
    NazwiskoIImieQueryObject,
    RokQueryObject,
    TypRekorduObject,
    ZrodloQueryObject,
)

PUBLIKACJE = "publikacje"
STRESZCZENIA = "streszczenia"
INNE = "inne"
TYPY = [PUBLIKACJE, STRESZCZENIA, INNE]


def conditional(**kwargs):
    """A wrapper around :func:`django.views.decorators.http.condition` that
    works for methods (i.e. class-based views).
    """
    from django.views.decorators.http import condition

    from django.utils.decorators import method_decorator

    return method_decorator(condition(**kwargs))


class UczelniaView(DetailView):
    model = Uczelnia
    template_name = "browse/uczelnia.html"

    def get_context_data(self, **kwargs):
        context = {}
        if "article_slug" in self.kwargs:
            context["article"] = get_object_or_404(
                Article, slug=self.kwargs["article_slug"]
            )
        else:
            context["miniblog"] = Article.objects.filter(
                status=Article.STATUS.published
            )[:5]

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

    def get_context_data(self, *args, **kw):
        return super().get_context_data(
            flt=self.request.GET.get(self.param),
            literki=LITERKI,
            wybrana=self.kwargs.pop("literka", None),
            *args,
            **kw
        )


class AutorzyView(Browser):
    template_name = "browse/autorzy.html"
    model = Autor
    param = "search"
    literka_field = "nazwisko"
    paginate_by = 252

    def get_queryset(self):

        # Uwzględnia wybraną literkę etc
        ret = super().get_queryset()

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

        return ret.only("nazwisko", "imiona", "slug", "poprzednie_nazwiska").order_by(
            "nazwisko", "imiona"
        )


class ZrodlaView(Browser):
    template_name = "browse/zrodla.html"
    model = Zrodlo
    param = "search"
    literka_field = "nazwa"
    paginate_by = 70

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .only("nazwa", "poprzednia_nazwa", "slug")
            .order_by("nazwa")
        )


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


class ZrodloView(DetailView):
    model = Zrodlo
    template_name = "browse/zrodlo.html"


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

        self.request.session[MULTISEEK_SESSION_KEY] = zrob_formularz(
            zrodla_box, autorzy_box, typy_box, jednostki_box, lata_box
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


END_NUMBER_REGEX = re.compile("(?P<content_type_id>\\d+)-(?P<object_id>\\d+)$")


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
                    except Rekord.DoesNotExist:
                        raise Http404
                    except Rekord.MultipleObjectsReturned:
                        raise NotImplementedError("This should never happen")

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
            except ContentType.DoesNotExist:
                raise Http404

        try:
            obj = Rekord.objects.get(pk=[model, self.kwargs["pk"]])
        except Rekord.DoesNotExist:
            raise Http404

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
