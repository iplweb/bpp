"""HTTP 410 Gone for public URLs of records that sit in the trash ("kosz").

A trashed record is hidden by the default manager, so a plain lookup misses
and the view would answer 404. For a record that DID exist and was moved to
the trash the honest answer is 410 Gone: search engines drop the URL faster
and visitors learn that the record was removed on purpose, not mistyped.

Contract:

- the fallback lookup in ``deleted_objects`` runs ONLY after a miss in the
  default manager -- live records pay nothing extra;
- a URL that never existed, or a record purged from the trash (hard delete),
  keeps the normal 404;
- the 410 page never shows any of the record's content (title, authors,
  dates, slug) -- only a generic message worded for the record type.

Views raise :class:`RekordUsuniety`; ``bpp.middleware.RekordUsunietyMiddleware``
turns it into the rendered 410 page.
"""

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.http import Http404

_NIEDOSTEPNA = "została usunięta i nie jest już dostępna."
_NIEDOSTEPNY = "został usunięty i nie jest już dostępny."
_NIEDOSTEPNE = "zostało usunięte i nie jest już dostępne."
_PUBLIKACJA = f"Publikacja, której szukasz, {_NIEDOSTEPNA}"

#: Per-type sentence shown under the generic heading. Keys are
#: ``Model._meta.model_name``; other models get ``KOMUNIKAT_DOMYSLNY``.
KOMUNIKATY = {
    "wydawnictwo_ciagle": _PUBLIKACJA,
    "wydawnictwo_zwarte": _PUBLIKACJA,
    "patent": _PUBLIKACJA,
    "praca_doktorska": _PUBLIKACJA,
    "praca_habilitacyjna": _PUBLIKACJA,
    "autor": f"Autor, którego szukasz, {_NIEDOSTEPNY}",
    "zrodlo": f"Źródło, którego szukasz, {_NIEDOSTEPNE}",
    "wydawca": f"Wydawca, którego szukasz, {_NIEDOSTEPNY}",
    "konferencja": f"Konferencja, której szukasz, {_NIEDOSTEPNA}",
    "seria_wydawnicza": f"Seria wydawnicza, której szukasz, {_NIEDOSTEPNA}",
    "uczelnia": f"Uczelnia, której szukasz, {_NIEDOSTEPNA}",
}

KOMUNIKAT_DOMYSLNY = f"Rekord, którego szukasz, {_NIEDOSTEPNY}"


class RekordUsuniety(Exception):
    """The requested record exists, but only in the trash -> HTTP 410."""

    def __init__(self, model=None):
        super().__init__(getattr(getattr(model, "_meta", None), "model_name", None))
        self.model = model

    @property
    def komunikat(self):
        model_name = getattr(getattr(self.model, "_meta", None), "model_name", None)
        return KOMUNIKATY.get(model_name, KOMUNIKAT_DOMYSLNY)


def rzuc_jesli_w_koszu(queryset, **lookup):
    """Raise :class:`RekordUsuniety` when ``queryset`` (built on
    ``deleted_objects``) has a row matching ``lookup``. Call ONLY after the
    regular lookup missed. Models without a trash are silently ignored."""
    if queryset is None or not lookup:
        return
    if queryset.filter(**lookup).exists():
        raise RekordUsuniety(queryset.model)


def kosz_modelu(model):
    """``deleted_objects`` queryset of ``model`` or ``None`` (no trash)."""
    manager = getattr(model, "deleted_objects", None)
    return manager.all() if manager is not None else None


def modele_publikacji():
    """The five soft-deletable publication models (WC/WZ/patent/theses)."""
    from bpp.models.soft_delete import BppPublikacjaSoftDeleteMixin

    return [
        m
        for m in apps.get_app_config("bpp").get_models()
        if issubclass(m, BppPublikacjaSoftDeleteMixin)
    ]


def rzuc_jesli_publikacja_w_koszu_po_slugu(slug):
    """Raise :class:`RekordUsuniety` if a trashed publication has ``slug``.

    Trashed publications drop out of ``bpp_rekord_mat`` (``Rekord``), but
    their own table keeps the denormalised (unique, indexed) slug."""
    for model in modele_publikacji():
        rzuc_jesli_w_koszu(model.deleted_objects.all(), slug=slug)


def rzuc_jesli_obiekt_w_koszu(content_type_id, object_id):
    """Raise :class:`RekordUsuniety` if the object addressed by a
    ``(content_type_id, object_id)`` pair is in the trash."""
    try:
        model = ContentType.objects.get_for_id(int(content_type_id)).model_class()
    except (ContentType.DoesNotExist, TypeError, ValueError):
        return  # unknown content type -> the caller answers 404
    if model is None:
        return  # stale content type (model removed) -> 404
    rzuc_jesli_w_koszu(kosz_modelu(model), pk=object_id)


class RekordUsunietyDetailMixin:
    """``DetailView`` mixin: a 404 from ``get_object`` becomes 410 when the
    same pk/slug resolves to a trashed record.

    Override :meth:`get_queryset_kosza` to apply the same visibility rules
    as ``get_queryset`` (e.g. hidden author pages stay 404)."""

    def get_queryset_kosza(self):
        return kosz_modelu(self.model)

    def get_object(self, queryset=None):
        try:
            return super().get_object(queryset)
        except Http404:
            pk = self.kwargs.get(self.pk_url_kwarg)
            slug = self.kwargs.get(self.slug_url_kwarg)
            if pk is not None:
                rzuc_jesli_w_koszu(self.get_queryset_kosza(), pk=pk)
            elif slug is not None:
                rzuc_jesli_w_koszu(
                    self.get_queryset_kosza(), **{self.get_slug_field(): slug}
                )
            raise
