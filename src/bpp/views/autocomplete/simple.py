"""Simple autocomplete views for various models."""

from braces.views import GroupRequiredMixin, LoginRequiredMixin
from dal import autocomplete
from django.contrib.postgres.search import TrigramSimilarity
from django.db.models.query_utils import Q
from django.utils.safestring import mark_safe
from queryset_sequence import QuerySetSequence
from taggit.models import Tag

from bpp.const import GR_WPROWADZANIE_DANYCH, PBN_UID_LEN
from bpp.models import (
    Dyscyplina_Naukowa,
    Kierunek_Studiow,
    Status_Korekty,
    Wydawca,
    Zewnetrzna_Baza_Danych,
)
from bpp.models.cache import Rekord
from bpp.models.konferencja import Konferencja
from bpp.models.nagroda import OrganPrzyznajacyNagrody
from bpp.models.seria_wydawnicza import Seria_Wydawnicza
from bpp.models.struktura import Wydzial
from bpp.models.zrodlo import Rodzaj_Zrodla, Zrodlo
from pbn_api.models import Publisher

from .base import (
    NazwaLubSkrotMixin,
    NazwaMixin,
    NazwaTrigramMixin,
    autocomplete_create_error,
)
from .mixins import SanitizedAutocompleteMixin


class PublicTaggitTagAutocomplete(
    SanitizedAutocompleteMixin, autocomplete.Select2QuerySetView
):
    """Public autocomplete for taggit Tags."""

    create_field = None

    def get_queryset(self):
        qs = Tag.objects.all()
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs


class LataAutocomplete(SanitizedAutocompleteMixin, autocomplete.Select2QuerySetView):
    """Autocomplete for years (lata) from Rekord cache."""

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


class KierunekStudiowAutocomplete(
    SanitizedAutocompleteMixin, autocomplete.Select2QuerySetView
):
    """Autocomplete for study directions."""

    qset = Kierunek_Studiow.objects.all().select_related("wydzial")

    def get_queryset(self):
        qs = self.qset
        if self.q:
            qs = qs.filter(Q(nazwa__icontains=self.q) | Q(skrot__icontains=self.q))
        return qs.order_by("nazwa")


class KonferencjaAutocomplete(
    SanitizedAutocompleteMixin,
    NazwaMixin,
    LoginRequiredMixin,
    autocomplete.Select2QuerySetView,
):
    """Autocomplete for conferences with create capability."""

    create_field = "nazwa"
    qset = Konferencja.objects.all()

    def get_result_label(self, result):
        return f"{Konferencja.TK_SYMBOLE[result.typ_konferencji]} {str(result)}"

    def create_object(self, text):
        return self.get_queryset().create(nazwa=text.strip())


class PublicKonferencjaAutocomplete(
    SanitizedAutocompleteMixin, NazwaMixin, autocomplete.Select2QuerySetView
):
    """Public autocomplete for conferences (no create)."""

    qset = Konferencja.objects.all()


class WydawcaAutocomplete(
    SanitizedAutocompleteMixin,
    NazwaTrigramMixin,
    LoginRequiredMixin,
    autocomplete.Select2QuerySetView,
):
    """Autocomplete for publishers with trigram matching."""

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
    """Autocomplete for PBN Publishers with trigram matching."""

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


class Seria_WydawniczaAutocomplete(
    SanitizedAutocompleteMixin,
    NazwaMixin,
    LoginRequiredMixin,
    autocomplete.Select2QuerySetView,
):
    """Autocomplete for publication series."""

    create_field = "nazwa"
    qset = Seria_Wydawnicza.objects.all()


class WydzialAutocomplete(
    SanitizedAutocompleteMixin, NazwaLubSkrotMixin, autocomplete.Select2QuerySetView
):
    """Autocomplete for departments (wydzialy)."""

    qset = Wydzial.objects.all()


class PublicWydzialAutocomplete(
    SanitizedAutocompleteMixin, NazwaLubSkrotMixin, autocomplete.Select2QuerySetView
):
    """Public autocomplete for visible departments."""

    qset = Wydzial.objects.filter(widoczny=True)


class OrganPrzyznajacyNagrodyAutocomplete(
    SanitizedAutocompleteMixin, NazwaMixin, autocomplete.Select2QuerySetView
):
    """Autocomplete for award-granting organizations."""

    qset = OrganPrzyznajacyNagrody.objects.all()


class PublicStatusKorektyAutocomplete(
    SanitizedAutocompleteMixin, autocomplete.Select2QuerySetView
):
    """Public autocomplete for correction status."""

    def get_queryset(self):
        if self.q:
            return Status_Korekty.objects.filter(nazwa__icontains=self.q)
        return Status_Korekty.objects.all()


class PublicZrodloAutocomplete(
    SanitizedAutocompleteMixin, autocomplete.Select2QuerySetView
):
    """Public autocomplete for sources (zrodla)."""

    # Additional filter fields for subclasses to extend
    extra_filter_fields = ()

    def _get_base_queryset(self):
        """Return the base queryset. Override in subclasses for customization."""
        return Zrodlo.objects.all()

    def _build_token_filter(self, token):
        """Build Q filter for a single search token."""
        qobj = (
            Q(nazwa__icontains=token)
            | Q(poprzednia_nazwa__icontains=token)
            | Q(nazwa_alternatywna__icontains=token)
            | Q(skrot__istartswith=token)
            | Q(skrot_nazwy_alternatywnej__istartswith=token)
        )
        # Add extra filter fields from subclass
        for field in self.extra_filter_fields:
            qobj |= Q(**{f"{field}__icontains": token})
        return qobj

    def get_queryset(self):
        qs = self._get_base_queryset()
        if self.q:
            for token in [x.strip() for x in self.q.split(" ") if x.strip()]:
                qs = qs.filter(self._build_token_filter(token))
        return qs


class ZrodloAutocomplete(GroupRequiredMixin, PublicZrodloAutocomplete):
    """Staff autocomplete for sources with create capability and PBN indicators."""

    create_field = "nazwa"
    group_required = GR_WPROWADZANIE_DANYCH
    extra_filter_fields = ("issn", "e_issn")

    def _get_base_queryset(self):
        return Zrodlo.objects.all().select_related("pbn_uid")

    def get_queryset(self):
        qs = self._get_base_queryset()
        if self.q:
            for token in [x.strip() for x in self.q.split(" ") if x.strip()]:
                qs = qs.filter(self._build_token_filter(token))

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
            res.model = Zrodlo  # django-autocomplete-light needs this
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


class ZrodloAutocompleteNoCreate(ZrodloAutocomplete):
    """Autocomplete for sources without create capability.

    Used in functions where we don't want users to accidentally create new sources.
    """

    create_field = None


class Dyscyplina_NaukowaAutocomplete(
    SanitizedAutocompleteMixin, autocomplete.Select2QuerySetView
):
    """Autocomplete for scientific disciplines."""

    def get_queryset(self):
        qs = Dyscyplina_Naukowa.objects.filter(widoczna=True)
        if self.q:
            qs = qs.filter(Q(nazwa__icontains=self.q) | Q(kod__icontains=self.q))
        return qs


class Zewnetrzna_Baza_DanychAutocomplete(
    SanitizedAutocompleteMixin, autocomplete.Select2QuerySetView
):
    """Autocomplete for external databases."""

    def get_queryset(self):
        qs = Zewnetrzna_Baza_Danych.objects.all()
        if self.q:
            qs = qs.filter(Q(nazwa__icontains=self.q) | Q(skrot__icontains=self.q))
        return qs
