import json
from collections import OrderedDict

import isbnlib
from braces.views import GroupRequiredMixin, LoginRequiredMixin
from dal import autocomplete
from dal_select2_queryset_sequence.views import Select2QuerySetSequenceView
from django import http
from django.core.exceptions import ImproperlyConfigured
from django.db.models.aggregates import Count
from django.db.models.query_utils import Q
from queryset_sequence import QuerySetSequence
from taggit.models import Tag

from import_common.core import normalized_db_isbn
from import_common.normalization import normalize_isbn
from import_common.util import check_if_doi, strip_doi_urls
from pbn_api.client import PBNClient
from pbn_api.exceptions import WillNotExportError
from pbn_api.integrator import zapisz_mongodb
from pbn_api.models import Publication, Publisher
from pbn_api.validators import check_mongoId

from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.postgres.search import TrigramSimilarity

from django.utils.text import capfirst

from bpp import const
from bpp.const import CHARAKTER_OGOLNY_KSIAZKA, GR_WPROWADZANIE_DANYCH, PBN_UID_LEN
from bpp.jezyk_polski import warianty_zapisanego_nazwiska
from bpp.models import (
    Autor_Dyscyplina,
    Dyscyplina_Naukowa,
    Jednostka,
    Kierunek_Studiow,
    Status_Korekty,
    Uczelnia,
    Wydawca,
    Zewnetrzna_Baza_Danych,
)
from bpp.models.autor import Autor
from bpp.models.cache import Rekord
from bpp.models.konferencja import Konferencja
from bpp.models.nagroda import OrganPrzyznajacyNagrody
from bpp.models.patent import Patent, Patent_Autor
from bpp.models.praca_doktorska import Praca_Doktorska
from bpp.models.praca_habilitacyjna import Praca_Habilitacyjna
from bpp.models.profile import BppUser
from bpp.models.seria_wydawnicza import Seria_Wydawnicza
from bpp.models.struktura import Wydzial
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte, Wydawnictwo_Zwarte_Autor
from bpp.models.zrodlo import Rodzaj_Zrodla, Zrodlo


class PublicTaggitTagAutocomplete(autocomplete.Select2QuerySetView):
    create_field = None

    def get_queryset(self):
        qs = Tag.objects.all()
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs


class Wydawnictwo_NadrzedneAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Wydawnictwo_Zwarte.objects.filter(
            charakter_formalny__charakter_ogolny=CHARAKTER_OGOLNY_KSIAZKA
        )

        if self.q:
            qs = qs.filter(tytul_oryginalny__icontains=self.q)
        return qs


class Wydawnictwo_CiagleAdminAutocomplete(
    LoginRequiredMixin, autocomplete.Select2QuerySetView
):
    def get_queryset(self):
        qs = Wydawnictwo_Ciagle.objects.all()
        if self.q:
            qs = qs.filter(tytul_oryginalny__icontains=self.q)
        return qs


class Wydawnictwo_ZwarteAdminAutocomplete(
    LoginRequiredMixin, autocomplete.Select2QuerySetView
):
    def get_queryset(self):
        qs = Wydawnictwo_Zwarte.objects.all()
        if self.q:
            qs = qs.filter(tytul_oryginalny__icontains=self.q)
        return qs


class PublicWydawnictwo_NadrzedneAutocomplete(Wydawnictwo_NadrzedneAutocomplete):
    create_field = None

    def get_queryset(self):
        """
        :test: :py:class:`bpp.tests.test_autocomplete`
        """

        # Publiczna wyszukiwarka dla wydawnictw nadrzędnych powinna wyszukiwać wyłącznie rekordy,
        # które są już wydawnictwami nadrzędnymi dla jakichś rekordów:

        qs = Wydawnictwo_Zwarte.objects.filter(
            pk__in=Wydawnictwo_Zwarte.objects.exclude(wydawnictwo_nadrzedne_id=None)
            .values_list("wydawnictwo_nadrzedne_id")
            .distinct()
        )

        if self.q:
            qs = qs.filter(tytul_oryginalny__icontains=self.q)
        return qs


class Wydawnictwo_Nadrzedne_W_PBNAutocomplete(autocomplete.Select2QuerySetView):
    # Ile rekordów maksymalnie ściągać z PBN?
    MAX_RECORDS_DOWNLOADED = 10

    MONGO_ID = "mongoId"
    ISBN = "ISBN"
    TITLE = "tytuł"
    DOI = "DOI"

    def qualify_query(self, txt):
        """Zwraca wartość klucza po którym wyszukiwać w PBN, ale i tym samym kwalifikuje
        wpisaną przez użytkownika wartość ze zmiennej txt jako ISBN, DOI lub tytuł"""

        if not isbnlib.notisbn(txt):
            return self.ISBN

        if check_mongoId(txt):
            return self.MONGO_ID

        if check_if_doi(txt):
            return self.DOI

        return self.TITLE

    def get_create_option(self, context, q):
        qual = self.qualify_query(q)
        if qual == self.DOI:
            q = strip_doi_urls(q)
        elif qual == self.ISBN:
            q = isbnlib.canonical(q)

        create_option = [
            {
                "id": q,
                "text": f'Pobierz z PBN rekord(y) gdzie {qual} to "{q}"',
                "create_id": True,
            }
        ]
        return create_option

    def render_to_response(self, context):
        """Return a JSON response in Select2 format."""
        q = self.request.GET.get("q", None)

        create_option = []
        if not self.has_more(context):
            # Wyświetlaj opcję pobrania z PBN tylko pod koniec listy rekordów
            create_option = self.get_create_option(context, q)

        return http.JsonResponse(
            {
                "results": self.get_results(context) + create_option,
                "pagination": {"more": self.has_more(context)},
            }
        )

    def get(self, request, *args, **kwargs):
        """Return option list json response."""
        if self.q is None or not self.q or len(self.q) < 5:
            return http.JsonResponse(
                {"results": [{"id": "id", "text": "Wpisz przynajmniej 5 znaków..."}]},
                content_type="application/json",
            )

        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        if not self.q or len(self.q) < 5:
            return [
                {
                    "id": self.q,
                    "text": "Wpisz przynajmniej 5 znaków...",
                    "create_id": False,
                }
            ]

        from pbn_api.models import Publication

        match self.qualify_query(self.q):
            case self.MONGO_ID:
                return Publication.objects.filter(pk=self.q)
            case self.ISBN:
                isbn = isbnlib.canonical(self.q)
                return Publication.objects.filter(isbn=isbn)
            case self.TITLE:
                return Publication.objects.filter(title__icontains=self.q)
            case self.DOI:
                doi = strip_doi_urls(self.q)
                return Publication.objects.filter(doi=doi)
            case _:
                raise NotImplementedError(self.q)

    def post(self, request, *args, **kwargs):
        """Create an object given a text after checking permissions."""
        uczelnia: Uczelnia = Uczelnia.objects.get_for_request(self.request)
        try:
            client: PBNClient = uczelnia.pbn_client()
        except WillNotExportError:
            return http.JsonResponse(
                {"id": "error", "text": "Wykonaj autoryzację w PBN!"}
            )

        text = request.POST.get("text", None)

        if text is None:
            return http.HttpResponseBadRequest()

        text = text.strip()

        match self.qualify_query(text):
            case self.MONGO_ID:
                lst = client.search_publications(objectId=text)
            case self.ISBN:
                text = isbnlib.canonical(text)
                lst = client.search_publications(isbn=text, type="BOOK")
            case self.TITLE:
                lst = client.search_publications(title=text, type="BOOK")
            case self.DOI:
                text = strip_doi_urls(text)
                lst = client.search_publications(doi=text, type="BOOK")
            case _:
                return http.JsonResponse(
                    {
                        "id": "error",
                        "text": f"Niezaimplementowany rodzaj wyszukiwania dla {text}",
                    }
                )

        no_records_found = 0

        for elem in lst:
            # z PBNu mogą przychodzić rekordy, które już sa w bazie danych i realnie nie ma żadnej możliwości
            # odsortować ich, więc po prostu je zignorujemy...
            print(elem)
            if Publication.objects.filter(pk=elem["mongoId"]).exists():
                print("mam istniejaca")
                continue
            print("mam nowa")

            # Jest rekord z PBN ID spoza tych w bazie
            no_records_found += 1
            if no_records_found > self.MAX_RECORDS_DOWNLOADED:
                break
            pub = zapisz_mongodb(
                client.get_publication_by_id(elem["mongoId"]), Publication
            )

        if no_records_found == 0:
            return http.JsonResponse(
                {"id": "test", "text": "Nic (nowego) nie znaleziono w PBN."}
            )

        if no_records_found == 1:
            # Znaleziono tylko 1 rekord w PBN, więc można go zwrócić i ustawić jako wybrany...
            return http.JsonResponse({"id": pub.pk, "text": pub.title})

        if no_records_found > self.MAX_RECORDS_DOWNLOADED:
            byloby_wiecej = "Potencjalnie jest ich więcej. "

        return http.JsonResponse(
            {
                "id": "test",
                "text": f"Pobrano {no_records_found} rekord/y/ów. {byloby_wiecej}Wpisz szukany tekst jeszcze raz",
            }
        )


class JednostkaMixin:
    def get_result_label(self, result):
        if result is not None:
            if hasattr(result, "wydzial") and result.wydzial is not None:
                return f"{result.nazwa} ({result.wydzial.skrot})"
            return f"{result.nazwa} (bez wydziału)"


class JednostkaAutocomplete(JednostkaMixin, autocomplete.Select2QuerySetView):
    qset = Jednostka.objects.all().select_related("wydzial")

    def get_queryset(self):
        qs = self.qset
        if self.q:
            qs = qs.filter(Q(nazwa__icontains=self.q) | Q(skrot__icontains=self.q))
        return qs.order_by(*Jednostka.objects.get_default_ordering())


class KierunekStudiowAutocomplete(autocomplete.Select2QuerySetView):
    qset = Kierunek_Studiow.objects.all().select_related("wydzial")

    def get_queryset(self):
        qs = self.qset
        if self.q:
            qs = qs.filter(Q(nazwa__icontains=self.q) | Q(skrot__icontains=self.q))
        return qs.order_by("nazwa")


class LataAutocomplete(autocomplete.Select2QuerySetView):
    qset = (
        Rekord.objects.all().values_list("rok", flat=True).distinct().order_by("-rok")
    )

    def get_queryset(self):
        qs = self.qset
        if self.q:
            qs = qs.filter(rok=self.q)
        return qs

    def get_result_value(self, result):
        return result

    def get_result_label(self, result):
        return str(result)


class NazwaMixin:
    def get_queryset(self):
        qs = self.qset
        if self.q:
            self.q = self.q.strip()
            qs = qs.filter(nazwa__icontains=self.q)
        return qs


class NazwaTrigramMixin:
    MIN_TRIGRAM_MATCH = 0.05

    def get_queryset(self):
        qs = self.qset
        if self.q:
            self.q = self.q.strip()
            qs = (
                qs.annotate(similarity=TrigramSimilarity("nazwa", self.q))
                .filter(similarity__gte=self.MIN_TRIGRAM_MATCH)
                .order_by("-similarity")[:10]
            )
        return qs


class NazwaLubSkrotMixin:
    def get_queryset(self):
        qs = self.qset
        if self.q:
            qs = qs.filter(Q(nazwa__icontains=self.q) | Q(skrot__icontains=self.q))
        return qs


class KonferencjaAutocomplete(
    NazwaMixin, LoginRequiredMixin, autocomplete.Select2QuerySetView
):
    create_field = "nazwa"
    qset = Konferencja.objects.all()

    def get_result_label(self, result):
        return f"{Konferencja.TK_SYMBOLE[result.typ_konferencji]} {str(result)}"

    def create_object(self, text):
        return self.get_queryset().create(nazwa=text.strip())


class WydawcaAutocomplete(
    NazwaTrigramMixin, LoginRequiredMixin, autocomplete.Select2QuerySetView
):
    create_field = "nazwa"
    qset = Wydawca.objects.all()

    def create_object(self, text):
        return self.get_queryset().create(nazwa=text.strip())


class PublisherAutocomplete(
    NazwaTrigramMixin, LoginRequiredMixin, autocomplete.Select2QuerySetView
):
    def get_queryset(self):
        qset = Publisher.objects.all()

        if not self.q or len(self.q) == PBN_UID_LEN:
            return qset.filter(mongoId=self.q)

        bazowe_zapytanie = (
            qset.annotate(similarity=TrigramSimilarity("publisherName", self.q))
            .filter(similarity__gte=self.MIN_TRIGRAM_MATCH)
            .order_by("-similarity")
        )

        z_identyfikatorami = bazowe_zapytanie.exclude(mniswId=None)[:10]
        bez_identyfikatorow = bazowe_zapytanie.filter(mniswId=None)[:10]

        return QuerySetSequence(z_identyfikatorami, bez_identyfikatorow)

    def get_result_label(self, result):
        return str(result)


class PublicKonferencjaAutocomplete(NazwaMixin, autocomplete.Select2QuerySetView):
    qset = Konferencja.objects.all()


class Seria_WydawniczaAutocomplete(
    NazwaMixin, LoginRequiredMixin, autocomplete.Select2QuerySetView
):
    create_field = "nazwa"
    qset = Seria_Wydawnicza.objects.all()


class WydzialAutocomplete(NazwaLubSkrotMixin, autocomplete.Select2QuerySetView):
    qset = Wydzial.objects.all()


class PublicWydzialAutocomplete(NazwaLubSkrotMixin, autocomplete.Select2QuerySetView):
    qset = Wydzial.objects.filter(widoczny=True)


class OrganPrzyznajacyNagrodyAutocomplete(NazwaMixin, autocomplete.Select2QuerySetView):
    qset = OrganPrzyznajacyNagrody.objects.all()


class WidocznaJednostkaAutocomplete(JednostkaAutocomplete):
    qset = Jednostka.objects.widoczne().select_related("wydzial")


class PublicJednostkaAutocomplete(JednostkaAutocomplete):
    qset = Jednostka.objects.publiczne().select_related("wydzial")


def autocomplete_create_error(msg):
    class Error:
        pk = -1

        def __str__(self):
            return msg

    return Error()


class PublicZrodloAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Zrodlo.objects.all()
        if self.q:
            for token in [x.strip() for x in self.q.split(" ") if x.strip()]:
                qs = qs.filter(
                    Q(nazwa__icontains=token)
                    | Q(poprzednia_nazwa__icontains=token)
                    | Q(nazwa_alternatywna__icontains=token)
                    | Q(skrot__istartswith=token)
                    | Q(skrot_nazwy_alternatywnej__istartswith=token)
                )
        return qs


class ZrodloAutocomplete(GroupRequiredMixin, PublicZrodloAutocomplete):
    create_field = "nazwa"
    group_required = GR_WPROWADZANIE_DANYCH

    def create_object(self, text):
        try:
            rz = Rodzaj_Zrodla.objects.get(nazwa="periodyk")
        except Rodzaj_Zrodla.DoesNotExist:
            return autocomplete_create_error(
                "Nie można utworzyć źródła - brak zdefiniowanego"
                " rodzaju źródła 'periodyk'"
            )

        return self.get_queryset().create(nazwa=text.strip(), rodzaj=rz)


class AutorAutocompleteBase(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.q:
            return Autor.objects.fulltext_filter(self.q).select_related("tytul")
        return Autor.objects.all()


class PublicStatusKorektyAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if self.q:
            return Status_Korekty.objects.filter(nazwa__icontains=self.q)
        return Status_Korekty.objects.all()


class AutorAutocomplete(GroupRequiredMixin, AutorAutocompleteBase):
    create_field = "nonzero"
    group_required = GR_WPROWADZANIE_DANYCH

    err = autocomplete_create_error(
        "Wpisz nazwisko, potem imiona. Wyrazy oddziel spacją. "
    )

    def create_object(self, text):
        try:
            return Autor.objects.create_from_string(text)
        except ValueError:
            return self.err


class PublicAutorAutocomplete(AutorAutocompleteBase):
    pass


class AutorZUczelniAutocopmlete(AutorAutocomplete):
    pass


class StaffRequired(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff


def jest_czyms(s, dlugosc):
    if s is not None:
        if len(s) == dlugosc and s.find(" ") == -1:
            return True
    return False


def jest_orcid(s):
    return jest_czyms(s, const.ORCID_LEN)


def jest_pbn_uid(s):
    return jest_czyms(s, const.PBN_UID_LEN)


AUTOR_ONLY = (
    "pk",
    "nazwisko",
    "imiona",
    "poprzednie_nazwiska",
    "tytul__skrot",
    "aktualna_funkcja__nazwa",
    "pseudonim",
)

AUTOR_SELECT_RELATED = "tytul", "aktualna_funkcja"


def globalne_wyszukiwanie_autora(querysets, q):
    if jest_orcid(q):
        querysets.append(
            Autor.objects.filter(orcid__icontains=q)
            .only(*AUTOR_ONLY)
            .select_related(*AUTOR_SELECT_RELATED)
        )

    if jest_pbn_uid(q):
        querysets.append(
            Autor.objects.filter(pbn_uid_id=q).only(*AUTOR_ONLY).select_related("tytul")
        )

    querysets.append(
        Autor.objects.fulltext_filter(q)
        .annotate(Count("wydawnictwo_ciagle"))
        .only(*AUTOR_ONLY)
        .select_related(*AUTOR_SELECT_RELATED)
        .order_by("-search__rank", "-wydawnictwo_ciagle__count")
    )


def globalne_wyszukiwanie_jednostki(querysets, s):
    def _fun(qry):
        return qry.only("pk", "nazwa", "wydzial__skrot").select_related("wydzial")

    querysets.append(_fun(Jednostka.objects.fulltext_filter(s)))

    if jest_pbn_uid(s):
        querysets.append(_fun(Jednostka.objects.filter(pbn_uid_id=s)))


def globalne_wyszukiwanie_zrodla(querysets, s):
    def _fun(qry):
        return qry.only("pk", "nazwa", "poprzednia_nazwa")

    rezultaty = Zrodlo.objects.fulltext_filter(s, normalization=8).order_by(
        "-search__rank", "nazwa"
    )
    querysets.append(_fun(rezultaty))

    if jest_pbn_uid(s):
        querysets.append(_fun(Zrodlo.objects.filter(pbn_uid_id=s)))


class GlobalNavigationAutocomplete(Select2QuerySetSequenceView):
    paginate_by = 40

    def get_result_label(self, result):
        if isinstance(result, Autor):
            if result.aktualna_funkcja_id is not None:
                return str(result) + ", " + str(result.aktualna_funkcja.nazwa)
        return str(result)

    def get_results(self, context):
        """
        Return a list of results usable by Select2.

        It will render as a list of one <optgroup> per different content type
        containing a list of one <option> per model.
        """
        groups = OrderedDict()

        for result in context["object_list"]:
            groups.setdefault(type(result), [])
            groups[type(result)].append(result)

        return [
            {
                "id": None,
                "text": capfirst(self.get_model_name(model)),
                "children": [
                    {
                        "id": self.get_result_value(result),
                        "text": self.get_result_label(result),
                    }
                    for result in results
                ],
            }
            for model, results in groups.items()
        ]

    def get_queryset(self):
        if not hasattr(self, "q"):
            return []

        if not self.q:
            return []

        querysets = []
        globalne_wyszukiwanie_jednostki(querysets, self.q)

        globalne_wyszukiwanie_autora(querysets, self.q)

        globalne_wyszukiwanie_zrodla(querysets, self.q)

        # Rekord

        rekord_qset_ftx = Rekord.objects.fulltext_filter(self.q)

        rekord_qset_doi = Rekord.objects.filter(doi__iexact=self.q)
        rekord_qset_isbn = Rekord.objects.filter(isbn__iexact=self.q)
        rekord_qset_pbn = None
        if jest_pbn_uid(self.q):
            rekord_qset_pbn = Rekord.objects.filter(pbn_uid_id=self.q)

        qry = Q(pk__in=rekord_qset_doi.values_list("pk"))
        qry |= Q(pk__in=rekord_qset_isbn)
        if rekord_qset_pbn:
            qry |= Q(pk__in=rekord_qset_pbn.values_list("pk"))

        rekord_qset = Rekord.objects.filter(qry).only("tytul_oryginalny")

        if hasattr(self, "request") and self.request.user.is_anonymous:
            uczelnia = Uczelnia.objects.get_for_request(self.request)
            if uczelnia is not None:
                rekord_qset_ftx = rekord_qset_ftx.exclude(
                    status_korekty_id__in=uczelnia.ukryte_statusy("podglad")
                )

                rekord_qset = rekord_qset.exclude(
                    status_korekty_id__in=uczelnia.ukryte_statusy("podglad")
                )
        querysets.append(rekord_qset_ftx)
        querysets.append(rekord_qset)

        this_is_an_id = False
        try:
            this_is_an_id = int(self.q)
        except (TypeError, ValueError):
            pass

        if this_is_an_id:
            querysets.append(
                Rekord.objects.extra(where=["id[2]=%s" % this_is_an_id]).only(
                    "tytul_oryginalny"
                )
            )

        ret = QuerySetSequence(*querysets)
        return self.mixup_querysets(ret)


class AdminNavigationAutocomplete(StaffRequired, Select2QuerySetSequenceView):
    paginate_by = 60

    def get_queryset(self):
        if not self.q:
            return []

        if len(self.q) < 1:
            return []

        querysets = []

        querysets.append(
            BppUser.objects.filter(username__icontains=self.q).only("pk", "username")
        )

        globalne_wyszukiwanie_jednostki(querysets, self.q)

        querysets.append(
            Konferencja.objects.filter(
                Q(nazwa__icontains=self.q) | Q(skrocona_nazwa__icontains=self.q)
            ).only("pk", "nazwa", "baza_inna", "baza_wos", "baza_scopus")
        )

        globalne_wyszukiwanie_autora(querysets, self.q)

        globalne_wyszukiwanie_zrodla(querysets, self.q)

        for klass in [
            Wydawnictwo_Zwarte,
            Wydawnictwo_Ciagle,
            Patent,
            Praca_Doktorska,
            Praca_Habilitacyjna,
        ]:
            filter = Q(tytul_oryginalny__icontains=self.q)

            try:
                int(self.q)
                filter |= Q(pk=self.q)
            except (TypeError, ValueError):
                pass

            if klass != Patent:
                filter |= Q(doi__iexact=self.q)

            if len(self.q) == 24 and self.q.find(" ") == -1:
                if "pbn_uid" in [fld.name for fld in klass._meta.fields]:
                    filter |= Q(pbn_uid__pk=self.q)

            annotate_isbn = False
            if hasattr(klass, "isbn"):
                ni = normalize_isbn(self.q)
                if len(ni) < 20:
                    filter |= Q(normalized_isbn=ni)
                    annotate_isbn = True

            if annotate_isbn:
                qset = klass.objects.annotate(
                    normalized_isbn=normalized_db_isbn
                ).filter(filter)
            else:
                qset = klass.objects.filter(filter)

            querysets.append(qset.only("tytul_oryginalny"))

        ret = QuerySetSequence(*querysets)
        return self.mixup_querysets(ret)


class ZapisanyJakoAutocomplete(autocomplete.Select2ListView):
    def get(self, request, *args, **kwargs):
        # Celem spatchowania tej funkcji jest zmiana tekstu 'Create "%s"'
        # na po prostu '%s'. Poza tym jest to kalka z autocomplete.Select2ListView
        results = self.get_list()
        create_option = []
        if self.q:
            results = [x for x in results if self.q.lower() in x.lower()]
            if hasattr(self, "create"):
                create_option = [{"id": self.q, "text": self.q, "create_id": True}]
        return http.HttpResponse(
            json.dumps(
                {"results": [dict(id=x, text=x) for x in results] + create_option}
            ),
            content_type="application/json",
        )

    def post(self, request):
        # Hotfix dla django-autocomplete-light w wersji 3.3.0-rc5, pull
        # request dla problemu zgłoszony tutaj:
        # https://github.com/yourlabs/django-autocomplete-light/issues/977
        if not hasattr(self, "create"):
            raise ImproperlyConfigured('Missing "create()"')

        text = request.POST.get("text", None)

        if text is None:
            return http.HttpResponseBadRequest()

        text = self.create(text)

        if text is None:
            return http.HttpResponseBadRequest()

        return http.JsonResponse(
            {
                "id": text,
                "text": text,
            }
        )

    def create(self, text):
        return text

    def get_list(self):
        autor = self.forwarded.get("autor", None)

        if autor is None:
            return ["(... może najpierw wybierz autora)"]

        try:
            autor_id = int(autor)
            a = Autor.objects.get(pk=autor_id)
        except (KeyError, ValueError):
            return [
                'Błąd. Wpisz poprawne dane w pole "Autor".',
            ]
        except Autor.DoesNotExist:
            return [
                'Błąd. Wpisz poprawne dane w pole "Autor".',
            ]
        return list(
            set(
                list(
                    warianty_zapisanego_nazwiska(
                        a.imiona, a.nazwisko, a.poprzednie_nazwiska
                    )
                )
            )
        )


class PodrzednaPublikacjaHabilitacyjnaAutocomplete(Select2QuerySetSequenceView):
    def get_queryset(self):
        wydawnictwa_zwarte = Wydawnictwo_Zwarte.objects.all()
        wydawnictwa_ciagle = Wydawnictwo_Ciagle.objects.all()
        patenty = Patent.objects.all()

        qs = QuerySetSequence(wydawnictwa_ciagle, wydawnictwa_zwarte, patenty)

        autor_id = self.forwarded.get("autor", None)
        if autor_id is None:
            return qs.none()

        try:
            autor = Autor.objects.get(pk=int(autor_id))
        except (TypeError, ValueError, Autor.DoesNotExist):
            return qs.none()

        wydawnictwa_zwarte = Wydawnictwo_Zwarte.objects.filter(
            pk__in=Wydawnictwo_Zwarte_Autor.objects.filter(autor=autor).only("rekord")
        )
        wydawnictwa_ciagle = Wydawnictwo_Ciagle.objects.filter(
            pk__in=Wydawnictwo_Ciagle_Autor.objects.filter(autor=autor).only("rekord")
        )

        patenty = Patent.objects.filter(
            pk__in=Patent_Autor.objects.filter(autor=autor).only("rekord")
        )

        qs = QuerySetSequence(wydawnictwa_ciagle, wydawnictwa_zwarte, patenty)

        if self.q:
            qs = qs.filter(tytul_oryginalny__icontains=self.q)

        qs = self.mixup_querysets(qs)

        return qs


class Dyscyplina_NaukowaAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Dyscyplina_Naukowa.objects.all()
        if self.q:
            qs = qs.filter(Q(nazwa__icontains=self.q) | Q(kod__icontains=self.q))
        return qs


class Zewnetrzna_Baza_DanychAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Zewnetrzna_Baza_Danych.objects.all()
        if self.q:
            qs = qs.filter(Q(nazwa__icontains=self.q) | Q(skrot__icontains=self.q))
        return qs


class Dyscyplina_Naukowa_PrzypisanieAutocomplete(autocomplete.Select2ListView):
    def results(self, results):
        """Return data for the 'results' key of the response."""
        return [{"id": _id, "text": value} for _id, value in results]

    def autocomplete_results(self, results):
        return [(x, y) for x, y in results if self.q.lower() in y.lower()]

    def get_list(self):
        autor = self.forwarded.get("autor", None)
        if autor is None:
            return [(None, "Podaj autora")]

        if not isinstance(autor, str):
            return [(None, "Podaj autora")]

        if not autor.strip():
            return [(None, "Podaj autora")]

        try:
            autor = int(autor)
        except (TypeError, ValueError):
            return [(None, "Nieprawidłowe ID autora")]

        rok = self.forwarded.get("rok", None)
        if rok is None:
            return [(None, "Podaj rok")]
        try:
            rok = int(rok)
        except (TypeError, ValueError):
            return [(None, "Nieprawidłowy rok")]
        if rok < 0 or rok > 9999:
            return [(None, "Nieprawidłowy rok")]

        try:
            ad = Autor_Dyscyplina.objects.get(rok=rok, autor=autor)
        except Autor_Dyscyplina.DoesNotExist:
            return [(None, "Brak przypisania dla roku %s" % rok)]

        res = set()
        for elem in ["dyscyplina_naukowa", "subdyscyplina_naukowa"]:
            id = getattr(ad, "%s_id" % elem)
            if id is not None:
                res.add((id, getattr(ad, elem).nazwa))

        res = list(res)
        res.sort(key=lambda obj: obj[1])

        return res
