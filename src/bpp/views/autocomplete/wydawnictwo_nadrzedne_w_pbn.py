import isbnlib
from dal import autocomplete
from django import http

from import_common.util import check_if_doi, strip_doi_urls
from pbn_api.client import PBNClient
from pbn_api.exceptions import WillNotExportError
from pbn_api.models import Publication
from pbn_api.validators import check_mongoId

from bpp.models import Uczelnia


class Wydawnictwo_Nadrzedne_W_PBNAutocomplete(autocomplete.Select2QuerySetView):
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

    def post(self, request, *args, **kwargs):
        """Create an object given a text after checking permissions."""

        # Nie ruszamy tego importu -- ma pozostać tutaj, bo inaczej testy nie mogą zostać spatchowane
        from pbn_api.integrator import zapisz_mongodb

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

        match self.qualify_query(text):
            case self.MONGO_ID:
                lst = client.search_publications(objectId=text)
            case self.ISBN:
                text = isbnlib.canonical(text)
                lst = client.search_publications(isbn=text, type="BOOK")
            case self.TITLE:
                lst = client.search_publications(title=text, type="BOOK")
            case self.DOI:
                text = strip_doi_urls(text)
                lst = client.search_publications(doi=text, type="BOOK")
            case _:
                return http.JsonResponse(
                    {
                        "id": "error",
                        "text": f"Niezaimplementowany rodzaj wyszukiwania dla {text}",
                    }
                )

        no_records_found = 0

        for elem in lst:
            # z PBNu mogą przychodzić rekordy, które już sa w bazie danych i realnie nie ma żadnej możliwości
            # odsortować ich, więc po prostu je zignorujemy...

            if Publication.objects.filter(pk=elem["mongoId"]).exists():
                continue

            # Jest rekord z PBN ID spoza tych w bazie
            no_records_found += 1
            if no_records_found > self.MAX_RECORDS_DOWNLOADED:
                break

            pub = zapisz_mongodb(
                client.get_publication_by_id(elem["mongoId"]), Publication
            )

        if no_records_found == 0:
            return http.JsonResponse(
                {"id": "test", "text": "Nic (nowego) nie znaleziono w PBN."}
            )

        if no_records_found == 1:
            # Znaleziono tylko 1 rekord w PBN, więc można go zwrócić i ustawić jako wybrany...
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
