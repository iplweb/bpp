from django.core.paginator import Paginator
from django.db.models import Q
from django.views.generic import ListView

from django.contrib.admin.views.decorators import staff_member_required

from django.utils.decorators import method_decorator

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte


@method_decorator(staff_member_required, name="dispatch")
class PublicationComparisonView(ListView):
    """View for comparing BPP publications with PBN API data."""

    template_name = "komparator_publikacji_pbn/comparison_list.html"
    context_object_name = "comparisons"
    paginate_by = 5

    def get_queryset(self):
        """Get all publications with pbn_uid_id and compare them."""
        comparisons = []
        query = self.request.GET.get("q", "")
        publication_type = self.request.GET.get("type", "all")

        # Get Wydawnictwo_Ciagle with pbn_uid_id
        if publication_type in ["all", "ciagle"]:
            ciagle_qs = Wydawnictwo_Ciagle.objects.filter(
                pbn_uid_id__isnull=False
            ).select_related("pbn_uid", "zrodlo")

            if query:
                ciagle_qs = ciagle_qs.filter(
                    Q(tytul_oryginalny__icontains=query)
                    | Q(pbn_uid__title__icontains=query)
                    | Q(doi__icontains=query)
                )

            for pub in ciagle_qs[:100]:  # Limit to prevent memory issues
                comparison = self._compare_publication(pub, "ciagle")
                if comparison["has_differences"]:
                    comparisons.append(comparison)

        # Get Wydawnictwo_Zwarte with pbn_uid_id
        if publication_type in ["all", "zwarte"]:
            zwarte_qs = Wydawnictwo_Zwarte.objects.filter(
                pbn_uid_id__isnull=False
            ).select_related("pbn_uid", "wydawca")

            if query:
                zwarte_qs = zwarte_qs.filter(
                    Q(tytul_oryginalny__icontains=query)
                    | Q(pbn_uid__title__icontains=query)
                    | Q(doi__icontains=query)
                    | Q(isbn__icontains=query)
                )

            for pub in zwarte_qs[:100]:  # Limit to prevent memory issues
                comparison = self._compare_publication(pub, "zwarte")
                if comparison["has_differences"]:
                    comparisons.append(comparison)

        return comparisons

    def _compare_publication(self, bpp_pub, pub_type):
        """Compare a BPP publication with its PBN counterpart."""
        pbn_pub = bpp_pub.pbn_uid
        differences = []

        # Compare title
        bpp_title = bpp_pub.tytul_oryginalny or ""
        pbn_title = pbn_pub.title or pbn_pub.value_or_none("object", "title") or ""
        if bpp_title.strip() != pbn_title.strip():
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
        bpp_year = bpp_pub.rok
        pbn_year = pbn_pub.year or pbn_pub.value_or_none("object", "year")
        if bpp_year and pbn_year and str(bpp_year) != str(pbn_year):
            differences.append(
                {"field": "Rok", "bpp_value": str(bpp_year), "pbn_value": str(pbn_year)}
            )

        # Compare DOI
        bpp_doi = bpp_pub.doi or ""
        pbn_doi = pbn_pub.doi or pbn_pub.value_or_none("object", "doi") or ""
        if bpp_doi.strip().lower() != pbn_doi.strip().lower():
            differences.append(
                {"field": "DOI", "bpp_value": bpp_doi, "pbn_value": pbn_doi}
            )

        # Compare ISBN (for books)
        if pub_type == "zwarte" and hasattr(bpp_pub, "isbn"):
            bpp_isbn = bpp_pub.isbn or ""
            pbn_isbn = pbn_pub.isbn or pbn_pub.value_or_none("object", "isbn") or ""
            if bpp_isbn.strip() != pbn_isbn.strip():
                differences.append(
                    {"field": "ISBN", "bpp_value": bpp_isbn, "pbn_value": pbn_isbn}
                )

        # Compare public URI/WWW
        bpp_www = (
            getattr(bpp_pub, "public_www", None) or getattr(bpp_pub, "www", "") or ""
        )
        pbn_uri = (
            pbn_pub.publicUri or pbn_pub.value_or_none("object", "publicUri") or ""
        )
        if bpp_www.strip() != pbn_uri.strip():
            differences.append(
                {
                    "field": "URL/WWW",
                    "bpp_value": bpp_www[:80] + ("..." if len(bpp_www) > 80 else ""),
                    "pbn_value": pbn_uri[:80] + ("..." if len(pbn_uri) > 80 else ""),
                }
            )

        # Compare authors count
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
        if pub_type == "ciagle":
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
        if pub_type == "ciagle" and hasattr(bpp_pub, "strony"):
            bpp_pages = bpp_pub.strony or ""
            pbn_pages = pbn_pub.value_or_none("object", "pages") or ""
            if bpp_pages.strip() != pbn_pages.strip():
                differences.append(
                    {"field": "Strony", "bpp_value": bpp_pages, "pbn_value": pbn_pages}
                )

        # Compare publisher (for books)
        if pub_type == "zwarte":
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

        return {
            "bpp_publication": bpp_pub,
            "pbn_publication": pbn_pub,
            "type": pub_type,
            "differences": differences,
            "has_differences": len(differences) > 0,
            "pbn_id": pbn_pub.mongoId,
            "bpp_id": bpp_pub.pk,
        }

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
        context["query"] = self.request.GET.get("q", "")
        context["publication_type"] = self.request.GET.get("type", "all")

        return context
