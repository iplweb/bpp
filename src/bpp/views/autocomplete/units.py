"""Jednostka (unit) autocomplete views."""

from dal import autocomplete
from django.db.models.query_utils import Q

from bpp.models import Jednostka

from .base import JednostkaMixin
from .mixins import SanitizedAutocompleteMixin


class JednostkaAutocomplete(
    SanitizedAutocompleteMixin, JednostkaMixin, autocomplete.Select2QuerySetView
):
    """Autocomplete for organizational units (jednostki)."""

    qset = Jednostka.objects.all().select_related("wydzial")

    def get_queryset(self):
        qs = self.qset
        if self.q:
            qs = qs.filter(Q(nazwa__icontains=self.q) | Q(skrot__icontains=self.q))
        return qs.order_by(*Jednostka.objects.get_default_ordering())


class WidocznaJednostkaAutocomplete(JednostkaAutocomplete):
    """Autocomplete for visible organizational units."""

    qset = Jednostka.objects.widoczne().select_related("wydzial")


class PublicJednostkaAutocomplete(JednostkaAutocomplete):
    """Public autocomplete for public organizational units."""

    qset = Jednostka.objects.publiczne().select_related("wydzial")
