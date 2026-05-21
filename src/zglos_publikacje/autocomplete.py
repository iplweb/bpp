"""Autocomplete views for publication submission form.

Uses QuerySetSequence to combine BPP and PBN data sources.
"""

from dal_select2_queryset_sequence.views import (
    Select2QuerySetSequenceView,
)
from django.contrib.postgres.search import TrigramSimilarity
from django.utils.html import format_html
from queryset_sequence import QuerySetSequence

from bpp.const import CHARAKTER_OGOLNY_KSIAZKA
from bpp.models.wydawca import Wydawca
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from bpp.views.autocomplete.mixins import SanitizedAutocompleteMixin
from pbn_api.models.publication import Publication as PBN_Publication
from pbn_api.models.publisher import Publisher as PBN_Publisher

MIN_TRIGRAM_MATCH = 0.05
MAX_RESULTS = 10


class PublicWydawcaAutocomplete(
    SanitizedAutocompleteMixin, Select2QuerySetSequenceView
):
    """Public autocomplete for publishers.

    Combines results from bpp.Wydawca (local) and
    pbn_api.Publisher (PBN) using QuerySetSequence.
    """

    def get_queryset(self):
        bpp_wydawcy = Wydawca.objects.all()
        pbn_publishers = PBN_Publisher.objects.all()

        if self.q:
            q = self.q.strip()
            bpp_wydawcy = (
                bpp_wydawcy.annotate(similarity=TrigramSimilarity("nazwa", q))
                .filter(similarity__gte=MIN_TRIGRAM_MATCH)
                .order_by("-similarity")[:MAX_RESULTS]
            )

            pbn_publishers = (
                pbn_publishers.annotate(
                    similarity=TrigramSimilarity("publisherName", q)
                )
                .filter(similarity__gte=MIN_TRIGRAM_MATCH)
                .order_by("-similarity")[:MAX_RESULTS]
            )
        else:
            bpp_wydawcy = bpp_wydawcy.none()
            pbn_publishers = pbn_publishers.none()

        qs = QuerySetSequence(bpp_wydawcy, pbn_publishers)
        qs = self.mixup_querysets(qs)
        return qs

    def get_result_label(self, result):
        if isinstance(result, Wydawca):
            return format_html("{} <small>[BPP]</small>", result.nazwa)
        return format_html("{} <small>[PBN]</small>", result.publisherName)

    # NIE nadpisuj `get_result_value` — domyślna implementacja
    # `dal_queryset_sequence.views` zwraca `<ct_pk>-<obj_pk>`, czego
    # oczekuje QSS widget przy POST-cie. Zwrócenie z get_result_value
    # samego label-a sprawia, że <option value="..."> ma w sobie
    # tekst etykiety (HTML!) zamiast referencji do obiektu — i FK
    # nigdy się nie odtworzy w `done()`.


class PublicWydawnictwoNadrzedneAutocomplete(
    SanitizedAutocompleteMixin, Select2QuerySetSequenceView
):
    """Public autocomplete for parent publications (books).

    Combines results from bpp.Wydawnictwo_Zwarte (local books)
    and pbn_api.Publication (PBN publications) using
    QuerySetSequence.
    """

    def get_queryset(self):
        wz = Wydawnictwo_Zwarte.objects.filter(
            charakter_formalny__charakter_ogolny=(CHARAKTER_OGOLNY_KSIAZKA)
        )
        pbn_pub = PBN_Publication.objects.all()

        if self.q:
            q = self.q.strip()
            wz = wz.filter(tytul_oryginalny__icontains=q)[:MAX_RESULTS]
            pbn_pub = pbn_pub.filter(title__icontains=q)[:MAX_RESULTS]
        else:
            wz = wz.none()
            pbn_pub = pbn_pub.none()

        qs = QuerySetSequence(wz, pbn_pub)
        qs = self.mixup_querysets(qs)
        return qs

    def get_result_label(self, result):
        if isinstance(result, Wydawnictwo_Zwarte):
            label = str(result.tytul_oryginalny)
            if result.rok:
                label += f" ({result.rok})"
            return format_html("{} <small>[BPP]</small>", label)

        # PBN_Publication
        label = str(result.title or "")
        if result.year:
            label += f" ({result.year})"
        return format_html("{} <small>[PBN]</small>", label)

    # j.w. — nie nadpisujemy `get_result_value`. Patrz komentarz
    # w `PublicWydawcaAutocomplete`.
