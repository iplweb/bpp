import io

from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.views.generic import ListView
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from import_common.normalization import normalize_isbn, normalize_issn

from django.contrib.admin.views.decorators import staff_member_required

from django.utils.decorators import method_decorator
from django.utils.html import strip_tags

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte

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


@method_decorator(staff_member_required, name="dispatch")
class PublicationComparisonView(ListView):
    """View for comparing BPP publications with PBN API data."""

    template_name = "komparator_publikacji_pbn/comparison_list.html"
    context_object_name = "comparisons"
    paginate_by = 5

    def get_queryset(self):
        """Get all publications with pbn_uid_id and compare them."""
        comparisons = []

        # Handle filter parameters - save to session if present in GET, otherwise load from session
        session_key = "komparator_publikacji_filters"

        # Check if we have any filter parameters in GET request
        has_filter_params = any(
            key in self.request.GET
            for key in ["q", "type", "year_min", "year_max", "fields"]
        )

        if has_filter_params:
            # Save current filters to session
            filters = {
                "query": self.request.GET.get("q", ""),
                "publication_type": self.request.GET.get("type", "all"),
                "year_min": self.request.GET.get("year_min", str(DEFAULT_YEAR_MIN)),
                "year_max": self.request.GET.get("year_max", str(DEFAULT_YEAR_MAX)),
                "enabled_fields": self.request.GET.getlist("fields"),
            }

            # If no fields selected in GET, use default set
            if not filters["enabled_fields"]:
                filters["enabled_fields"] = [
                    "title",
                    "year",
                    "doi",
                    "isbn",
                    "issn",
                    "url",
                    "authors",
                ]

            self.request.session[session_key] = filters
        else:
            # Load filters from session or use defaults
            filters = self.request.session.get(
                session_key,
                {
                    "query": "",
                    "publication_type": "all",
                    "year_min": str(DEFAULT_YEAR_MIN),
                    "year_max": str(DEFAULT_YEAR_MAX),
                    "enabled_fields": [
                        "title",
                        "year",
                        "doi",
                        "isbn",
                        "issn",
                        "url",
                        "authors",
                    ],
                },
            )

        # Extract filter values
        query = filters["query"]
        publication_type = filters["publication_type"]
        year_min = filters["year_min"]
        year_max = filters["year_max"]
        enabled_fields = filters["enabled_fields"]

        # Convert years to integers
        try:
            year_min = int(year_min) if year_min else DEFAULT_YEAR_MIN
        except ValueError:
            year_min = DEFAULT_YEAR_MIN

        try:
            year_max = int(year_max) if year_max else DEFAULT_YEAR_MAX
        except ValueError:
            year_max = DEFAULT_YEAR_MAX

        # Get Wydawnictwo_Ciagle with pbn_uid_id
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

            for pub in ciagle_qs[:100]:  # Limit to prevent memory issues
                comparison = self._compare_publication(pub, "ciagle", enabled_fields)
                if comparison["has_differences"]:
                    comparisons.append(comparison)

        # Get Wydawnictwo_Zwarte with pbn_uid_id
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

            for pub in zwarte_qs[:100]:  # Limit to prevent memory issues
                comparison = self._compare_publication(pub, "zwarte", enabled_fields)
                if comparison["has_differences"]:
                    comparisons.append(comparison)

        return comparisons

    def _compare_publication(self, bpp_pub, pub_type, enabled_fields):
        """Compare a BPP publication with its PBN counterpart."""
        pbn_pub = bpp_pub.pbn_uid
        differences = []

        # Compare title
        if "title" in enabled_fields:
            bpp_title = bpp_pub.tytul_oryginalny or ""
            pbn_title = pbn_pub.title or pbn_pub.value_or_none("object", "title") or ""
            # Strip HTML tags from BPP title for comparison (PBN titles don't have HTML tags)
            bpp_title_clean = strip_tags(bpp_title)
            if bpp_title_clean.strip() != pbn_title.strip():
                differences.append(
                    {
                        "field": "Tytuł",
                        "bpp_value": bpp_title[:100]
                        + ("..." if len(bpp_title) > 100 else ""),
                        "pbn_value": pbn_title[:100]
                        + ("..." if len(pbn_title) > 100 else ""),
                    }
                )

        # Compare year
        if "year" in enabled_fields:
            bpp_year = bpp_pub.rok
            pbn_year = pbn_pub.year or pbn_pub.value_or_none("object", "year")
            if bpp_year and pbn_year and str(bpp_year) != str(pbn_year):
                differences.append(
                    {
                        "field": "Rok",
                        "bpp_value": str(bpp_year),
                        "pbn_value": str(pbn_year),
                    }
                )

        # Compare DOI
        if "doi" in enabled_fields:
            bpp_doi = bpp_pub.doi or ""
            pbn_doi = pbn_pub.doi or pbn_pub.value_or_none("object", "doi") or ""
            if bpp_doi.strip().lower() != pbn_doi.strip().lower():
                differences.append(
                    {"field": "DOI", "bpp_value": bpp_doi, "pbn_value": pbn_doi}
                )

        # Compare ISBN (for books)
        if (
            "isbn" in enabled_fields
            and pub_type == "zwarte"
            and hasattr(bpp_pub, "isbn")
        ):
            # Get raw values for display
            bpp_isbn_raw = bpp_pub.isbn or ""
            pbn_isbn_raw = pbn_pub.isbn or pbn_pub.value_or_none("object", "isbn") or ""

            # Normalize for comparison
            bpp_isbn_normalized = normalize_isbn(bpp_isbn_raw) or ""
            pbn_isbn_normalized = normalize_isbn(pbn_isbn_raw) or ""

            # Also check e_isbn if main ISBN doesn't match
            if bpp_isbn_normalized != pbn_isbn_normalized:
                # Try e_isbn if available
                if hasattr(bpp_pub, "e_isbn") and bpp_pub.e_isbn:
                    bpp_e_isbn_normalized = normalize_isbn(bpp_pub.e_isbn) or ""
                    if bpp_e_isbn_normalized == pbn_isbn_normalized:
                        # E-ISBN matches PBN ISBN, so no difference
                        pass
                    else:
                        differences.append(
                            {
                                "field": "ISBN",
                                "bpp_value": bpp_isbn_raw,
                                "pbn_value": pbn_isbn_raw,
                            }
                        )
                else:
                    differences.append(
                        {
                            "field": "ISBN",
                            "bpp_value": bpp_isbn_raw,
                            "pbn_value": pbn_isbn_raw,
                        }
                    )

        # Compare public URI/WWW
        if "url" in enabled_fields:
            bpp_www = (
                getattr(bpp_pub, "public_www", None)
                or getattr(bpp_pub, "www", "")
                or ""
            )
            pbn_uri = (
                pbn_pub.publicUri or pbn_pub.value_or_none("object", "publicUri") or ""
            )
            if bpp_www.strip() != pbn_uri.strip():
                differences.append(
                    {
                        "field": "URL/WWW",
                        "bpp_value": bpp_www[:80]
                        + ("..." if len(bpp_www) > 80 else ""),
                        "pbn_value": pbn_uri[:80]
                        + ("..." if len(pbn_uri) > 80 else ""),
                    }
                )

        # Compare authors count
        if "authors" in enabled_fields:
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

        # Compare volume (for journal articles)
        if "volume" in enabled_fields and pub_type == "ciagle":
            bpp_tom = bpp_pub.tom if hasattr(bpp_pub, "tom") else ""
            pbn_volume = pbn_pub.volume() if hasattr(pbn_pub, "volume") else ""
            if (
                bpp_tom
                and pbn_volume
                and str(bpp_tom).strip() != str(pbn_volume).strip()
            ):
                differences.append(
                    {
                        "field": "Tom",
                        "bpp_value": str(bpp_tom),
                        "pbn_value": str(pbn_volume),
                    }
                )

        # Compare pages
        if (
            "pages" in enabled_fields
            and pub_type == "ciagle"
            and hasattr(bpp_pub, "strony")
        ):
            bpp_pages = bpp_pub.strony or ""
            pbn_pages = pbn_pub.value_or_none("object", "pages") or ""
            if bpp_pages.strip() != pbn_pages.strip():
                differences.append(
                    {"field": "Strony", "bpp_value": bpp_pages, "pbn_value": pbn_pages}
                )

        # Compare publisher (for books)
        if "publisher" in enabled_fields and pub_type == "zwarte":
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

        # Compare ISSN
        if "issn" in enabled_fields and hasattr(bpp_pub, "issn"):
            # Get raw values for display
            bpp_issn_raw = bpp_pub.issn or ""
            pbn_issn_raw = (
                pbn_pub.value_or_none("object", "issn")
                or pbn_pub.value_or_none("object", "journal", "issn")
                or ""
            )

            # Normalize for comparison
            bpp_issn_normalized = normalize_issn(bpp_issn_raw) or ""
            pbn_issn_normalized = normalize_issn(pbn_issn_raw) or ""

            # Also check e_issn if main ISSN doesn't match
            if bpp_issn_normalized != pbn_issn_normalized:
                # Try e_issn if available
                if hasattr(bpp_pub, "e_issn") and bpp_pub.e_issn:
                    bpp_e_issn_normalized = normalize_issn(bpp_pub.e_issn) or ""
                    if bpp_e_issn_normalized == pbn_issn_normalized:
                        # E-ISSN matches PBN ISSN, so no difference
                        pass
                    else:
                        # Also check if PBN has eissn field (for journal articles)
                        pbn_eissn = (
                            pbn_pub.value_or_none("object", "journal", "eissn") or ""
                        )
                        pbn_eissn_normalized = normalize_issn(pbn_eissn) or ""

                        if (
                            bpp_issn_normalized == pbn_eissn_normalized
                            or bpp_e_issn_normalized == pbn_eissn_normalized
                        ):
                            # One of the BPP ISSNs matches PBN eISSN, so no difference
                            pass
                        else:
                            differences.append(
                                {
                                    "field": "ISSN",
                                    "bpp_value": bpp_issn_raw,
                                    "pbn_value": pbn_issn_raw,
                                }
                            )
                else:
                    # Check if PBN has eissn field
                    pbn_eissn = (
                        pbn_pub.value_or_none("object", "journal", "eissn") or ""
                    )
                    pbn_eissn_normalized = normalize_issn(pbn_eissn) or ""

                    if bpp_issn_normalized == pbn_eissn_normalized:
                        # BPP ISSN matches PBN eISSN, so no difference
                        pass
                    else:
                        differences.append(
                            {
                                "field": "ISSN",
                                "bpp_value": bpp_issn_raw,
                                "pbn_value": pbn_issn_raw,
                            }
                        )

        # Compare issue number (numer zeszytu)
        if "issue" in enabled_fields and pub_type == "ciagle":
            bpp_issue = ""
            if hasattr(bpp_pub, "nr_zeszytu"):
                bpp_issue = bpp_pub.nr_zeszytu or ""
            pbn_issue = pbn_pub.value_or_none("object", "issue") or ""
            if bpp_issue.strip() != pbn_issue.strip():
                differences.append(
                    {
                        "field": "Numer zeszytu",
                        "bpp_value": bpp_issue,
                        "pbn_value": pbn_issue,
                    }
                )

        # Compare conference
        if "conference" in enabled_fields and hasattr(bpp_pub, "konferencja"):
            bpp_conference = ""
            if bpp_pub.konferencja:
                bpp_conference = bpp_pub.konferencja.nazwa
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

        # Compare keywords (słowa kluczowe)
        if "keywords" in enabled_fields and hasattr(bpp_pub, "slowa_kluczowe"):
            bpp_keywords = bpp_pub.slowa_kluczowe or ""
            pbn_keywords = pbn_pub.value_or_none("object", "keywords") or ""
            if isinstance(pbn_keywords, list):
                pbn_keywords = ", ".join(pbn_keywords)
            if bpp_keywords.strip() != pbn_keywords.strip():
                differences.append(
                    {
                        "field": "Słowa kluczowe",
                        "bpp_value": bpp_keywords[:200]
                        + ("..." if len(bpp_keywords) > 200 else ""),
                        "pbn_value": pbn_keywords[:200]
                        + ("..." if len(pbn_keywords) > 200 else ""),
                    }
                )

        # Compare abstract (streszczenie) - using similarity for long text
        if "abstract" in enabled_fields and hasattr(bpp_pub, "streszczenie"):
            bpp_abstract = bpp_pub.streszczenie or ""
            pbn_abstract = pbn_pub.value_or_none("object", "abstract") or ""
            # For abstracts, we compare if they exist/don't exist or are significantly different in length
            bpp_has_abstract = len(bpp_abstract.strip()) > 10
            pbn_has_abstract = len(pbn_abstract.strip()) > 10

            if bpp_has_abstract != pbn_has_abstract:
                differences.append(
                    {
                        "field": "Streszczenie",
                        "bpp_value": "Tak" if bpp_has_abstract else "Brak",
                        "pbn_value": "Tak" if pbn_has_abstract else "Brak",
                    }
                )
            elif bpp_has_abstract and pbn_has_abstract:
                # Compare lengths - if significantly different
                len_diff = abs(len(bpp_abstract) - len(pbn_abstract))
                if (
                    len_diff > max(len(bpp_abstract), len(pbn_abstract)) * 0.3
                ):  # 30% difference
                    differences.append(
                        {
                            "field": "Streszczenie (długość)",
                            "bpp_value": f"{len(bpp_abstract)} znaków",
                            "pbn_value": f"{len(pbn_abstract)} znaków",
                        }
                    )

        # Compare language (język)
        if "language" in enabled_fields and hasattr(bpp_pub, "jezyk"):
            bpp_language = ""
            if bpp_pub.jezyk:
                bpp_language = bpp_pub.jezyk.nazwa
            pbn_language = pbn_pub.value_or_none("object", "language") or ""
            if bpp_language.strip().lower() != pbn_language.strip().lower():
                differences.append(
                    {
                        "field": "Język",
                        "bpp_value": bpp_language,
                        "pbn_value": pbn_language,
                    }
                )

        # Compare publication place (miejsce wydania)
        if "publication_place" in enabled_fields and pub_type == "zwarte":
            bpp_place = ""
            if hasattr(bpp_pub, "miejsce_i_rok"):
                bpp_place = bpp_pub.miejsce_i_rok or ""
                # Extract place from "miejsce_i_rok" (e.g., "Warszawa 2023" -> "Warszawa")
                import re

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

        # Compare series (seria wydawnicza)
        if "series" in enabled_fields and hasattr(bpp_pub, "seria_wydawnicza"):
            bpp_series = ""
            if bpp_pub.seria_wydawnicza:
                bpp_series = bpp_pub.seria_wydawnicza.nazwa
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

        # Compare points (punkty)
        if "points" in enabled_fields and hasattr(bpp_pub, "punkty_kbn"):
            bpp_points = bpp_pub.punkty_kbn or 0
            pbn_points = pbn_pub.value_or_none("object", "points") or 0
            try:
                bpp_points = float(bpp_points)
                pbn_points = float(pbn_points)
                if (
                    abs(bpp_points - pbn_points) > 0.01
                ):  # Allow small floating point differences
                    differences.append(
                        {
                            "field": "Punkty",
                            "bpp_value": str(bpp_points),
                            "pbn_value": str(pbn_points),
                        }
                    )
            except (ValueError, TypeError):
                # If conversion fails, compare as strings
                if str(bpp_points) != str(pbn_points):
                    differences.append(
                        {
                            "field": "Punkty",
                            "bpp_value": str(bpp_points),
                            "pbn_value": str(pbn_points),
                        }
                    )

        return {
            "bpp_publication": bpp_pub,
            "pbn_publication": pbn_pub,
            "type": pub_type,
            "differences": differences,
            "has_differences": len(differences) > 0,
            "pbn_id": pbn_pub.mongoId,
            "bpp_id": bpp_pub.pk,
        }

    def get(self, request, *args, **kwargs):
        """Handle GET request, including XLSX export and reset."""
        if request.GET.get("export") == "xlsx":
            return self.export_xlsx()

        # Handle reset action
        if request.GET.get("reset") == "1":
            session_key = "komparator_publikacji_filters"
            if session_key in request.session:
                del request.session[session_key]
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
                row_num += 1

        # Adjust column widths
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except BaseException:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width

        # Save to bytes buffer
        buffer = io.BytesIO()
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
        session_key = "komparator_publikacji_filters"
        filters = self.request.session.get(
            session_key,
            {
                "query": "",
                "publication_type": "all",
                "year_min": str(DEFAULT_YEAR_MIN),
                "year_max": str(DEFAULT_YEAR_MAX),
                "enabled_fields": [
                    "title",
                    "year",
                    "doi",
                    "isbn",
                    "issn",
                    "url",
                    "authors",
                ],
            },
        )

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

        return context
