import io

from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.generic import ListView
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte
from bpp.util import sanitize_xlsx_row
from importer_publikacji.providers.pbn import publikacja_z_obiektu_wersji
from importer_publikacji.wzbogacanie.pola import PUSTE, ZGODNE, porownaj
from pbn_downloader_app.freshness import is_pbn_publications_data_fresh

# Default year range for evaluation period
DEFAULT_YEAR_MIN = 2022
DEFAULT_YEAR_MAX = 2025

# All available comparison fields
COMPARISON_FIELDS = {
    "title": "Tytuł",
    "year": "Rok",
    "doi": "DOI",
    "isbn": "ISBN",
    "issn": "ISSN",
    "url": "URL/WWW",
    "authors": "Liczba autorów",
    "volume": "Tom",
    "pages": "Strony",
    "publisher": "Wydawca",
    "issue": "Numer zeszytu",
    "conference": "Konferencja",
    "keywords": "Słowa kluczowe",
    "abstract": "Streszczenie",
    "language": "Język",
    "publication_place": "Miejsce wydania",
    "series": "Seria wydawnicza",
    "points": "Punkty",
}


#: Pola porównywane silnikiem wzbogacania rekordu (FD#517): klucz pola
#: komparatora → pola silnika (``importer_publikacji.wzbogacanie.pola.POLA``).
POLA_SILNIKA = {
    "title": ("tytul_oryginalny",),
    "year": ("rok",),
    "doi": ("doi",),
    "isbn": ("isbn", "e_isbn"),
    "issn": ("issn", "e_issn"),
    "url": ("www",),
    "volume": ("tom",),
    "pages": ("strony",),
    "issue": ("nr_zeszytu",),
    "keywords": ("slowa_kluczowe",),
    "abstract": ("streszczenie",),
    "language": ("jezyk",),
}

#: Etykiety różnic — jak dotąd w komparatorze (pola silnika → etykieta).
ETYKIETY_SILNIKA = {
    "tytul_oryginalny": "Tytuł",
    "rok": "Rok",
    "doi": "DOI",
    "isbn": "ISBN",
    "e_isbn": "e-ISBN",
    "issn": "ISSN",
    "e_issn": "e-ISSN",
    "www": "URL/WWW",
    "tom": "Tom",
    "strony": "Strony",
    "nr_zeszytu": "Numer zeszytu",
    "slowa_kluczowe": "Słowa kluczowe",
    "jezyk": "Język",
}

#: Dłuższe wartości (streszczenia) są w wynikach skracane.
MAKSYMALNA_DLUGOSC_WARTOSCI = 300


def _wartosc(tekst):
    """Wartość pola do wyniku: pusty tekst dla braku, długie skrócone."""
    if tekst == PUSTE:
        return ""
    if len(tekst) > MAKSYMALNA_DLUGOSC_WARTOSCI:
        return tekst[:MAKSYMALNA_DLUGOSC_WARTOSCI] + "..."
    return tekst


DEFAULT_FIELDS = ["title", "year", "doi", "isbn", "issn", "url", "authors"]
SESSION_KEY = "komparator_publikacji_filters"


def _get_default_filters():
    """Return default filter values."""
    return {
        "query": "",
        "publication_type": "all",
        "year_min": str(DEFAULT_YEAR_MIN),
        "year_max": str(DEFAULT_YEAR_MAX),
        "enabled_fields": DEFAULT_FIELDS.copy(),
    }


def _parse_year(value, default):
    """Parse year string to int, returning default on failure."""
    try:
        return int(value) if value else default
    except ValueError:
        return default


@method_decorator(staff_member_required, name="dispatch")
class PublicationComparisonView(ListView):
    """View for comparing BPP publications with PBN API data."""

    template_name = "komparator_publikacji_pbn/comparison_list.html"
    context_object_name = "comparisons"
    paginate_by = 5

    def _get_filters(self):
        """Get filters from GET params or session."""
        has_filter_params = any(
            key in self.request.GET
            for key in ["q", "type", "year_min", "year_max", "fields"]
        )

        if has_filter_params:
            filters = {
                "query": self.request.GET.get("q", ""),
                "publication_type": self.request.GET.get("type", "all"),
                "year_min": self.request.GET.get("year_min", str(DEFAULT_YEAR_MIN)),
                "year_max": self.request.GET.get("year_max", str(DEFAULT_YEAR_MAX)),
                "enabled_fields": self.request.GET.getlist("fields")
                or DEFAULT_FIELDS.copy(),
            }
            self.request.session[SESSION_KEY] = filters
        else:
            filters = self.request.session.get(SESSION_KEY, _get_default_filters())

        return filters

    def _process_publications(self, queryset, pub_type, enabled_fields, comparisons):
        """Process publications and add comparisons with differences."""
        for pub in queryset[:100]:
            comparison = self._compare_publication(pub, pub_type, enabled_fields)
            if comparison["has_differences"]:
                comparisons.append(comparison)

    def get_queryset(self):
        """Get all publications with pbn_uid_id and compare them."""
        comparisons = []
        filters = self._get_filters()

        query = filters["query"]
        publication_type = filters["publication_type"]
        year_min = _parse_year(filters["year_min"], DEFAULT_YEAR_MIN)
        year_max = _parse_year(filters["year_max"], DEFAULT_YEAR_MAX)
        enabled_fields = filters["enabled_fields"]

        if publication_type in ["all", "ciagle"]:
            ciagle_qs = Wydawnictwo_Ciagle.objects.filter(
                pbn_uid_id__isnull=False, rok__gte=year_min, rok__lte=year_max
            ).select_related("pbn_uid", "zrodlo")
            if query:
                ciagle_qs = ciagle_qs.filter(
                    Q(tytul_oryginalny__icontains=query)
                    | Q(pbn_uid__title__icontains=query)
                    | Q(doi__icontains=query)
                )
            self._process_publications(ciagle_qs, "ciagle", enabled_fields, comparisons)

        if publication_type in ["all", "zwarte"]:
            zwarte_qs = Wydawnictwo_Zwarte.objects.filter(
                pbn_uid_id__isnull=False, rok__gte=year_min, rok__lte=year_max
            ).select_related("pbn_uid", "wydawca")
            if query:
                zwarte_qs = zwarte_qs.filter(
                    Q(tytul_oryginalny__icontains=query)
                    | Q(pbn_uid__title__icontains=query)
                    | Q(doi__icontains=query)
                    | Q(isbn__icontains=query)
                )
            self._process_publications(zwarte_qs, "zwarte", enabled_fields, comparisons)

        return comparisons

    def _compare_publication(self, bpp_pub, pub_type, enabled_fields):
        """Compare a BPP publication with its PBN counterpart."""
        pbn_pub = bpp_pub.pbn_uid
        differences = []

        # Pola, których silnik wzbogacania nie zna — porównywane po staremu.
        comparers = {
            "authors": self._compare_authors,
            "publisher": lambda b, p, d: self._compare_publisher(b, p, pub_type, d),
            "conference": self._compare_conference,
            "publication_place": lambda b, p, d: self._compare_publication_place(
                b, p, pub_type, d
            ),
            "series": self._compare_series,
            "points": self._compare_points,
        }

        # Kolejność różnic jak kolejność pól na liście wyboru.
        for field_name in COMPARISON_FIELDS:
            if field_name not in enabled_fields:
                continue
            if field_name in POLA_SILNIKA:
                differences.extend(self._roznice_silnika(bpp_pub, pbn_pub, field_name))
            else:
                comparers[field_name](bpp_pub, pbn_pub, differences)

        return {
            "bpp_publication": bpp_pub,
            "pbn_publication": pbn_pub,
            "type": pub_type,
            "differences": differences,
            "has_differences": len(differences) > 0,
            "pbn_id": pbn_pub.mongoId,
            "bpp_id": bpp_pub.pk,
        }

    def _dane_pbn(self, pbn_pub):
        """Dane bieżącej wersji publikacji z LOKALNEJ kopii PBN, w postaci
        używanej przez importer i wzbogacanie (bez łączenia z PBN). Ostatnia
        publikacja jest pamiętana — porównanie bywa wołane pole po polu."""
        ostatnia = getattr(self, "_ostatnie_dane_pbn", None)
        if ostatnia is not None and ostatnia[0] is pbn_pub:
            return ostatnia[1]
        wersja = pbn_pub.current_version or {}
        dane = publikacja_z_obiektu_wersji(
            {"versions": pbn_pub.versions}, wersja.get("object") or {}, pbn_pub.pk
        )
        self._ostatnie_dane_pbn = (pbn_pub, dane)
        return dane

    def _jezyk_dla_kodu(self, kod):
        """Język BPP dla kodu z PBN — jedno wyszukiwanie na kod, nie na pracę."""
        from importer_publikacji.wzbogacanie.pola import _znajdz_jezyk

        pamiec = self.__dict__.setdefault("_jezyki_wg_kodu", {})
        if kod not in pamiec:
            pamiec[kod] = _znajdz_jezyk(kod)
        return pamiec[kod]

    def _roznice_silnika(self, bpp_pub, pbn_pub, field_name):
        """Różnice jednego pola wg reguł wzbogacania rekordu (FD#517) —
        tych samych, których używa „Wzbogać z PBN”."""
        wiersze = porownaj(
            bpp_pub,
            self._dane_pbn(pbn_pub),
            pola=POLA_SILNIKA[field_name],
            znajdz_jezyk=self._jezyk_dla_kodu,
        )
        for wiersz in wiersze:
            if wiersz.status == ZGODNE:
                continue
            yield {
                "field": ETYKIETY_SILNIKA.get(wiersz.klucz, wiersz.etykieta),
                "bpp_value": _wartosc(wiersz.bpp),
                "pbn_value": _wartosc(wiersz.zrodlo),
            }

    def _compare_authors(self, bpp_pub, pbn_pub, differences):
        bpp_authors_count = bpp_pub.autorzy_set.count()
        pbn_authors_count = (
            pbn_pub.policz_autorow() if hasattr(pbn_pub, "policz_autorow") else 0
        )
        if bpp_authors_count != pbn_authors_count:
            differences.append(
                {
                    "field": "Liczba autorów",
                    "bpp_value": str(bpp_authors_count),
                    "pbn_value": str(pbn_authors_count),
                }
            )

    def _compare_publisher(self, bpp_pub, pbn_pub, pub_type, differences):
        if pub_type != "zwarte":
            return
        bpp_publisher = ""
        if hasattr(bpp_pub, "wydawca") and bpp_pub.wydawca:
            bpp_publisher = bpp_pub.wydawca.nazwa
        elif hasattr(bpp_pub, "wydawca_opis"):
            bpp_publisher = bpp_pub.wydawca_opis or ""
        pbn_publisher = pbn_pub.value_or_none("object", "publisher", "name") or ""
        if bpp_publisher.strip() != pbn_publisher.strip():
            differences.append(
                {
                    "field": "Wydawca",
                    "bpp_value": bpp_publisher[:50]
                    + ("..." if len(bpp_publisher) > 50 else ""),
                    "pbn_value": pbn_publisher[:50]
                    + ("..." if len(pbn_publisher) > 50 else ""),
                }
            )

    def _compare_conference(self, bpp_pub, pbn_pub, differences):
        if not hasattr(bpp_pub, "konferencja"):
            return
        bpp_conference = bpp_pub.konferencja.nazwa if bpp_pub.konferencja else ""
        pbn_conference = pbn_pub.value_or_none("object", "conferenceName") or ""
        if bpp_conference.strip() != pbn_conference.strip():
            differences.append(
                {
                    "field": "Konferencja",
                    "bpp_value": bpp_conference[:100]
                    + ("..." if len(bpp_conference) > 100 else ""),
                    "pbn_value": pbn_conference[:100]
                    + ("..." if len(pbn_conference) > 100 else ""),
                }
            )

    def _compare_publication_place(self, bpp_pub, pbn_pub, pub_type, differences):
        import re

        if pub_type != "zwarte":
            return
        bpp_place = ""
        if hasattr(bpp_pub, "miejsce_i_rok"):
            bpp_place = bpp_pub.miejsce_i_rok or ""
            place_match = re.match(r"^([^0-9]+)", bpp_place.strip())
            if place_match:
                bpp_place = place_match.group(1).strip()
        pbn_place = pbn_pub.value_or_none("object", "publicationPlace") or ""
        if bpp_place.strip() != pbn_place.strip():
            differences.append(
                {
                    "field": "Miejsce wydania",
                    "bpp_value": bpp_place,
                    "pbn_value": pbn_place,
                }
            )

    def _compare_series(self, bpp_pub, pbn_pub, differences):
        if not hasattr(bpp_pub, "seria_wydawnicza"):
            return
        bpp_series = bpp_pub.seria_wydawnicza.nazwa if bpp_pub.seria_wydawnicza else ""
        pbn_series = pbn_pub.value_or_none("object", "series") or ""
        if bpp_series.strip() != pbn_series.strip():
            differences.append(
                {
                    "field": "Seria wydawnicza",
                    "bpp_value": bpp_series[:100]
                    + ("..." if len(bpp_series) > 100 else ""),
                    "pbn_value": pbn_series[:100]
                    + ("..." if len(pbn_series) > 100 else ""),
                }
            )

    def _compare_points(self, bpp_pub, pbn_pub, differences):
        if not hasattr(bpp_pub, "punkty_kbn"):
            return
        bpp_points = bpp_pub.punkty_kbn or 0
        pbn_points = pbn_pub.value_or_none("object", "points") or 0
        try:
            bpp_points = float(bpp_points)
            pbn_points = float(pbn_points)
            if abs(bpp_points - pbn_points) > 0.01:
                differences.append(
                    {
                        "field": "Punkty",
                        "bpp_value": str(bpp_points),
                        "pbn_value": str(pbn_points),
                    }
                )
        except (ValueError, TypeError):
            if str(bpp_points) != str(pbn_points):
                differences.append(
                    {
                        "field": "Punkty",
                        "bpp_value": str(bpp_points),
                        "pbn_value": str(pbn_points),
                    }
                )

    def get(self, request, *args, **kwargs):
        """Handle GET request, including XLSX export and reset."""
        if request.GET.get("export") == "xlsx":
            return self.export_xlsx()

        # Handle reset action
        if request.GET.get("reset") == "1":
            if SESSION_KEY in request.session:
                del request.session[SESSION_KEY]
            # Redirect to clean URL
            from django.shortcuts import redirect

            return redirect("komparator_publikacji_pbn:comparison_list")

        return super().get(request, *args, **kwargs)

    def export_xlsx(self):
        """Export comparisons to XLSX file."""
        comparisons = self.get_queryset()

        # Create workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Porównanie publikacji BPP-PBN"

        # Headers
        headers = [
            "Typ",
            "ID BPP",
            "ID PBN",
            "Tytuł BPP",
            "Rok",
            "Pole",
            "Wartość BPP",
            "Wartość PBN",
        ]
        ws.append(headers)

        # Style headers
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(
            start_color="366092", end_color="366092", fill_type="solid"
        )
        for col in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")

        # Add data
        row_num = 2
        for comparison in comparisons:
            for diff in comparison["differences"]:
                ws.append(
                    sanitize_xlsx_row(
                        [
                            (
                                "Wydawnictwo ciągłe"
                                if comparison["type"] == "ciagle"
                                else "Wydawnictwo zwarte"
                            ),
                            comparison["bpp_id"],
                            comparison["pbn_id"],
                            comparison["bpp_publication"].tytul_oryginalny[:100],
                            comparison["bpp_publication"].rok,
                            diff["field"],
                            diff["bpp_value"],
                            diff["pbn_value"],
                        ]
                    )
                )
                row_num += 1

        from bpp.util import auto_fit_columns

        auto_fit_columns(ws)

        # Save to bytes buffer
        buffer = io.BytesIO()
        from bpp.util import sanitize_xlsx_workbook

        sanitize_xlsx_workbook(wb)
        wb.save(buffer)
        buffer.seek(0)

        # Create response
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            'attachment; filename="komparator_publikacji_bpp_pbn.xlsx"'
        )
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Manual pagination since we're working with a list
        queryset = self.get_queryset()
        paginator = Paginator(queryset, self.paginate_by)
        page_number = self.request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        context["comparisons"] = page_obj.object_list
        context["page_obj"] = page_obj
        context["is_paginated"] = page_obj.has_other_pages()

        # Get filters from session
        filters = self.request.session.get(SESSION_KEY, _get_default_filters())

        context["query"] = filters["query"]
        context["publication_type"] = filters["publication_type"]
        context["year_min"] = filters["year_min"]
        context["year_max"] = filters["year_max"]
        context["enabled_fields"] = filters["enabled_fields"]
        context["all_fields"] = COMPARISON_FIELDS

        # Build export URL with current filters
        export_params = {
            "q": filters["query"],
            "type": filters["publication_type"],
            "year_min": filters["year_min"],
            "year_max": filters["year_max"],
            "export": "xlsx",
        }
        # Add fields to export params
        for field in filters["enabled_fields"]:
            if "fields" not in export_params:
                export_params["fields"] = []
            export_params["fields"].append(field)

        # Build URL string
        export_url_parts = []
        for key, value in export_params.items():
            if key == "fields":
                for field_val in value:
                    export_url_parts.append(f"fields={field_val}")
            else:
                export_url_parts.append(f"{key}={value}")
        context["export_url"] = f"?{'&'.join(export_url_parts)}"

        # Add PBN data freshness check
        pbn_data_fresh, pbn_stale_message, pbn_last_download = (
            is_pbn_publications_data_fresh()
        )
        context["pbn_data_fresh"] = pbn_data_fresh
        context["pbn_stale_message"] = pbn_stale_message
        context["pbn_last_download"] = pbn_last_download

        return context
