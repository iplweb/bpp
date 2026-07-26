"""Eksport wyników „Wyszukiwania zapytaniem" (DjangoQL).

Widok trzyma routing formatów i limity; zamianę querysetu na plik robi
bpp.views.multiseek_export — ta sama warstwa, której używa multiseek.
"""

from django.http import HttpResponseBadRequest
from django.views.generic import View

from bpp.views.multiseek_export import (
    MULTISEEK_EXPORT_DANE_FIELDS,
    MULTISEEK_EXPORT_OPIS_FIELDS,
    bibtex_export_response,
    csv_export_response,
    document_export_response,
    plain_multiseek_report_title,
    xlsx_export_response,
)
from bpp.views.zapytanie import (
    MODEL_REKORD,
    WprowadzanieDanychOrSuperuserMixin,
    parse_postac,
    wykonaj_zapytanie,
)

ZAPYTANIE_EXPORT_MAX_DANE = 25000
ZAPYTANIE_EXPORT_MAX_DOKUMENT = 5000
ZAPYTANIE_DEFAULT_REPORT_TITLE = "Wynik zapytania"

DATA_FORMATS = {"csv", "xlsx"}
DOCUMENT_FORMATS = {"html", "docx", "bib"}


class ZapytanieExportView(WprowadzanieDanychOrSuperuserMixin, View):
    http_method_names = ["get"]

    def get(self, request, export_format, *args, **kwargs):
        if export_format not in DATA_FORMATS | DOCUMENT_FORMATS:
            return HttpResponseBadRequest("Nieznany format eksportu.")

        model_key = request.GET.get("model") or MODEL_REKORD
        query = (request.GET.get("query") or "").strip()
        if not query:
            return HttpResponseBadRequest("Brak zapytania do wyeksportowania.")
        if model_key != MODEL_REKORD:
            return HttpResponseBadRequest(
                "Eksport autorów zostanie dodany w kolejnym kroku."
            )

        wynik = wykonaj_zapytanie(model_key, query)
        if wynik.queryset is None:
            return HttpResponseBadRequest(f"Błędne zapytanie: {wynik.error}")

        report_title = plain_multiseek_report_title(
            request.GET.get("tytul") or ZAPYTANIE_DEFAULT_REPORT_TITLE
        )
        queryset = wynik.queryset
        count = queryset.count()

        # Limity czytamy ze stałych MODUŁU (nie z domyślnych argumentów ani
        # zmiennych klasy) w chwili wywołania — inaczej
        # monkeypatch.setattr(zapytanie_export, "...", 0) w testach nie
        # miałby żadnego efektu (funkcja widziałaby starą wartość zamrożoną
        # przy imporcie).
        if export_format in DATA_FORMATS:
            if count > ZAPYTANIE_EXPORT_MAX_DANE:
                return self._za_duzo(count, ZAPYTANIE_EXPORT_MAX_DANE)
            return self._eksport_danych(request, export_format, queryset, report_title)

        if count > ZAPYTANIE_EXPORT_MAX_DOKUMENT:
            return self._za_duzo(count, ZAPYTANIE_EXPORT_MAX_DOKUMENT)

        postac = parse_postac(request.GET, model_key)
        return self._eksport_dokumentu(
            request, export_format, postac, queryset, report_title
        )

    @staticmethod
    def _eksport_dokumentu(request, export_format, postac, queryset, report_title):
        if export_format == "bib":
            if postac != "bibtex":
                return HttpResponseBadRequest(
                    'BibTeX dostępny tylko przy postaci wyniku „BibTeX".'
                )
            return bibtex_export_response(queryset, report_title)
        if postac == "bibtex":
            # Tak samo jak w multiseeku: gdy postać wyniku to BibTeX, html/
            # docx degradują do .bib — to nie jest zaskoczenie dla usera,
            # bo strona i tak renderuje BibTeX na ekranie w tej postaci.
            return bibtex_export_response(queryset, report_title)

        # postac=rekordy to tabela redakcyjna z ID i linkami do admina — jako
        # dokument do wydruku nie ma sensu, więc degradujemy do listy.
        report_type = "list" if postac == "rekordy" else postac
        return document_export_response(
            queryset, request, report_type, report_title, export_format
        )

    @staticmethod
    def _za_duzo(count, limit):
        return HttpResponseBadRequest(
            f"Eksport dostępny dla maksymalnie {limit} rekordów "
            f"(zapytanie zwróciło {count}). Zawęź zapytanie."
        )

    @staticmethod
    def _eksport_danych(request, export_format, queryset, report_title):
        wariant = request.GET.get("wariant", "dane")
        if export_format == "csv" or wariant not in {"dane", "opis"}:
            wariant = "dane"

        if wariant == "opis":
            queryset = (
                queryset.select_related(None)
                .select_related("charakter_formalny", "typ_kbn")
                .only(*MULTISEEK_EXPORT_OPIS_FIELDS)
            )
            return xlsx_export_response(queryset, request, report_title, "opis")

        queryset = (
            queryset.select_related(None)
            .select_related("zrodlo", "typ_kbn")
            .only(*MULTISEEK_EXPORT_DANE_FIELDS)
        )
        if export_format == "csv":
            return csv_export_response(queryset, request, report_title)
        return xlsx_export_response(queryset, request, report_title, "dane")
