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


class ZgloszenieJednostkaAutocomplete(PublicJednostkaAutocomplete):
    """Jednostka autora w formularzu zgłaszania prac (FD#640).

    Jak ``PublicJednostkaAutocomplete``, ale z przekazanym (``forward``)
    autorem: autorowi spoza uczelni z requestu podpowiada wyłącznie jednostkę
    obcą (``Uczelnia.obca_jednostka``) — autor spoza uczelni nie może
    dostać w zgłoszeniu jednostki uczelni. Gdy uczelnia nie ma
    skonfigurowanej obcej jednostki, lista jest jak w publicznym
    autocomplete (nie ma czego zaproponować w zamian).
    """

    def _obca_jednostka_dla_autora(self):
        from bpp.models import Autor, Uczelnia

        uczelnia = Uczelnia.objects.get_for_request(self.request)
        if uczelnia is None or uczelnia.obca_jednostka_id is None:
            return None
        try:
            autor = Autor.objects.get(pk=int(self.forwarded.get("autor")))
        except (Autor.DoesNotExist, TypeError, ValueError):
            return None
        if autor.jest_autorem_uczelni(uczelnia):
            return None
        return uczelnia.obca_jednostka

    def get_queryset(self):
        obca = self._obca_jednostka_dla_autora()
        if obca is None:
            return super().get_queryset()
        qs = Jednostka.objects.filter(pk=obca.pk).select_related("wydzial")
        if self.q:
            qs = qs.filter(Q(nazwa__icontains=self.q) | Q(skrot__icontains=self.q))
        return qs


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


class PublicJednostkaWydzialRankinguAutocomplete(
    UczelniaScopedAutocompleteMixin, _JednostkaAutocompleteBase
):
    """Faza B (#438): picker „wydziału" w rankingu autorów — widoczne korzenie
    (``parent IS NULL``), które DOPUSZCZAJĄ ranking (``zezwalaj_na_ranking_
    autorow=True``). Bez filtra ``zezwalaj`` picker oferował wydziały wyłączone
    z rankingu → wybór dawał CICHO pusty wynik (widok odrzuca je w
    ``get_dostepne_wydzialy``). Węższy niż ``…-toplevel-…``; per-uczelnia.
    """

    qset = (
        Jednostka.objects.widoczne()
        .filter(parent__isnull=True, zezwalaj_na_ranking_autorow=True)
        .select_related("wydzial")
    )
