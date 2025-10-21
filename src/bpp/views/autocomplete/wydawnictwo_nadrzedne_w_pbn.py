import isbnlib
from dal import autocomplete
from django import http

from bpp.models import Uczelnia
from import_common.util import check_if_doi, strip_doi_urls
from pbn_api.client import PBNClient
from pbn_api.exceptions import WillNotExportError
from pbn_api.models import Publication
from pbn_api.validators import check_mongoId

from .mixins import SanitizedAutocompleteMixin


class Wydawnictwo_Nadrzedne_W_PBNAutocomplete(
    SanitizedAutocompleteMixin, autocomplete.Select2QuerySetView
):
    # Ile rekordów maksymalnie ściągać z PBN?
    MAX_RECORDS_DOWNLOADED = 5

    MONGO_ID = "mongoId"
    ISBN = "ISBN"
    TITLE = "tytuł"
    DOI = "DOI"

    def qualify_query(self, txt):
        """Zwraca wartość klucza po którym wyszukiwać w PBN, ale i tym samym kwalifikuje
        wpisaną przez użytkownika wartość ze zmiennej txt jako ISBN, DOI lub tytuł"""

        if not isbnlib.notisbn(txt):
            return self.ISBN

        if check_mongoId(txt):
            return self.MONGO_ID

        if check_if_doi(txt):
            return self.DOI

        return self.TITLE

    def get_create_option(self, context, q):
        qual = self.qualify_query(q)
        if qual == self.DOI:
            q = strip_doi_urls(q)
        elif qual == self.ISBN:
            q = isbnlib.canonical(q)

        create_option = [
            {
                "id": q,
                "text": f'Pobierz z PBN rekord(y) gdzie {qual} to "{q}"',
                "create_id": True,
            }
        ]
        return create_option

    def render_to_response(self, context):
        """Return a JSON response in Select2 format."""
        q = self.request.GET.get("q", None)

        create_option = []
        if not self.has_more(context):
            # Wyświetlaj opcję pobrania z PBN tylko pod koniec listy rekordów
            create_option = self.get_create_option(context, q)

        return http.JsonResponse(
            {
                "results": self.get_results(context) + create_option,
                "pagination": {"more": self.has_more(context)},
            }
        )

    def get(self, request, *args, **kwargs):
        """Return option list json response."""
        if self.q is None or not self.q or len(self.q) < 5:
            return http.JsonResponse(
                {"results": [{"id": "id", "text": "Wpisz przynajmniej 5 znaków..."}]},
                content_type="application/json",
            )

        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        if not self.q or len(self.q) < 5:
            return [
                {
                    "id": self.q,
                    "text": "Wpisz przynajmniej 5 znaków...",
                    "create_id": False,
                }
            ]

        from pbn_api.models import Publication

        match self.qualify_query(self.q):
            case self.MONGO_ID:
                return Publication.objects.filter(pk=self.q)
            case self.ISBN:
                isbn = isbnlib.canonical(self.q)
                return Publication.objects.filter(isbn=isbn)
            case self.TITLE:
                return Publication.objects.filter(title__icontains=self.q)
            case self.DOI:
                doi = strip_doi_urls(self.q)
                return Publication.objects.filter(doi=doi)
            case _:
                raise NotImplementedError(self.q)

    def _get_pbn_search_results(self, client, query_type, text):
        """Get search results from PBN based on query type"""
        match query_type:
            case self.MONGO_ID:
                return client.search_publications(objectId=text)
            case self.ISBN:
                text = isbnlib.canonical(text)
                return client.search_publications(isbn=text, type="BOOK")
            case self.TITLE:
                return client.search_publications(title=text, type="BOOK")
            case self.DOI:
                text = strip_doi_urls(text)
                return client.search_publications(doi=text, type="BOOK")
            case _:
                return None

    def _process_search_results(self, client, lst):
        """Process search results and download new publications"""
        from pbn_integrator.utils import zapisz_mongodb

        no_records_found = 0
        pub = None

        for elem in lst:
            # Skip records that already exist in the database
            if Publication.objects.filter(pk=elem["mongoId"]).exists():
                continue

            # Found a record with PBN ID not in the database
            no_records_found += 1
            if no_records_found > self.MAX_RECORDS_DOWNLOADED:
                break

            pub = zapisz_mongodb(
                client.get_publication_by_id(elem["mongoId"]), Publication
            )

        return no_records_found, pub

    def _create_response_message(self, no_records_found, pub):
        """Create appropriate response message based on results"""
        if no_records_found == 0:
            return http.JsonResponse(
                {"id": "test", "text": "Nic (nowego) nie znaleziono w PBN."}
            )

        if no_records_found == 1:
            # Only one record found, return it as selected
            return http.JsonResponse({"id": pub.pk, "text": pub.title})

        byloby_wiecej = ""
        if no_records_found > self.MAX_RECORDS_DOWNLOADED:
            byloby_wiecej = "Potencjalnie jest ich więcej. "

        return http.JsonResponse(
            {
                "id": "test",
                "text": f"Pobrano {no_records_found} rekord/y/ów. {byloby_wiecej}Wpisz szukany tekst jeszcze raz",
            }
        )

    def post(self, request, *args, **kwargs):
        """Create an object given a text after checking permissions."""
        uczelnia: Uczelnia = Uczelnia.objects.get_for_request(self.request)
        try:
            client: PBNClient = uczelnia.pbn_client()
        except WillNotExportError:
            return http.JsonResponse(
                {"id": "error", "text": "Wykonaj autoryzację w PBN!"}
            )

        text = request.POST.get("text", None)
        if text is None:
            return http.HttpResponseBadRequest()

        text = text.strip()
        query_type = self.qualify_query(text)

        # Get search results from PBN
        lst = self._get_pbn_search_results(client, query_type, text)
        if lst is None:
            return http.JsonResponse(
                {
                    "id": "error",
                    "text": f"Niezaimplementowany rodzaj wyszukiwania dla {text}",
                }
            )

        # Process search results
        no_records_found, pub = self._process_search_results(client, lst)

        # Create and return response message
        return self._create_response_message(no_records_found, pub)
