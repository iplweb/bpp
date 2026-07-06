import json
import logging
import re

from cacheops import cached
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Exists, OuterRef
from django.db.models.functions import Substr
from django.http import JsonResponse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

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
    JednostkaNadrzednaQueryObject,
    JednostkaQueryObject,
    NazwiskoIImieQueryObject,
    RokQueryObject,
    TypRekorduObject,
    WydzialQueryObject,
    ZakresLatQueryObject,
    ZrodloQueryObject,
)
from bpp.util.uczelnia_scope import (
    scope_jednostki_do_uczelni,
    scope_rekord_do_uczelni,
    tylko_jedna_uczelnia,
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

    # Multi-host: filtruj artykuły po Site bieżącej uczelni. siteblog.Article
    # ma M2M `sites`; pusty M2M = artykuł widoczny wszędzie (zgodnie z
    # help_textem w siteblog). on_site (CurrentSiteManager) jest strict —
    # wymusza Site_id i wyklucza puste M2M — więc używamy własnego Q.
    site_id = uczelnia.site_id
    visible_articles = Article.objects.filter(
        Q(sites=site_id) | Q(sites__isnull=True)
    ).distinct()

    if article_slug:
        context["article"] = get_object_or_404(visible_articles, slug=article_slug)
    else:
        context["news"] = visible_articles.filter(status=Article.STATUS.published)[:5]

        # Multi-host: zawężamy do rekordów uczelni oglądającej przez
        # scope_rekord_do_uczelni. W single-host (jedna uczelnia) helper daje
        # no-op — rekordy bez wpisanego autorstwa pozostają liczone i widoczne,
        # parytet z zachowaniem sprzed multi-hosted (patrz test_single_host_parity).
        context["recently_updated"] = (
            scope_rekord_do_uczelni(Rekord.objects.all(), uczelnia)
            .order_by("-ostatnio_zmieniony")
            .distinct()[:12]
        )

        recent_abstracts = Wydawnictwo_Ciagle_Streszczenie.objects.exclude(
            streszczenie__isnull=True
        ).exclude(streszczenie__exact="")
        # Ten sam guard co scope_rekord_do_uczelni, ale na querysecie Streszczeń
        # (helper przyjmuje qs Rekordów). Single-host / brak uczelni => bez filtra.
        if uczelnia is not None and not tylko_jedna_uczelnia():
            recent_abstracts = recent_abstracts.filter(
                rekord__autorzy_set__jednostka__uczelnia=uczelnia
            )
        context["recent_abstracts"] = recent_abstracts.order_by(
            "-rekord__ostatnio_zmieniony"
        ).distinct()[:5]

        context["total_rekord_count"] = (
            scope_rekord_do_uczelni(Rekord.objects.all(), uczelnia).distinct().count()
        )
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


def browse_wydzial_redirect(request, slug):
    """Legacy URL (`/wydzial/<slug>/`) -- przekierowanie 301 na odpowiednik
    dawnego wydziału w drzewie ``Jednostka``.

    Faza B (#438), III-2: strona wydziału jako osobny widok znika --
    ``WydzialView`` usunięty. Stary URL musi jednak dalej działać (linki
    zewnętrzne, wyszukiwarki, zakładki) -- szukamy więc ``Wydzial`` po
    ``slug`` (model żyje do Fazy C wyłącznie na potrzeby tego lookupu), a
    następnie węzła-lustra (``Jednostka.legacy_wydzial_id == wydzial.pk``,
    patrz ``struktura_konwersja.py``) i przekierowujemy na jego stronę.

    Fallback: gdy slug nie odpowiada żadnemu legacy ``Wydzial`` (albo
    wydział nie ma węzła-lustra), ale istnieje ``Jednostka`` o dokładnie
    tym slugu (np. wydział założony od razu w drzewie, bez modelu
    Wydzial), przekierowujemy wprost na /jednostka/<ten-sam-slug>/.
    W pozostałych przypadkach 404.
    """
    wydzial = Wydzial.objects.filter(slug=slug).first()
    if wydzial is not None:
        jednostka = Jednostka.objects.filter(legacy_wydzial_id=wydzial.pk).first()
        if jednostka is not None:
            return redirect("bpp:browse_jednostka", slug=jednostka.slug, permanent=True)
    get_object_or_404(Jednostka, slug=slug)
    return redirect("bpp:browse_jednostka", slug=slug, permanent=True)


class JednostkaView(DetailView):
    template_name = "browse/jednostka.html"
    model = Jednostka

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        rodzaj = self.object.rodzaj
        if rodzaj is not None and rodzaj.pokazuj_strukture_podjednostek:
            # Styl strukturalny (dawna strona wydziału): jeżeli węzeł ma
            # dokładnie jedną podjednostkę (aktualną, koło naukowe lub
            # historyczną), przeskocz od razu na jej stronę -- tak jak robił
            # to dawny ``WydzialView``.
            aktualne = list(self.object.aktualne_podjednostki())
            kola = list(self.object.kola_naukowe())
            historyczne = list(self.object.historyczne_podjednostki())

            wszystkie = aktualne + kola + historyczne

            if len(wszystkie) == 1:
                return redirect("bpp:browse_jednostka", slug=wszystkie[0].slug)

        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

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
        # Multi-homed: link do PBN musi znać uczelnię z requestu — szablon
        # nie umie przekazać argumentu do metody, więc liczymy go tu. Bez
        # tego ``autor.link_do_pbn`` (bezargumentowo) degraduje do
        # ``get_single_uczelnia_or_none() → None`` przy >1 uczelni (FD#390).
        return super().get_context_data(
            typy=TYPY,
            ma_powiazania=ma_powiazania,
            link_do_pbn=self.object.link_do_pbn(uczelnia),
            **kwargs,
        )


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

                # Guard against open redirects: only ever redirect within this
                # host. The constructed URL is always same-origin (request.path
                # + urlencoded params), so this guard passes in practice; the
                # fallback is a constant (not request-derived) so the redirect
                # sink only ever sees validated-or-literal data.
                if not url_has_allowed_host_and_scheme(
                    redirect_url, allowed_hosts={request.get_host()}
                ):
                    redirect_url = "/"

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
        uczelnia = Uczelnia.objects.get_for_request(getattr(self, "request", None))
        if uczelnia is None:
            return self.paginate_by
        return uczelnia.ilosc_jednostek_na_strone

    def get_queryset(self):
        ordering = None

        qry = super().get_queryset().filter(widoczna=True)

        uczelnia = Uczelnia.objects.get_for_request(self.request)
        qry = scope_jednostki_do_uczelni(qry, uczelnia)
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
        base_qry = scope_jednostki_do_uczelni(base_qry, uczelnia)
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
        uczelnia = Uczelnia.objects.get_for_request(self.request)
        qs = scope_rekord_do_uczelni(Rekord.objects.all(), uczelnia)
        return [
            {"year": row["rok"], "count": row["count"]}
            for row in qs.values("rok")
            .annotate(count=Count("*"))
            .filter(count__gt=0)
            .order_by("-rok")
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Suma z policzonych juz count-ow per rok (get_queryset liczy je juz
        # w zakresie uczelni) — bez drugiego skanu tabeli.
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
        uczelnia = Uczelnia.objects.get_for_request(self.request)
        return scope_rekord_do_uczelni(
            Rekord.objects.filter(rok=year), uczelnia
        ).order_by("-ostatnio_zmieniony")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        year = int(self.kwargs.get("rok"))
        context["year"] = year

        # Navigation to previous/next year (jedno zapytanie zamiast dwoch EXISTS)
        context["prev_year"] = None
        context["next_year"] = None

        uczelnia = Uczelnia.objects.get_for_request(self.request)
        sasiednie_lata = set(
            scope_rekord_do_uczelni(
                Rekord.objects.filter(rok__in=(year - 1, year + 1)), uczelnia
            )
            .values_list("rok", flat=True)
            .distinct()
        )
        if year - 1 in sasiednie_lata:
            context["prev_year"] = year - 1
        if year + 1 in sasiednie_lata:
            context["next_year"] = year + 1

        # Paginator ListView policzyl juz COUNT dla tego roku (queryset jest
        # juz zawezony do uczelni) — nie liczymy drugi raz.
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

        zakres_lat_box = zrob_box_z_requestu(
            self.request.POST, "zakres_lat", ZakresLatQueryObject
        )

        # #438: oba pola „poddrzewowe" (Wydział / Jednostka nadrzędna) budujemy
        # BEZWARUNKOWO. Gdy danego parametru nie ma w POST, ``zrob_box_z_
        # requestu`` zwraca [], a ``zrob_formularz`` pomija puste boxy (no-op),
        # więc obecność obu w wywołaniu nie dokłada nic dla uczelni, która ich
        # nie używa. Dzięki temu POST z przycisku „Pokaż wszystkie publikacje"
        # (``wydzial`` gdy uczelnia używa wydziałów, ``jednostka_nadrzedna`` gdy
        # nie) jest ZAWSZE honorowany — wcześniej gałąź ``not uzywaj_wydzialow``
        # po cichu wyrzucała wartość, dając pusty raport.
        wydzialy_box = zrob_box_z_requestu(
            self.request.POST, "wydzial", WydzialQueryObject
        )
        jednostki_nadrzedne_box = zrob_box_z_requestu(
            self.request.POST, "jednostka_nadrzedna", JednostkaNadrzednaQueryObject
        )

        self.request.session[MULTISEEK_SESSION_KEY] = zrob_formularz(
            zrodla_box,
            autorzy_box,
            typy_box,
            jednostki_box,
            wydzialy_box,
            jednostki_nadrzedne_box,
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
        from raport_slotow.uczelnia_helper import uczelnia_dla_odczytu

        self.object = self.get_object()

        # Multi-hosted: tabela punktacji na stronie rekordu pokazuje sloty/
        # punkty tylko uczelni oglądającego (CPD po uczelni, CPA po
        # jednostka__uczelnia). No-op przy single-install.
        self.object._uczelnia_ogladajacego = uczelnia_dla_odczytu(request)

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
