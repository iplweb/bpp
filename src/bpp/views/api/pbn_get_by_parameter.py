# -*- encoding: utf-8 -*-

from django.http import JsonResponse
from django.views.generic.base import View
from sentry_sdk import capture_exception

from import_common.normalization import normalize_doi, normalize_isbn
from pbn_api.exceptions import NeedsPBNAuthorisationException
from pbn_api.integrator import _pobierz_prace_po_elemencie
from pbn_api.models import Publication

from bpp.models import Uczelnia
from bpp.views.api.const import API_BRAK_PARAMETRU


class GetPBNPublicationsByBase(View):
    def get_rok(
        self,
        request,
    ):
        rok = request.POST.get("rok", "").strip()[:1024]
        try:
            rok = int(rok)
        except BaseException:
            rok = None
        return rok

    def get_publication(self, value, rok):
        """Pobierz publikacje po danych z zapytania uzytkownika"""
        return Publication.objects.get(
            **{self.publication_element_name: value, "year": rok}
        ).pk

    def get_normalized_values(self, request):
        # tytul = request.POST.get("tytul")
        return self.get_value(request), self.get_rok(request)

    def get_publication_by_element_name(
        self, client, elementName, normalizedInput, year
    ):
        return _pobierz_prace_po_elemencie(
            client,
            elementName,
            normalizedInput,
            # title=tytul[: len(tytul) // 3 * 4],
            year=year,
            matchuj=True,
        )

    def post(self, request, *args, **kw):
        ni, rok = self.get_normalized_values(request)

        if not ni:
            return JsonResponse({"error": API_BRAK_PARAMETRU})

        uczelnia = Uczelnia.objects.get_default()
        if not uczelnia:
            return JsonResponse({"error": "W systemie brak obiektu Uczelnia"})

        # Zawsze pobierz świeże dane z serwera -- w pierwszej kolejności:

        client = uczelnia.pbn_client(request.user.pbn_token)

        try:
            ret = self.get_publication_by_element_name(
                client=client,
                elementName=self.publication_element_name,
                normalizedInput=ni,
                year=rok,
            )
        except NeedsPBNAuthorisationException:
            return JsonResponse(
                {"error": "Autoryzuj się w PBN korzystając z menu na głównej stronie. "}
            )
        except Exception as e:
            # Zgłoś nieznany typ błędu do Sentry
            capture_exception(e)

            # .. oraz do użytkownika:
            return JsonResponse(
                {
                    "error": "Nieznany błąd po stronie serwera przy wywołaniu funkcji odpytującej PBN. "
                    + str(e)
                }
            )

        if ret:
            return JsonResponse({"id": ret[0].pbn_uid.pk})

        # Jeżeli serwer nie zwrócil nic rozsądnego, zwróc dane z lokalnego cache
        try:
            return JsonResponse({"id": self.get_publication(ni, rok)})
        except Publication.DoesNotExist:
            return JsonResponse(
                {
                    "error": "Taka publikacja nie istnieje ani w bazie PBN, ani w lokalnym "
                    "cache rekordów PBNu. "
                }
            )
        except Publication.MultipleObjectsReturned:
            # Wiele rekordów, zwróc ISBN. Po stronie klienta spowoduje to wpisanie numeru ISBN
            # do pola wyszukujacego
            return JsonResponse({"id": ni})

        raise NotImplementedError("Should never happen")


class GetPBNPublicationsByISBN(GetPBNPublicationsByBase):
    publication_element_name = "isbn"  # nazwa parametru dla _pobierz_prace_po_elemencie

    def get_value(self, request):
        """Pobierz wartość dla zapytania (ISBN, DOI, itp)"""
        ni = normalize_isbn(request.POST.get("t", "").strip()[:1024])
        return ni


class GetPBNPublicationsByDOI(GetPBNPublicationsByBase):
    publication_element_name = "doi"  # nazwa parametru dla _pobierz_prace_po_elemencie

    def get_value(self, request):
        """Pobierz wartość dla zapytania (ISBN, DOI, itp)"""
        ni = normalize_doi(request.POST.get("t", "").strip()[:1024])
        return ni
