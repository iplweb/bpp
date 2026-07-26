"""Eksport wyników „Wyszukiwania zapytaniem" (DjangoQL).

Widok trzyma routing formatów i limity; zamianę querysetu na plik robi
bpp.views.multiseek_export — ta sama warstwa, której używa multiseek.
"""

from django.http import HttpResponseBadRequest
from django.utils.html import escape
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
    MODEL_AUTOR,
    MODEL_REKORD,
    POSTAC_PIVOT,
    WprowadzanieDanychOrSuperuserMixin,
    parse_postac,
    wykonaj_zapytanie,
)

ZAPYTANIE_EXPORT_MAX_DANE = 25000
ZAPYTANIE_EXPORT_MAX_DOKUMENT = 5000
ZAPYTANIE_DEFAULT_REPORT_TITLE = "Wynik zapytania"

DATA_FORMATS = {"csv", "xlsx"}
DOCUMENT_FORMATS = {"html", "docx", "bib"}


def _blad(tresc):
    """400 jako CZYSTY TEKST, nie HTML.

    HttpResponseBadRequest domyślnie ustawia Content-Type: text/html —
    komunikaty tego widoku bywają zbudowane z fragmentów pochodzących od
    użytkownika (patrz błąd DjangoQL w get()), więc bez wymuszenia
    text/plain przeglądarka renderowałaby taki string jako aktywny HTML
    (reflected XSS). Jedna funkcja dla WSZYSTKICH odpowiedzi błędu w tym
    pliku, żeby nie było dwóch ścieżek do wyboru.
    """
    return HttpResponseBadRequest(tresc, content_type="text/plain; charset=utf-8")


class ZapytanieExportView(WprowadzanieDanychOrSuperuserMixin, View):
    http_method_names = ["get"]

    def get(self, request, export_format, *args, **kwargs):
        if export_format not in DATA_FORMATS | DOCUMENT_FORMATS:
            return _blad("Nieznany format eksportu.")

        model_key = request.GET.get("model") or MODEL_REKORD
        query = (request.GET.get("query") or "").strip()
        if not query:
            return _blad("Brak zapytania do wyeksportowania.")
        if model_key not in (MODEL_REKORD, MODEL_AUTOR):
            return _blad("Nieznany model do eksportu.")

        # Eksport modelu "autor" istnieje dziś TYLKO dla postac="pivot" —
        # macierz idzie przez ten sam _eksport_pivota co dla rekordów i
        # naprawdę działa (Zadanie 9). Lista autorów (postac domyślna
        # "rekordy") zostaje zablokowana do Zadania 11 — patrz
        # eksport_formaty() w zapytanie.py, który z tego samego powodu nie
        # pokazuje dla niej linków w pasku.
        postac = parse_postac(request.GET, model_key)
        if model_key == MODEL_AUTOR and postac != POSTAC_PIVOT:
            return _blad("Eksport autorów zostanie dodany w kolejnym kroku.")

        wynik = wykonaj_zapytanie(model_key, query)
        if wynik.queryset is None:
            # wynik.error to str(exc) z djangoql — odbija SUROWE literały z
            # zapytania usera (np. rok = "<script>...") w tekście błędu.
            # escape() jest drugą linią obrony NIEZALEŻNĄ od content_type
            # ustawionego w _blad(): gdyby ktoś kiedyś zmienił _blad z
            # powrotem na HTML, ekranowanie i tak chroni.
            return _blad(f"Błędne zapytanie: {escape(wynik.error)}")

        report_title = plain_multiseek_report_title(
            request.GET.get("tytul") or ZAPYTANIE_DEFAULT_REPORT_TITLE
        )
        queryset = wynik.queryset

        if postac == POSTAC_PIVOT:
            # Pivot eksportuje MACIERZ — jej rozmiar nie zależy od liczby
            # rekordów źródłowych, więc capy rekordowe (25000/5000) go nie
            # dotyczą (dokładnie jak w MyMultiseekExport.get). Od tego
            # miejsca w dół (poza tą gałęzią) queryset jest ZAWSZE
            # model=rekord — model=autor + postac!=pivot już odbił się
            # wyżej.
            return self._eksport_pivota(
                request, export_format, model_key, queryset, report_title
            )

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

        return self._eksport_dokumentu(
            request, export_format, postac, queryset, report_title
        )

    @staticmethod
    def _eksport_pivota(request, export_format, model_key, queryset, report_title):
        from bpp.pivot import core as pivot_core
        from bpp.pivot import wybierz_rejestr_pivota
        from bpp.views.multiseek_export import (
            pivot_csv_export_response,
            pivot_xlsx_export_response,
        )

        if export_format not in {"csv", "xlsx"}:
            return _blad("Eksport tabeli krzyżowej dostępny jako XLSX lub CSV.")
        rejestr = wybierz_rejestr_pivota(model_key)
        row_dim, col_dim, metric = rejestr.parse_params(request.GET)
        try:
            pivot_result = rejestr.zbuduj(queryset, row_dim, col_dim, metric)
        except pivot_core.PivotTooLargeError:
            return _blad(
                "Tabela krzyżowa jest zbyt duża do wyeksportowania — "
                "zawęź zapytanie lub wybierz mniej liczny wymiar."
            )
        if export_format == "csv":
            return pivot_csv_export_response(pivot_result, request, report_title)
        return pivot_xlsx_export_response(pivot_result, request, report_title)

    @staticmethod
    def _eksport_dokumentu(request, export_format, postac, queryset, report_title):
        if export_format == "bib":
            if postac != "bibtex":
                return _blad('BibTeX dostępny tylko przy postaci wyniku „BibTeX".')
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
        # limit i count to liczby (stała modułu / queryset.count()), nie
        # tekst od użytkownika — nic tu nie wymaga escape(), ale i tak
        # idzie przez _blad() (text/plain) razem z resztą komunikatów.
        return _blad(
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
