import hashlib
import json
import logging
import re

from cacheops import cached
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef
from django.db.models.functions import Substr
from django.http import JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.functional import cached_property
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt

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
from bpp.models.util import prefetch_dane_strony_rekordu
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
from bpp.permissions import moze_wprowadzac_dane
from bpp.util import sanitize_multiseek_title
from bpp.util.uczelnia_scope import (
    scope_jednostki_do_uczelni,
    scope_rekord_do_uczelni,
    tylko_jedna_uczelnia,
)
from bpp.views.cache_publiczny import DOMYSLNY_TTL, _generacja, cache_publiczny

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
        # BEZ ``.distinct()`` na tym poziomie: ``SELECT DISTINCT`` po
        # bpp_rekord_mat porównuje 49 kolumn (w tym tsvector ``search_index``
        # i duże ``opis_bibliograficzny_cache``), więc Postgres musi
        # zmaterializować i posortować CAŁĄ tabelę zanim zadziała LIMIT 12 —
        # indeks (ostatnio_zmieniony) idzie do kosza. Deduplikacja należy do
        # ``scope_rekord_do_uczelni``: JOIN po M2M ``autorzy`` (jedyne źródło
        # duplikatów tutaj) istnieje wyłącznie w trybie multi-host i helper
        # dokłada tam ``.distinct()`` sam.
        context["recently_updated"] = scope_rekord_do_uczelni(
            Rekord.objects.all(), uczelnia
        ).order_by("-ostatnio_zmieniony")[:12]

        recent_abstracts = Wydawnictwo_Ciagle_Streszczenie.objects.exclude(
            streszczenie__isnull=True
        ).exclude(streszczenie__exact="")
        # Ten sam guard co scope_rekord_do_uczelni, ale na querysecie Streszczeń
        # (helper przyjmuje qs Rekordów). Single-host / brak uczelni => bez filtra.
        # ``.distinct()`` TYLKO w tej gałęzi: ``rekord__autorzy_set__…`` to
        # JOIN po relacji wielowartościowej (rekord z N autorstwami tej samej
        # uczelni dałby N kopii streszczenia). W single-install filtru nie ma,
        # więc nie ma czego deduplikować.
        if uczelnia is not None and not tylko_jedna_uczelnia():
            recent_abstracts = recent_abstracts.filter(
                rekord__autorzy_set__jednostka__uczelnia=uczelnia
            ).distinct()
        context["recent_abstracts"] = recent_abstracts.order_by(
            "-rekord__ostatnio_zmieniony"
        )[:5]

        # Bez ``.distinct()`` COUNT może pójść index-only scanem zamiast
        # hashować 49 kolumn na wiersz; dedup — jak wyżej — jest w helperze.
        context["total_rekord_count"] = scope_rekord_do_uczelni(
            Rekord.objects.all(), uczelnia
        ).count()
        context["current_year"] = timezone.now().date().year

    return context


def conditional(**kwargs):
    """A wrapper around :func:`django.views.decorators.http.condition` that
    works for methods (i.e. class-based views).
    """
    from django.utils.decorators import method_decorator
    from django.views.decorators.http import condition

    return method_decorator(condition(**kwargs))


@method_decorator(cache_publiczny(), name="dispatch")
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


@method_decorator(cache_publiczny(), name="dispatch")
class JednostkaView(DetailView):
    template_name = "browse/jednostka.html"
    model = Jednostka

    #: Listy podjednostek policzone w ``get()`` dla stylu strukturalnego —
    #: szablon dostaje je przez kontekst, zamiast wołać metody modelu (i tak
    #: potrzebne są tu na decyzję o przekierowaniu).
    podjednostki = None

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

            self.podjednostki = {
                "aktualne_podjednostki": aktualne,
                "kola_naukowe": kola,
                "historyczne_podjednostki": historyczne,
            }

        # Szablon woła zarówno pracownicy(), jak i wspolpracowali() — obie te
        # metody potrzebują tego samego zbioru PK aktualnych autorów.
        self.object.prefetch_aktualnych_autorow()

        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            typy=TYPY, **(self.podjednostki or {}), **kwargs
        )


@method_decorator(cache_publiczny(), name="dispatch")
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

    ``.order_by()`` jest tu OBOWIĄZKOWE, nie kosmetyczne. Modele mają
    domyślne ``Meta.ordering`` (``Autor`` — ``["sort"]``, ``Zrodlo``
    i ``Jednostka`` — ``["nazwa"]``), a Django dokłada kolumny sortujące
    do ``SELECT DISTINCT``. Bez wyczyszczenia sortowania baza deduplikuje
    po parze ``(sort, literka)`` zamiast po samej literce i zwraca tyle
    wierszy, ile pasujących obiektów — deduplikację robi dopiero ``set()``
    niżej, po przesłaniu wszystkiego do Pythona. Pilnuje tego
    ``test_distinct_literek_nie_wciaga_kolumny_sortujacej``.
    """
    first_chars = (
        queryset.annotate(_first_char=Substr(field_name, 1, 1))
        .exclude(_first_char="")
        .order_by()
        .values_list("_first_char", flat=True)
        .distinct()
    )
    return {_CHAR_TO_LITERKA[ch] for ch in first_chars if ch and ch in _CHAR_TO_LITERKA}


#: Prefiks kluczy zliczeń — celowo inny niż ``cache_publiczny.PREFIKS``,
#: żeby dało się je rozróżnić w Redisie, ale generacja jest ta SAMA.
PREFIKS_ZLICZEN = "bpp-zliczenia:v1"


def _klucz_zliczenia(request, etykieta):
    """Klucz cache'a dla zliczenia strony przeglądania.

    ``request.get_host()`` jest składnikiem KRYTYCZNYM — to on izoluje
    uczelnie od siebie w multi-host (dokładnie jak w
    ``cache_publiczny._klucz``). Bez niego licznik autorów jednej uczelni
    pokazałby się na stronie drugiej.

    Znacznik generacji sprawia, że zapis ``Autor``/``Jednostka``/``Zrodlo``
    unieważnia zliczenia NATYCHMIAST — te modele są w
    ``BppConfig.MODELE_INWALIDUJACE_CACHE_PUBLICZNY``, więc bumpują tę samą
    generację, której używa cache całych stron.
    """
    surowy = "|".join([str(_generacja()), request.get_host().lower(), etykieta])
    return f"{PREFIKS_ZLICZEN}:{hashlib.sha256(surowy.encode('utf-8')).hexdigest()}"


def zliczenie_z_cache(request, etykieta, oblicz):
    """Policz raz i zapamiętaj — dla zliczeń niebędących treścią strony.

    Dotyczy ``paginator.count`` i rządka literek: obie wartości są
    identyczne dla każdego odwiedzającego, kosztują skan całej tabeli i
    zmieniają się wyłącznie przy edycji danych.

    Zmierzone na bazie UML (68 tys. autorów): wejście na ``/bpp/autorzy/``
    to 409 ms, z czego COUNT 163 ms + literki 174 ms, a właściwa strona
    50 autorów — 35 ms. Po wpięciu tego cache'a: 57 ms (7,2×).

    ``is None`` zamiast testu prawdziwości jest tu istotne: licznik ``0``
    i pusty zbiór liter są POPRAWNYMI zapamiętanymi wartościami.

    Gdy hosta nie da się ustalić (obiekt request niebędący
    ``HttpRequest`` — tak wołają widoki niektóre testy i narzędzia),
    liczymy świeżo i NIE zapamiętujemy. Podstawienie stałej w miejsce
    hosta zlałoby wszystkie uczelnie do jednego wpisu.
    """
    if not hasattr(request, "get_host"):
        return oblicz()

    klucz = _klucz_zliczenia(request, etykieta)
    wartosc = cache.get(klucz)
    if wartosc is None:
        wartosc = oblicz()
        cache.set(klucz, wartosc, DOMYSLNY_TTL)
    return wartosc


class PaginatorZeZliczeniemZCache(Paginator):
    """``Paginator``, którego ``count`` bierze się z ``zliczenie_z_cache``.

    Django woła ``paginator.count`` przy każdym renderze (numery stron,
    napis „N autorów"). Bez tego liczyłby ``COUNT(*)`` po całej tabeli z
    kompletem filtrów uczelni na każde żądanie.
    """

    def __init__(self, *args, licz_count=None, **kwargs):
        self._licz_count = licz_count
        super().__init__(*args, **kwargs)

    @cached_property
    def count(self):
        if self._licz_count is None:
            return super().count
        return self._licz_count()


class Browser(ListView):
    model = None
    param = None
    literka_field = None
    paginate_by = 40

    def setup(self, request, *args, **kwargs):
        """Zapamiętaj wybraną literkę ZANIM ktokolwiek ruszy ``self.kwargs``.

        ``get_context_data`` niżej robi ``self.kwargs.pop("literka")``, a
        pagination w ``MultipleObjectMixin.get_context_data`` biegnie
        DOPIERO po wyliczeniu argumentów tego wywołania — czyli paginator
        widziałby już ``kwargs`` bez literki. Dopóki literka służyła tylko
        do zbudowania querysetu (``get_queryset`` leci przed ``pop``), nie
        bolało; od kiedy wchodzi do klucza cache'a licznika, ``pop``
        sprawiłby, że WSZYSTKIE litery dzielą wpis policzony dla „wszyscy".
        Pilnuje tego ``test_zapamietane_zliczenia_nie_wyciekaja_miedzy_literami``.
        """
        super().setup(request, *args, **kwargs)
        self.literka = kwargs.get("literka")

    def get_search_string(self):
        return self.request.GET.get(self.param, "")

    def get_literka(self):
        # Fallback na ``self.kwargs`` jest konieczny, bo widoki bywają
        # instancjonowane ręcznie, z pominięciem ``setup()``:
        # ``v = AutorzyView(); v.request = ...; v.kwargs = {...}``. Taki
        # widok nigdy nie dojdzie do ``pop`` w ``get_context_data``, więc
        # odczyt wprost z ``kwargs`` jest tam poprawny.
        if not hasattr(self, "literka"):
            return self.kwargs.get("literka")
        return self.literka

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

        # BEZ ``.distinct()``: żadna ścieżka filtrowania nie zwraca tu
        # zdublowanych wierszy, a Paginator wołał ``COUNT(DISTINCT …)`` po
        # wszystkich kolumnach modelu (29 dla Autora) przy każdym wejściu i
        # każdej kolejnej stronie. Ścieżka po ścieżce:
        #
        # * filtr „literki" — ``istartswith`` na własnej kolumnie modelu,
        # * ``fulltext_filter`` dla ``Zrodlo`` i ``Jednostka`` — predykat na
        #   jednokolumnowym tsvectorze, bez JOIN-a,
        # * ``fulltext_filter`` dla ``Autor`` — UWAGA, tu JOIN JEST:
        #   ``AutorManager.fulltext_annotate`` (``bpp/models/autor.py``)
        #   nadpisuje wersję z ``FulltextSearchMixin`` i zwraca
        #   ``Count("wydawnictwo_ciagle")``, co dokłada ``LEFT OUTER JOIN
        #   bpp_wydawnictwo_ciagle_autor``. Wierszy nie mnoży wyłącznie
        #   dlatego, że agregat wymusza ``GROUP BY`` po pk — deduplikacja
        #   pochodzi stamtąd, nie z braku złączenia. Zmiana tej adnotacji na
        #   NIEagregującą zostawi JOIN bez ``GROUP BY`` i wymaga własnej
        #   deduplikacji (pilnuje tego
        #   ``test_autorzy_view_fulltext_nie_mnozy_mimo_joinu_po_publikacjach``),
        # * ``AutorzyView`` — ``Exists()``/``OuterRef`` (skorelowane
        #   podzapytania) plus ``select_related`` po FK,
        # * ``ZrodlaView`` — ``pk__in=<podzapytanie>`` (``IN``, nie JOIN),
        # * ``JednostkiView`` — ``scope_jednostki_do_uczelni`` (równość po
        #   skalarnym FK ``uczelnia``), ``widoczna``, ``parent=None``.
        #
        # Reguła na przyszłość: nowy filtr po relacji odwrotnej lub M2M ma
        # przynieść własną deduplikację RAZEM z sobą (jak robi to
        # ``scope_rekord_do_uczelni``), a nie przywracać bezwarunkowe
        # ``.distinct()`` w klasie bazowej.
        return qry

    def get_paginator(self, queryset, per_page, *args, **kwargs):
        """Paginator liczący ``count`` przez cache — chyba że trwa szukanie.

        Fraza szukana NIE trafia do klucza i przy szukaniu w ogóle nie
        cache'ujemy: przestrzeń fraz jest nieograniczona, więc robot
        przemielający ``?search=<cokolwiek>`` zaśmieciłby Redisa wpisami
        użytecznymi dokładnie raz. Strony bez frazy to najwyżej „wszyscy"
        + 26 liter na host — tyle wpisów jest tanie i trafiane stale.
        """
        if self.get_search_string():
            return super().get_paginator(queryset, per_page, *args, **kwargs)

        etykieta = f"{type(self).__name__}:count:{self.get_literka() or ''}"
        return PaginatorZeZliczeniemZCache(
            queryset,
            per_page,
            *args,
            licz_count=lambda: zliczenie_z_cache(
                self.request, etykieta, lambda: queryset.count()
            ),
            **kwargs,
        )

    def zapamietane_literki(self, base_qry):
        """Rządek dostępnych literek — jeden skan tabeli na generację.

        ``base_qry`` celowo NIE zależy od wybranej litery ani od frazy:
        rządek pokazuje ten sam zestaw na każdej podstronie, więc jeden
        wpis na host obsługuje je wszystkie.
        """
        return zliczenie_z_cache(
            self.request,
            f"{type(self).__name__}:literki",
            lambda: get_available_letters(base_qry, self.literka_field),
        )

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


@method_decorator(cache_publiczny(), name="dispatch")
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
        context["available_letters"] = self.zapamietane_literki(base_qry)
        return context


@method_decorator(cache_publiczny(), name="dispatch")
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

        context["available_letters"] = self.zapamietane_literki(base_qry)
        return context


@method_decorator(cache_publiczny(), name="dispatch")
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

        context["available_letters"] = self.zapamietane_literki(base_qry)
        return context


@method_decorator(cache_publiczny(), name="dispatch")
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


@method_decorator(cache_publiczny(), name="dispatch")
class LataView(ListView):
    template_name = "browse/lata.html"
    context_object_name = "years"
    paginate_by = None

    def get_queryset(self):
        uczelnia = Uczelnia.objects.get_for_request(self.request)
        qs = scope_rekord_do_uczelni(Rekord.objects.all(), uczelnia)
        # ``Count("id", distinct=True)``, NIE ``Count("*")``: w multi-host
        # ``scope_rekord_do_uczelni`` dokłada JOIN po M2M ``autorzy``, więc
        # ``Count("*")`` liczył wiersze złączenia — rekord z dwoma
        # autorstwami tej samej uczelni podbijał licznik roku do 2.
        # ``.distinct()`` z helpera tego nie ratuje: dotyczy zwiniętych par
        # ``(rok, count)``, a nie wierszy wchodzących do agregatu.
        return [
            {"year": row["rok"], "count": row["count"]}
            for row in qs.values("rok")
            .annotate(count=Count("id", distinct=True))
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


@method_decorator(cache_publiczny(), name="dispatch")
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


@method_decorator(csrf_exempt, name="dispatch")
class BuildSearch(RedirectView):
    """Widok przyjmuje zmienne w request.POST i buduje w sesji formularz
    wyszukiwawczy dla multiseek.

    DLACZEGO ``@csrf_exempt`` JEST TU BEZPIECZNY
    ============================================

    Jedynym efektem ubocznym ``post()`` jest zapis zbudowanego zapytania
    wyszukiwawczego do WŁASNEJ sesji requestującego
    (``request.session[MULTISEEK_SESSION_KEY]`` + tytuł + wyczyszczenie
    listy ręcznie wyrzuconych rekordów) i przekierowanie na
    ``multiseek:index``. Nie ma tu żadnej uprzywilejowanej akcji, mutacji
    danych współdzielonych, ujawnienia sekretu ani zmiany stanu poza sesją
    ofiary. Najgorsze, co atak CSRF może osiągnąć, to podsunięcie ofierze
    wyszukiwania, którego sama nie wpisała — zero szkody. Ta sama
    funkcjonalność jest zresztą publiczna (parametry POST bez uwierzytelniania).

    Powód wyłączenia CSRF: bez tokenu w formularzu (``{% csrf_token %}``
    usunięte z szablonów ``browse/autor.html``, ``jednostka.html``,
    ``zrodlo.html``, ``uczelnia.html``) wyrenderowana treść tych stron nie
    zawiera już sekretu związanego z jednym odwiedzającym, dzięki czemu
    ``cache_publiczny`` może je współdzielić między anonimami (strona autora
    ma wysoki ruch). Token w formularzu blokował cache przez bezpiecznik
    ``_ZAWIERA_CSRF``. UWAGA dla przyszłego ``/security-review``: to celowa,
    przemyślana decyzja — NIE regresja. Jeśli kiedyś ``post()`` zacznie robić
    cokolwiek poza zapisem do własnej sesji, ``@csrf_exempt`` trzeba cofnąć.
    """

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

        self.request.session["MULTISEEK_TITLE"] = sanitize_multiseek_title(
            self.request.POST.get("suggested-title", "")
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

        if not moze_wprowadzac_dane(request.user):
            # Rekordy o statusie ukrytym na poziomie "podglad" są niedostępne
            # dla wszystkich POZA użytkownikami z uprawnieniami redaktorskimi
            # (anonim oraz zwykłe zalogowane konto → 403).
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

        # Szablon strony rekordu sięga po autorów opisu i po streszczenia
        # z kilku miejsc (metadane w <head>, opis bibliograficzny, tabela
        # informacji dodatkowych). Materializujemy je raz, przed renderem.
        prefetch_dane_strony_rekordu(self.object.original)

        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)


END_NUMBER_REGEX = re.compile(r"(?P<content_type_id>\d+)-(?P<object_id>\d+)$")


@method_decorator(cache_publiczny(), name="dispatch")
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


@method_decorator(cache_publiczny(), name="dispatch")
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
