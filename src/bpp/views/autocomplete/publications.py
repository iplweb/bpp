"""Publication-related autocomplete views."""

from braces.views import LoginRequiredMixin
from dal import autocomplete

from bpp.const import CHARAKTER_OGOLNY_KSIAZKA
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte

from .mixins import SanitizedAutocompleteMixin


class Wydawnictwo_NadrzedneAutocomplete(
    SanitizedAutocompleteMixin, autocomplete.Select2QuerySetView
):
    """Autocomplete for parent publications (books only)."""

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
    """Admin autocomplete for continuous publications."""

    def get_queryset(self):
        qs = Wydawnictwo_Ciagle.objects.all()
        if self.q:
            qs = qs.filter(tytul_oryginalny__icontains=self.q)
        return qs


class Wydawnictwo_ZwarteAdminAutocomplete(
    SanitizedAutocompleteMixin, LoginRequiredMixin, autocomplete.Select2QuerySetView
):
    """Admin autocomplete for monographic publications."""

    def get_queryset(self):
        qs = Wydawnictwo_Zwarte.objects.all()
        if self.q:
            qs = qs.filter(tytul_oryginalny__icontains=self.q)
        return qs


class PublicWydawnictwo_NadrzedneAutocomplete(Wydawnictwo_NadrzedneAutocomplete):
    """Public autocomplete for parent publications.

    Only returns publications that are already parent publications for some records.
    """

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
