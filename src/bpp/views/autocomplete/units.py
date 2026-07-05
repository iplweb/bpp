"""Jednostka (unit) autocomplete views."""

from braces.views import LoginRequiredMixin
from dal import autocomplete
from django.db.models.query_utils import Q

from bpp.models import Jednostka

from .base import JednostkaMixin
from .mixins import SanitizedAutocompleteMixin, UczelniaScopedAutocompleteMixin


class _JednostkaAutocompleteBase(
    SanitizedAutocompleteMixin, JednostkaMixin, autocomplete.Select2QuerySetView
):
    """Shared query logic for jednostka autocompletes.

    Not bound to any URL directly -- see `JednostkaAutocomplete` (editor,
    login-gated) and `WidocznaJednostkaAutocomplete` /
    `PublicJednostkaAutocomplete` (public, ungated) below.
    """

    qset = Jednostka.objects.all().select_related("wydzial")

    def get_queryset(self):
        qs = self.qset
        if self.q:
            qs = qs.filter(Q(nazwa__icontains=self.q) | Q(skrot__icontains=self.q))
        return qs.order_by(*Jednostka.objects.get_default_ordering())


class JednostkaAutocomplete(LoginRequiredMixin, _JednostkaAutocompleteBase):
    """Editor-only autocomplete for organizational units (jednostki).

    Bound to `jednostka-autocomplete`, used by django-admin widgets
    (bpp/admin/core.py, autor.py, praca_doktorska.py,
    praca_habilitacyjna.py) and other editor-only forms. Returns `.all()`
    -- including `widoczna=False` units -- on purpose, because editors
    must be able to assign an author/work to a historical (hidden) unit.
    That means hidden units would leak to anonymous users if this view
    were not gated, so it requires login (see #438). It is deliberately
    NOT the base class for the public variants below
    (WidocznaJednostkaAutocomplete / PublicJednostkaAutocomplete), which
    inherit from `_JednostkaAutocompleteBase` directly so they stay
    anonymous-accessible.
    """


class WidocznaJednostkaAutocomplete(
    UczelniaScopedAutocompleteMixin, _JednostkaAutocompleteBase
):
    """Autocomplete for visible organizational units (per-uczelnia, multi-hosted).

    Bound to `jednostka-widoczna-autocomplete`, used by the (anonymous)
    multiseek search -- must stay accessible without login, so it inherits
    from the ungated `_JednostkaAutocompleteBase`, not `JednostkaAutocomplete`.
    """

    qset = Jednostka.objects.widoczne().select_related("wydzial")


class PublicJednostkaAutocomplete(
    UczelniaScopedAutocompleteMixin, _JednostkaAutocompleteBase
):
    """Public autocomplete for public organizational units (per-uczelnia, multi-hosted)."""

    qset = Jednostka.objects.publiczne().select_related("wydzial")


class PublicJednostkaToplevelAutocomplete(
    UczelniaScopedAutocompleteMixin, _JednostkaAutocompleteBase
):
    """Faza B (#438): publiczny autocomplete jednostek TOP-LEVEL (``parent IS
    NULL``) — czyli „wydziałów" w nowym modelu. Zawężony per-uczelnia i do
    widocznych węzłów. Zastępuje dawny ``public-wydzial-autocomplete`` jako
    picker „wydziału" w raportach/multiseeku.
    """

    qset = (
        Jednostka.objects.widoczne()
        .filter(parent__isnull=True)
        .select_related("wydzial")
    )


class PublicJednostkaNieToplevelAutocomplete(
    UczelniaScopedAutocompleteMixin, _JednostkaAutocompleteBase
):
    """Faza B (#438): publiczny autocomplete jednostek NIE-TOP-LEVEL
    (``parent IS NOT NULL``) — czyli „jednostek" (nie „wydziałów") w nowym
    modelu. Używany jako picker „jednostki" w raportach uczelni, które
    UŻYWAJĄ wydziałów: wydziały (korzenie) wybiera się osobnym selektorem
    „wydział", więc lista „jednostka" nie powinna ich pokazywać (inaczej
    użytkownik wybrałby korzeń, który waliduje się jako „nie do wyboru",
    bo prace ma tylko w poddrzewie — nie bezpośrednio).
    """

    qset = (
        Jednostka.objects.publiczne()
        .filter(parent__isnull=False)
        .select_related("wydzial")
    )
