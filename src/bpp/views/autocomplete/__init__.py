import json
from collections import OrderedDict

from braces.views import GroupRequiredMixin, LoginRequiredMixin
from dal import autocomplete
from dal_select2_queryset_sequence.views import Select2QuerySetSequenceView
from django import http
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.postgres.search import TrigramSimilarity
from django.core.exceptions import ImproperlyConfigured
from django.db.models.aggregates import Count
from django.db.models.query_utils import Q
from django.utils.safestring import mark_safe
from django.utils.text import capfirst
from queryset_sequence import QuerySetSequence
from taggit.models import Tag

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
from import_common.core import normalized_db_isbn
from import_common.normalization import normalize_isbn
from pbn_api.models import Publisher

from .mixins import SanitizedAutocompleteMixin  # noqa
from .wydawnictwo_nadrzedne_w_pbn import Wydawnictwo_Nadrzedne_W_PBNAutocomplete  # noqa


class PublicTaggitTagAutocomplete(
    SanitizedAutocompleteMixin, autocomplete.Select2QuerySetView
):
    create_field = None

    def get_queryset(self):
        qs = Tag.objects.all()
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs


class Wydawnictwo_NadrzedneAutocomplete(
    SanitizedAutocompleteMixin, autocomplete.Select2QuerySetView
):
    def get_queryset(self):
        qs = Wydawnictwo_Zwarte.objects.filter(
            charakter_formalny__charakter_ogolny=CHARAKTER_OGOLNY_KSIAZKA
        )

        if self.q:
            qs = qs.filter(tytul_oryginalny__icontains=self.q)
        return qs


class Wydawnictwo_CiagleAdminAutocomplete(
    SanitizedAutocompleteMixin, LoginRequiredMixin, autocomplete.Select2QuerySetView
):
    def get_queryset(self):
        qs = Wydawnictwo_Ciagle.objects.all()
        if self.q:
            qs = qs.filter(tytul_oryginalny__icontains=self.q)
        return qs


class Wydawnictwo_ZwarteAdminAutocomplete(
    SanitizedAutocompleteMixin, LoginRequiredMixin, autocomplete.Select2QuerySetView
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


class JednostkaMixin:
    def get_result_label(self, result):
        if result is not None:
            return str(result)


class JednostkaAutocomplete(
    SanitizedAutocompleteMixin, JednostkaMixin, autocomplete.Select2QuerySetView
):
    qset = Jednostka.objects.all().select_related("wydzial")

    def get_queryset(self):
        qs = self.qset
        if self.q:
            qs = qs.filter(Q(nazwa__icontains=self.q) | Q(skrot__icontains=self.q))
        return qs.order_by(*Jednostka.objects.get_default_ordering())


class KierunekStudiowAutocomplete(
    SanitizedAutocompleteMixin, autocomplete.Select2QuerySetView
):
    qset = Kierunek_Studiow.objects.all().select_related("wydzial")

    def get_queryset(self):
        qs = self.qset
        if self.q:
            qs = qs.filter(Q(nazwa__icontains=self.q) | Q(skrot__icontains=self.q))
        return qs.order_by("nazwa")


class LataAutocomplete(SanitizedAutocompleteMixin, autocomplete.Select2QuerySetView):
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
    SanitizedAutocompleteMixin,
    NazwaMixin,
    LoginRequiredMixin,
    autocomplete.Select2QuerySetView,
):
    create_field = "nazwa"
    qset = Konferencja.objects.all()

    def get_result_label(self, result):
        return f"{Konferencja.TK_SYMBOLE[result.typ_konferencji]} {str(result)}"

    def create_object(self, text):
        return self.get_queryset().create(nazwa=text.strip())


class WydawcaAutocomplete(
    SanitizedAutocompleteMixin,
    NazwaTrigramMixin,
    LoginRequiredMixin,
    autocomplete.Select2QuerySetView,
):
    create_field = "nazwa"
    qset = Wydawca.objects.all()

    def create_object(self, text):
        return self.get_queryset().create(nazwa=text.strip())


class PublisherAutocomplete(
    SanitizedAutocompleteMixin,
    NazwaTrigramMixin,
    LoginRequiredMixin,
    autocomplete.Select2QuerySetView,
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


class PublicKonferencjaAutocomplete(
    SanitizedAutocompleteMixin, NazwaMixin, autocomplete.Select2QuerySetView
):
    qset = Konferencja.objects.all()


class Seria_WydawniczaAutocomplete(
    SanitizedAutocompleteMixin,
    NazwaMixin,
    LoginRequiredMixin,
    autocomplete.Select2QuerySetView,
):
    create_field = "nazwa"
    qset = Seria_Wydawnicza.objects.all()


class WydzialAutocomplete(
    SanitizedAutocompleteMixin, NazwaLubSkrotMixin, autocomplete.Select2QuerySetView
):
    qset = Wydzial.objects.all()


class PublicWydzialAutocomplete(
    SanitizedAutocompleteMixin, NazwaLubSkrotMixin, autocomplete.Select2QuerySetView
):
    qset = Wydzial.objects.filter(widoczny=True)


class OrganPrzyznajacyNagrodyAutocomplete(
    SanitizedAutocompleteMixin, NazwaMixin, autocomplete.Select2QuerySetView
):
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


class PublicZrodloAutocomplete(
    SanitizedAutocompleteMixin, autocomplete.Select2QuerySetView
):
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

    def get_queryset(self):
        qs = Zrodlo.objects.all().select_related("pbn_uid")
        if self.q:
            for token in [x.strip() for x in self.q.split(" ") if x.strip()]:
                qs = qs.filter(
                    Q(nazwa__icontains=token)
                    | Q(poprzednia_nazwa__icontains=token)
                    | Q(nazwa_alternatywna__icontains=token)
                    | Q(skrot__istartswith=token)
                    | Q(skrot_nazwy_alternatywnej__istartswith=token)
                    | Q(issn__icontains=token)
                    | Q(e_issn__icontains=token)
                )

            # Prioritize sources with PBN identifiers (both pbn_uid and mniswId)
            qs_with_full_pbn = qs.filter(
                pbn_uid__isnull=False, pbn_uid__mniswId__isnull=False
            )[:10]
            qs_with_pbn_no_mnisw = qs.filter(
                pbn_uid__isnull=False, pbn_uid__mniswId__isnull=True
            )[:10]
            qs_without_pbn = qs.filter(pbn_uid__isnull=True)[:10]

            # Use QuerySetSequence to chain querysets with priority
            res = QuerySetSequence(
                qs_with_full_pbn, qs_with_pbn_no_mnisw, qs_without_pbn
            )
            res.model = Zrodlo  # django-autocomplete-light tego potrzebuje
            return res

        return qs

    def get_result_label(self, result):
        parts = [str(result.nazwa)]

        # Add ISSN/E-ISSN if available
        issn_parts = []
        if result.issn:
            issn_parts.append(f"ISSN: {result.issn}")
        if result.e_issn:
            issn_parts.append(f"E-ISSN: {result.e_issn}")
        if issn_parts:
            parts.append(f"[{', '.join(issn_parts)}]")

        # Add indicator for sources with MNiSW identifier
        if result.pbn_uid_id:
            parts.append("📚 PBN")
            if hasattr(result, "pbn_uid") and result.pbn_uid:
                if result.pbn_uid.mniswId:
                    # Using Foundation Icon for ministry/government building
                    parts.append("🏛️ MNiSW")

        return mark_safe(" ".join(parts))

    def create_object(self, text):
        try:
            rz = Rodzaj_Zrodla.objects.get(nazwa="periodyk")
        except Rodzaj_Zrodla.DoesNotExist:
            return autocomplete_create_error(
                "Nie można utworzyć źródła - brak zdefiniowanego"
                " rodzaju źródła 'periodyk'"
            )

        return self.get_queryset().create(nazwa=text.strip(), rodzaj=rz)


class AutorAutocompleteBase(
    SanitizedAutocompleteMixin, autocomplete.Select2QuerySetView
):
    def get_queryset(self):
        if self.q:
            return Autor.objects.fulltext_filter(self.q).select_related("tytul")
        return Autor.objects.all()


class PublicStatusKorektyAutocomplete(
    SanitizedAutocompleteMixin, autocomplete.Select2QuerySetView
):
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


class GlobalNavigationAutocomplete(
    SanitizedAutocompleteMixin, Select2QuerySetSequenceView
):
    paginate_by = 40

    def get_result_label(self, result):
        if isinstance(result, Autor):
            if result.aktualna_funkcja_id is not None:
                return str(result) + ", " + str(result.aktualna_funkcja.nazwa)
        elif isinstance(result, Rekord):
            return result.opis_bibliograficzny_cache
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
                Rekord.objects.extra(where=[f"id[2]={this_is_an_id}"]).only(
                    "tytul_oryginalny"
                )
            )

        ret = QuerySetSequence(*querysets)
        return self.mixup_querysets(ret)


class DjangoApp:
    """Pseudo-model representing a Django app in search results"""

    def __init__(self, app_label, verbose_name, app_url):
        self.pk = f"app:{app_label}"
        self.app_label = app_label
        self.verbose_name = verbose_name
        self.app_url = app_url

    def __str__(self):
        return self.verbose_name


class DjangoModel:
    """Pseudo-model representing a Django model in search results"""

    def __init__(
        self,
        app_label,
        model_name,
        verbose_name,
        changelist_url,
        add_url=None,
        can_add=False,
        is_add_action=False,
    ):
        # Distinguish between list and add actions in the pk
        action_suffix = ":add" if is_add_action else ""
        self.pk = f"model:{app_label}:{model_name}{action_suffix}"
        self.app_label = app_label
        self.model_name = model_name
        self.verbose_name = verbose_name
        self.changelist_url = changelist_url
        self.add_url = add_url
        self.can_add = can_add
        self.is_add_action = is_add_action

    def __str__(self):
        if self.is_add_action:
            return f"Dodaj {self.verbose_name.lower()}"
        return self.verbose_name


class AdminNavigationAutocomplete(
    SanitizedAutocompleteMixin, StaffRequired, Select2QuerySetSequenceView
):
    paginate_by = 60

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.django_items = []

    def get_result_value(self, result):
        """Get the value to use for the result's ID"""
        if isinstance(result, DjangoApp | DjangoModel):
            return result.pk
        return super().get_result_value(result)

    def get_result_label(self, result):
        """Format the display of results in the dropdown"""
        if isinstance(result, DjangoApp):
            return f"📁 {result.verbose_name}"
        elif isinstance(result, DjangoModel):
            if result.is_add_action:
                return f"➕ Dodaj {result.verbose_name.lower()}"
            return f"📄 {result.verbose_name}"

        # Default handling for other types
        return super().get_result_label(result)

    def get_model_name(self, model):
        """Return the display name for grouping results"""
        if model == DjangoApp:
            return "Aplikacje modułu redagowania"
        elif model == DjangoModel:
            return "Modele modułu redagowania"

        # Default handling for other types
        return super().get_model_name(model)

    def get_results(self, context):
        """Override to include Django items in the results"""
        # Get regular results from parent class
        results = super().get_results(context)

        # If we have Django items, add them to the results
        if self.django_items:
            # Group Django items by type
            apps = [item for item in self.django_items if isinstance(item, DjangoApp)]
            models = [
                item for item in self.django_items if isinstance(item, DjangoModel)
            ]

            # Add Django apps group
            if apps:
                results.append(
                    {
                        "id": None,
                        "text": "Aplikacje Django",
                        "children": [
                            {
                                "id": self.get_result_value(app),
                                "text": self.get_result_label(app),
                            }
                            for app in apps
                        ],
                    }
                )

            # Add Django models group
            if models:
                results.append(
                    {
                        "id": None,
                        "text": "Modele Django",
                        "children": [
                            {
                                "id": self.get_result_value(model),
                                "text": self.get_result_label(model),
                            }
                            for model in models
                        ],
                    }
                )

        return results

    def _check_model_permissions(self, user, app_label, model_name):
        """Check permissions for a model and return permission dict"""
        return {
            "view": user.has_perm(f"{app_label}.view_{model_name}"),
            "add": user.has_perm(f"{app_label}.add_{model_name}"),
            "change": user.has_perm(f"{app_label}.change_{model_name}"),
            "delete": user.has_perm(f"{app_label}.delete_{model_name}"),
        }

    def _model_matches_query(self, model):
        """Check if model matches the search query"""
        model_verbose_name = model._meta.verbose_name_plural
        model_verbose_name_singular = model._meta.verbose_name
        q_lower = self.q.lower()
        return (
            q_lower in model_verbose_name.lower()
            or q_lower in model._meta.model_name.lower()
            or q_lower in model_verbose_name_singular.lower()
        )

    def _add_model_entries(self, results, model, perms, changelist_url, add_url):
        """Add model entries to results if they match the search query"""
        from django.utils.text import capfirst

        if not self._model_matches_query(model):
            return

        app_label = model._meta.app_label
        model_verbose_name = model._meta.verbose_name_plural
        model_verbose_name_singular = model._meta.verbose_name

        # Add entry for model list (changelist)
        django_model = DjangoModel(
            app_label=app_label,
            model_name=model._meta.model_name,
            verbose_name=capfirst(model_verbose_name),
            changelist_url=changelist_url,
            add_url=add_url,
            can_add=perms["add"],
            is_add_action=False,
        )
        results.append(django_model)

        # Add separate entry for adding new instance if user has permission
        if perms["add"]:
            django_model_add = DjangoModel(
                app_label=app_label,
                model_name=model._meta.model_name,
                verbose_name=capfirst(model_verbose_name_singular),
                changelist_url=changelist_url,
                add_url=add_url,
                can_add=True,
                is_add_action=True,
            )
            results.append(django_model_add)

    def get_django_apps_and_models(self):
        """Get Django apps and models accessible to the current user"""
        from django.apps import apps
        from django.contrib import admin
        from django.urls import reverse
        from django.utils.text import capfirst

        results = []

        if not hasattr(self, "request"):
            return results

        user = self.request.user
        admin_site = admin.site
        app_dict = {}

        for model, _model_admin in admin_site._registry.items():
            app_label = model._meta.app_label

            # Check if user has any permission for this model
            if not user.has_module_perms(app_label):
                continue

            # Check specific permissions
            perms = self._check_model_permissions(
                user, app_label, model._meta.model_name
            )

            # Skip if no view permission
            if not perms["view"] and not perms["change"]:
                continue

            # Get URLs
            changelist_url = reverse(
                f"admin:{app_label}_{model._meta.model_name}_changelist"
            )
            add_url = None
            if perms["add"]:
                add_url = reverse(f"admin:{app_label}_{model._meta.model_name}_add")

            # Add model entries to results if they match the search query
            self._add_model_entries(results, model, perms, changelist_url, add_url)

            # Build app dict for app-level search
            if app_label not in app_dict:
                app_config = apps.get_app_config(app_label)
                app_dict[app_label] = {
                    "name": capfirst(app_config.verbose_name),
                    "app_label": app_label,
                    "app_url": reverse(
                        "admin:app_list", kwargs={"app_label": app_label}
                    ),
                    "has_models": True,
                }

        # Add matching apps to results
        for app_label, app_info in app_dict.items():
            if (
                self.q.lower() in app_info["name"].lower()
                or self.q.lower() in app_label.lower()
            ):
                django_app = DjangoApp(
                    app_label=app_label,
                    verbose_name=app_info["name"],
                    app_url=app_info["app_url"],
                )
                results.append(django_app)

        return results

    def _build_publication_filter(self, klass):
        """Build filter for publication models"""
        query_filter = Q(tytul_oryginalny__icontains=self.q)

        # Try to add primary key filter if q is an integer
        try:
            int(self.q)
            query_filter |= Q(pk=self.q)
        except (TypeError, ValueError):
            pass

        # Add DOI filter for non-Patent models
        if klass != Patent:
            query_filter |= Q(doi__iexact=self.q)

        # Add PBN UID filter if applicable
        if len(self.q) == 24 and self.q.find(" ") == -1:
            if "pbn_uid" in [fld.name for fld in klass._meta.fields]:
                query_filter |= Q(pbn_uid__pk=self.q)

        return query_filter

    def _add_publication_querysets(self, querysets):
        """Add querysets for publication models"""
        for klass in [
            Wydawnictwo_Zwarte,
            Wydawnictwo_Ciagle,
            Patent,
            Praca_Doktorska,
            Praca_Habilitacyjna,
        ]:
            query_filter = self._build_publication_filter(klass)

            # Handle ISBN normalization if applicable
            annotate_isbn = False
            if hasattr(klass, "isbn"):
                ni = normalize_isbn(self.q)
                if len(ni) < 20:
                    query_filter |= Q(normalized_isbn=ni)
                    annotate_isbn = True

            if annotate_isbn:
                qset = klass.objects.annotate(
                    normalized_isbn=normalized_db_isbn
                ).filter(query_filter)
            else:
                qset = klass.objects.filter(query_filter)

            querysets.append(qset.only("tytul_oryginalny"))

    def get_queryset(self):
        if not self.q or len(self.q) < 1:
            return []

        querysets = []

        # Add user queryset
        querysets.append(
            BppUser.objects.filter(username__icontains=self.q).only("pk", "username")
        )

        # Add organizational units and other querysets
        globalne_wyszukiwanie_jednostki(querysets, self.q)

        querysets.append(
            Konferencja.objects.filter(
                Q(nazwa__icontains=self.q) | Q(skrocona_nazwa__icontains=self.q)
            ).only("pk", "nazwa", "baza_inna", "baza_wos", "baza_scopus")
        )

        globalne_wyszukiwanie_autora(querysets, self.q)
        globalne_wyszukiwanie_zrodla(querysets, self.q)

        # Add publication querysets
        self._add_publication_querysets(querysets)

        # Store Django apps and models separately (don't add to QuerySetSequence)
        self.django_items = self.get_django_apps_and_models()

        ret = QuerySetSequence(*querysets)
        return self.mixup_querysets(ret)


class ZapisanyJakoAutocomplete(
    SanitizedAutocompleteMixin, autocomplete.Select2ListView
):
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


class PodrzednaPublikacjaHabilitacyjnaAutocomplete(
    SanitizedAutocompleteMixin, Select2QuerySetSequenceView
):
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


class Dyscyplina_NaukowaAutocomplete(
    SanitizedAutocompleteMixin, autocomplete.Select2QuerySetView
):
    def get_queryset(self):
        qs = Dyscyplina_Naukowa.objects.filter(widoczna=True)
        if self.q:
            qs = qs.filter(Q(nazwa__icontains=self.q) | Q(kod__icontains=self.q))
        return qs


class Zewnetrzna_Baza_DanychAutocomplete(
    SanitizedAutocompleteMixin, autocomplete.Select2QuerySetView
):
    def get_queryset(self):
        qs = Zewnetrzna_Baza_Danych.objects.all()
        if self.q:
            qs = qs.filter(Q(nazwa__icontains=self.q) | Q(skrot__icontains=self.q))
        return qs


class Dyscyplina_Naukowa_PrzypisanieAutocomplete(
    SanitizedAutocompleteMixin, autocomplete.Select2ListView
):
    def results(self, results):
        """Return data for the 'results' key of the response."""
        return [{"id": _id, "text": value} for _id, value in results]

    def autocomplete_results(self, results):
        return [(x, y) for x, y in results if self.q.lower() in y.lower()]

    def _validate_autor(self, autor):
        """Validate and convert autor parameter"""
        if autor is None or not isinstance(autor, str) or not autor.strip():
            return None, "Podaj autora"

        try:
            return int(autor), None
        except (TypeError, ValueError):
            return None, "Nieprawidłowe ID autora"

    def _validate_rok(self, rok):
        """Validate and convert rok parameter"""
        if rok is None:
            return None, "Podaj rok"

        try:
            rok_int = int(rok)
        except (TypeError, ValueError):
            return None, "Nieprawidłowy rok"

        if rok_int < 0 or rok_int > 9999:
            return None, "Nieprawidłowy rok"

        return rok_int, None

    def _get_disciplines_for_autor(self, autor, rok):
        """Get disciplines for the given autor and rok"""
        try:
            ad = Autor_Dyscyplina.objects.get(rok=rok, autor=autor)
        except Autor_Dyscyplina.DoesNotExist:
            return None, f"Brak przypisania dla roku {rok}"

        res = set()
        for elem in ["dyscyplina_naukowa", "subdyscyplina_naukowa"]:
            disc_id = getattr(ad, f"{elem}_id")
            if disc_id is not None:
                res.add((disc_id, getattr(ad, elem).nazwa))

        res = list(res)
        res.sort(key=lambda obj: obj[1])
        return res, None

    def get_list(self):
        # Validate autor
        autor, error = self._validate_autor(self.forwarded.get("autor", None))
        if error:
            return [(None, error)]

        # Validate rok
        rok, error = self._validate_rok(self.forwarded.get("rok", None))
        if error:
            return [(None, error)]

        # Get disciplines
        disciplines, error = self._get_disciplines_for_autor(autor, rok)
        if error:
            return [(None, error)]

        return disciplines
