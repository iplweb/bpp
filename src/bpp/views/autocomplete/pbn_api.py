from abc import abstractmethod

from dal import autocomplete
from django import http
from django.db.models.query_utils import Q
from sentry_sdk import capture_exception

from pbn_api.client import PBNClient
from pbn_api.exceptions import AccessDeniedException
from pbn_api.integrator import ACTIVE, zapisz_mongodb
from pbn_api.models import Journal, Publication, Scientist

from django.contrib.auth.mixins import LoginRequiredMixin

from django.utils.translation import gettext_lazy as _

from bpp import const
from bpp.const import PBN_UID_LEN
from bpp.models import Uczelnia


class BasePBNAutocomplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    """
    Ta klasa robi wyszukiwanie zadeklarowanego modelu z PBN, jednocześnie pozwala
    też utworzyć w bazie danych taki model - na podstawie mongoID.
    """

    create_field = "mongoId"

    @property
    def pbn_api_model(self):
        raise NotImplementedError("Please override this in a subclass")

    @property
    def sort_order(self):
        raise NotImplementedError("Please override this in a subclass")

    @abstractmethod
    def filter_queryset(self, qs, word):
        raise NotImplementedError("Please override in a subclass")

    @abstractmethod
    def fetch_pbn_data(self, client, query):
        raise NotImplementedError("Please override in a subclass")

    def get_create_option(self, context, q):
        """Form the correct create_option to append to results."""
        create_option = []
        display_create_option = False
        if self.create_field and q:
            page_obj = context.get("page_obj", None)
            if (page_obj is None or page_obj.number == 1) and len(
                q.strip()
            ) == PBN_UID_LEN:
                display_create_option = True

            # Don't offer to create a new option if a
            # case-insensitive) identical one already exists
            existing_options = (
                self.get_result_label(result).lower()
                for result in context["object_list"]
            )
            if q.lower() in existing_options:
                display_create_option = False
            if Publication.objects.filter(pk=q.lower()).exists():
                display_create_option = False

        if display_create_option and self.has_add_permission(self.request):
            create_option = [
                {
                    "id": q,
                    "text": _('Pobierz rekord o UID "%(new_value)s" z serwera PBNu')
                    % {"new_value": q},
                    "create_id": True,
                }
            ]
        return create_option

    def create_object(self, text):
        uczelnia = Uczelnia.objects.get_for_request(self.request)
        client = uczelnia.pbn_client(self.request.user.pbn_token)
        return zapisz_mongodb(self.fetch_pbn_data(client, text), self.pbn_api_model)

    def post(self, request, *args, **kwargs):
        """Create an object given a text after checking permissions."""
        if not self.has_add_permission(request):
            return http.HttpResponseForbidden()

        text = request.POST.get("text", None)

        if text is None:
            return http.HttpResponseBadRequest()

        try:
            result = self.create_object(text)
        except AccessDeniedException:
            return http.JsonResponse(
                {
                    "id": None,
                    "text": "Brak dostępu. Autoryzuj się w PBN API za pomocą opcji na głównej stronie. ",
                }
            )

        except Exception as e:
            # Zaloguj wyjątek do Sentry
            capture_exception(e)
            return http.HttpResponseBadRequest(str(e))

        return http.JsonResponse(
            {
                "id": result.pk,
                "text": self.get_selected_result_label(result),
            }
        )

    def get_base_queryset(self):
        return self.pbn_api_model.objects.filter(status=ACTIVE)

    def separate_words(self, q):
        return [word.strip() for word in q.strip().split(" ") if word.strip()]

    def get_queryset(self):
        qs = self.get_base_queryset()

        self.q = self.q.strip()

        if self.q:
            if len(self.q) == const.PBN_UID_LEN and self.q.find(" ") == -1:
                # podany parametr ma długość PBN_UID, więc szukamy po PBN UID:
                qs = qs.filter(pk=self.q)
            else:
                words = self.separate_words(self.q)
                for word in words:
                    qs = self.filter_queryset(qs, word)
        return qs.order_by(*self.sort_order)


class PublicationAutocomplete(BasePBNAutocomplete):
    pbn_api_model = Publication
    sort_order = ("title", "-year")

    def fetch_pbn_data(self, client, query):
        return client.get_publication_by_id(query)

    def filter_queryset(self, qs, word):
        return qs.filter(
            Q(title__istartswith=self.q.strip())
            | Q(title__icontains=word)
            | Q(isbn__exact=word)
            | Q(doi__icontains=word)
        )


class ScientistAutocomplete(BasePBNAutocomplete):
    pbn_api_model = Scientist
    sort_order = ("from_institution_api",)  # "lastName", "name")

    def fetch_pbn_data(self, client, query):
        return client.get_person_by_id(query)

    def filter_queryset(self, qs, word):
        return qs.filter(
            Q(lastName__istartswith=self.q.strip())
            | Q(name__icontains=word)
            | Q(pbnId__exact=word)
            | Q(orcid__icontains=word)
        )


class JournalAutocomplete(BasePBNAutocomplete):
    pbn_api_model = Journal
    sort_order = ("title", "mniswId")

    def fetch_pbn_data(self, client: PBNClient, query):
        return client.get_journal_by_id(query)

    def filter_queryset(self, qs, word):
        return qs.filter(
            Q(title__istartswith=self.q.strip())
            | Q(title__icontains=word)
            | Q(issn__exact=word)
            | Q(eissn__exact=word)
            | Q(websiteLink__icontains=word)
        )
