"""Author-related autocomplete views."""

import json
from collections import OrderedDict

from braces.views import GroupRequiredMixin
from dal import autocomplete
from dal_select2_queryset_sequence.views import Select2QuerySetSequenceView
from django import http
from django.core.exceptions import ImproperlyConfigured
from django.utils.safestring import mark_safe
from queryset_sequence import QuerySetSequence

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.jezyk_polski import warianty_zapisanego_nazwiska
from bpp.models import Autor_Dyscyplina
from bpp.models.autor import Autor, Autor_Jednostka
from bpp.models.patent import Patent, Patent_Autor
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte, Wydawnictwo_Zwarte_Autor
from pbn_api.models import OsobaZInstytucji

from .base import autocomplete_create_error
from .mixins import SanitizedAutocompleteMixin


class AutorAutocompleteBase(
    SanitizedAutocompleteMixin, autocomplete.Select2QuerySetView
):
    """Base autocomplete for authors with PBN indicators."""

    GROUP_NASZA_UCZELNIA = 1
    GROUP_HISTORYCZNIE = 2
    GROUP_ZEWNETRZNI = 3

    GROUP_LABELS = {
        GROUP_NASZA_UCZELNIA: "✅ Autorzy z naszej uczelni",
        GROUP_HISTORYCZNIE: "🏛️ Autorzy powiązani historycznie z naszą uczelnią",
        GROUP_ZEWNETRZNI: "🌐 Autorzy zewnętrzni",
    }

    def get_queryset(self):
        from django.db.models import (
            Case,
            Exists,
            IntegerField,
            OuterRef,
            Value,
            When,
        )

        if self.q:
            qs = Autor.objects.fulltext_filter(self.q)
        else:
            qs = Autor.objects.all()

        qs = qs.select_related("tytul", "pbn_uid").annotate(
            ma_osobe_z_instytucji=Exists(
                OsobaZInstytucji.objects.filter(personId_id=OuterRef("pbn_uid_id"))
            )
        )

        uczelnia = getattr(getattr(self, "request", None), "_uczelnia", None)
        if uczelnia:
            ma_jednostke_w_naszej = Exists(
                Autor_Jednostka.objects.filter(
                    autor=OuterRef("pk"),
                    jednostka__uczelnia=uczelnia,
                )
            )
            qs = qs.annotate(
                ma_jednostke_w_naszej=ma_jednostke_w_naszej,
                grupa_uczelnia=Case(
                    When(
                        aktualna_jednostka__uczelnia=uczelnia,
                        then=Value(self.GROUP_NASZA_UCZELNIA),
                    ),
                    When(
                        ma_jednostke_w_naszej=True,
                        then=Value(self.GROUP_HISTORYCZNIE),
                    ),
                    default=Value(self.GROUP_ZEWNETRZNI),
                    output_field=IntegerField(),
                ),
            ).order_by("grupa_uczelnia", "nazwisko", "imiona")

        return qs

    def get_results(self, context):
        """Group authors into optgroups by their relation to the current uczelnia."""
        uczelnia = getattr(getattr(self, "request", None), "_uczelnia", None)
        if uczelnia is None:
            return super().get_results(context)

        groups = OrderedDict((grp_no, []) for grp_no in self.GROUP_LABELS)
        for result in context["object_list"]:
            grp_no = getattr(result, "grupa_uczelnia", self.GROUP_ZEWNETRZNI)
            groups.setdefault(grp_no, []).append(result)

        output = []
        for grp_no, items in groups.items():
            if not items:
                continue
            output.append(
                {
                    "id": None,
                    "text": self.GROUP_LABELS.get(grp_no, ""),
                    "children": [
                        {
                            "id": self.get_result_value(r),
                            "text": self.get_result_label(r),
                            "selected_text": self.get_selected_result_label(r),
                        }
                        for r in items
                    ],
                }
            )
        return output

    def get_result_label(self, result):
        # Handle error objects or non-Autor instances
        if not isinstance(result, Autor):
            return str(result)

        parts = []

        # Add deletion status prefix if author is deleted in PBN
        if result.pbn_uid_id and hasattr(result, "pbn_uid") and result.pbn_uid:
            if result.pbn_uid.status == "DELETED":
                parts.append("[❌ USUNIĘTY]")

        # Add base author name
        parts.append(str(result))

        # Add PBN indicator if author has pbn_uid
        if result.pbn_uid_id:
            parts.append("📚 PBN")
            # Add MNISW indicator if person exists in OsobaZInstytucji
            if (
                hasattr(result, "ma_osobe_z_instytucji")
                and result.ma_osobe_z_instytucji
            ):
                parts.append("🏛️ MNISW")

        return mark_safe(" ".join(parts))


class AutorAutocomplete(GroupRequiredMixin, AutorAutocompleteBase):
    """Staff autocomplete for authors with create capability."""

    create_field = "nonzero"
    group_required = GR_WPROWADZANIE_DANYCH

    err = autocomplete_create_error(
        "Wpisz nazwisko, potem imiona. Wyrazy oddziel spacją. "
    )

    def create_object(self, text):
        try:
            obj = Autor.objects.create_from_string(text)
        except ValueError:
            return self.err

        from django.contrib.admin.models import ADDITION, LogEntry
        from django.contrib.contenttypes.models import ContentType

        try:
            LogEntry.objects.create(
                user_id=self.request.user.pk,
                content_type_id=ContentType.objects.get_for_model(Autor).pk,
                object_id=str(obj.pk),
                object_repr=str(obj)[:200],
                action_flag=ADDITION,
                change_message="Utworzono z formularza autocomplete",
            )
        except (AttributeError, TypeError):
            pass

        return obj


class PublicAutorAutocomplete(AutorAutocompleteBase):
    """Public autocomplete for authors (no create, no PBN/MNISW markers)."""

    def get_result_label(self, result):
        """Return clean author name without PBN/MNISW markers."""
        return str(result)


class AutorZUczelniAutocopmlete(AutorAutocomplete):
    """Autocomplete for authors from the institution."""

    pass


class ZapisanyJakoAutocomplete(
    SanitizedAutocompleteMixin, autocomplete.Select2ListView
):
    """Autocomplete for 'zapisany jako' field - author name variants."""

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
    """Autocomplete for subordinate publications in habilitation proceedings."""

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


class Dyscyplina_Naukowa_PrzypisanieAutocomplete(
    SanitizedAutocompleteMixin, autocomplete.Select2ListView
):
    """Autocomplete for discipline assignment based on author and year."""

    def results(self, results):
        """Return data for the 'results' key of the response."""
        return [{"id": _id, "text": value} for _id, value in results]

    def autocomplete_results(self, results):
        return [(x, y) for x, y in results if self.q.lower() in y.lower()]

    def _validate_autor(self, autor):
        """Validate and convert autor parameter."""
        if autor is None or not isinstance(autor, str) or not autor.strip():
            return None, "Podaj autora"

        try:
            return int(autor), None
        except (TypeError, ValueError):
            return None, "Nieprawidłowe ID autora"

    def _validate_rok(self, rok):
        """Validate and convert rok parameter."""
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
        """Get disciplines for the given autor and rok."""
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
