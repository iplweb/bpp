# -*- encoding: utf-8 -*-
import json

from braces.views import GroupRequiredMixin, LoginRequiredMixin
from dal import autocomplete
from dal_select2_queryset_sequence.views import Select2QuerySetSequenceView
from django import http
from django.core.exceptions import ImproperlyConfigured
from django.db.models.aggregates import Count
from django.db.models.query_utils import Q
from queryset_sequence import QuerySetSequence

from django.contrib.auth.mixins import UserPassesTestMixin

from bpp.jezyk_polski import warianty_zapisanego_nazwiska
from bpp.lookups import SearchQueryStartsWith
from bpp.models import (
    Autor_Dyscyplina,
    Dyscyplina_Naukowa,
    Jednostka,
    Uczelnia,
    Wydawca,
    Zewnetrzna_Baza_Danych,
)
from bpp.models.autor import Autor
from bpp.models.cache import Rekord
from bpp.models.const import CHARAKTER_OGOLNY_KSIAZKA, GR_WPROWADZANIE_DANYCH
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
from bpp.util import fulltext_tokenize


class Wydawnictwo_NadrzedneAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):

        qs = Wydawnictwo_Zwarte.objects.filter(
            charakter_formalny__charakter_ogolny=CHARAKTER_OGOLNY_KSIAZKA
        )

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


class JednostkaMixin:
    def get_result_label(self, result):
        return f"{result.nazwa} ({result.wydzial.skrot})"


class JednostkaAutocomplete(JednostkaMixin, autocomplete.Select2QuerySetView):
    qset = Jednostka.objects.all().select_related("wydzial")

    def get_queryset(self):
        qs = self.qset
        if self.q:
            qs = qs.filter(Q(nazwa__icontains=self.q) | Q(skrot__icontains=self.q))
        return qs.order_by(*Jednostka.objects.get_default_ordering())


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
            qs = qs.filter(nazwa__icontains=self.q)
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
    NazwaMixin, LoginRequiredMixin, autocomplete.Select2QuerySetView
):
    create_field = "nazwa"
    qset = Wydawca.objects.all()

    def create_object(self, text):
        return self.get_queryset().create(nazwa=text.strip())


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
    qset = Jednostka.objects.filter(widoczna=True).select_related("wydzial")


def autocomplete_create_error(msg):
    class Error:
        pk = -1

        def __str__(self):
            return msg

    return Error


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
        qs = Autor.objects.all()
        if self.q:
            tokens = fulltext_tokenize(self.q)
            query = SearchQueryStartsWith(
                "&".join([token + ":*" for token in tokens if token]),
                config="bpp_nazwy_wlasne",
            )

            qs = qs.filter(search=query)

            qs = (
                qs.annotate(Count("wydawnictwo_ciagle"))
                .select_related("tytul")
                .order_by("-wydawnictwo_ciagle__count")
            )

        return qs


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


class GlobalNavigationAutocomplete(Select2QuerySetSequenceView):
    paginate_by = 20

    def get_queryset(self):
        if not hasattr(self, "q"):
            return []

        if not self.q:
            return []

        querysets = []
        querysets.append(
            Jednostka.objects.fulltext_filter(self.q)
            .only("pk", "nazwa", "wydzial__skrot")
            .select_related("wydzial")
        )

        querysets.append(
            Autor.objects.fulltext_filter(self.q)
            .annotate(Count("wydawnictwo_ciagle"))
            .only("pk", "nazwisko", "imiona", "poprzednie_nazwiska", "tytul__skrot")
            .select_related("tytul")
            .order_by("-wydawnictwo_ciagle__count")
        )

        if len(self.q) == len("0000-0003-1240-323X"):
            querysets.append(
                Autor.objects.filter(orcid__icontains=self.q)
                .annotate(Count("wydawnictwo_ciagle"))
                .only("pk", "nazwisko", "imiona", "poprzednie_nazwiska", "tytul__skrot")
                .select_related("tytul")
                .order_by("-wydawnictwo_ciagle__count")
            )

        querysets.append(
            Zrodlo.objects.fulltext_filter(self.q).only(
                "pk", "nazwa", "poprzednia_nazwa"
            )
        )

        rekord_qset = Rekord.objects.fulltext_filter(self.q).only("tytul_oryginalny")

        if hasattr(self, "request") and self.request.user.is_anonymous:
            uczelnia = Uczelnia.objects.get_for_request(self.request)
            if uczelnia is not None:
                rekord_qset = rekord_qset.exclude(
                    status_korekty_id__in=uczelnia.ukryte_statusy("podglad")
                )
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


class StaffRequired(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff


class AdminNavigationAutocomplete(StaffRequired, Select2QuerySetSequenceView):
    paginate_by = 30

    def get_queryset(self):
        if not self.q:
            return []

        querysets = []

        querysets.append(
            BppUser.objects.filter(username__icontains=self.q).only("pk", "username")
        )

        querysets.append(Jednostka.objects.fulltext_filter(self.q).only("pk", "nazwa"))

        querysets.append(
            Konferencja.objects.filter(
                Q(nazwa__icontains=self.q) | Q(skrocona_nazwa__icontains=self.q)
            ).only("pk", "nazwa")
        )

        querysets.append(
            Autor.objects.fulltext_filter(self.q)
            .annotate(Count("wydawnictwo_ciagle"))
            .only("pk", "nazwisko", "imiona", "poprzednie_nazwiska", "tytul")
            .select_related("tytul")
            .order_by("-wydawnictwo_ciagle__count")
        )

        if len(self.q) == len("0000-0003-1240-323X"):
            querysets.append(
                Autor.objects.filter(orcid__icontains=self.q)
                .annotate(Count("wydawnictwo_ciagle"))
                .only("pk", "nazwisko", "imiona", "poprzednie_nazwiska", "tytul__skrot")
                .select_related("tytul")
                .order_by("-wydawnictwo_ciagle__count")
            )

        querysets.append(
            Zrodlo.objects.fulltext_filter(self.q).only(
                "pk", "nazwa", "poprzednia_nazwa"
            )
        )

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

            querysets.append(klass.objects.filter(filter).only("tytul_oryginalny"))

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
