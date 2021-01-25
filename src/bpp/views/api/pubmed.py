# -*- encoding: utf-8 -*-

import pymed
from django.conf import settings
from django.http import JsonResponse
from django.views.generic.base import View

from bpp.views.api.const import (
    PUBMED_BRAK_PARAMETRU,
    PUBMED_PO_TYTULE_BRAK,
    PUBMED_PO_TYTULE_WIELE,
    PUBMED_TITLE_MULTIPLE,
    PUBMED_TITLE_NONEXISTENT,
)

from django_bpp.version import VERSION


def get_data_from_ncbi(title):
    pubmed = pymed.PubMed(tool=f"BPP {VERSION}", email=settings.ADMINS[0][0])
    title = (
        title.lower()
        .replace(" and ", " ")
        .replace(" in ", " ")
        .replace(" of ", " ")
        .replace(" the ", " ")
    )

    while title.find("  ") != -1:
        title = title.replace("  ", " ")

    results = list(pubmed.query(title, max_results=2))
    return results


def extract_data(x: "pymed.api.PubMedArticle"):
    return {
        "pubmed_id": x.pubmed_id,
        "doi": x.doi,
        "pmc_id": x.pmc_id,
        "title": x.title,
    }


class GetPubmedIDView(View):
    def post(self, request, *args, **kw):
        tytul = request.POST.get("t", "").strip()[:1024]

        if not tytul:
            return JsonResponse({"error": PUBMED_BRAK_PARAMETRU})

        if tytul == PUBMED_TITLE_NONEXISTENT:
            # ten warunek wykorzystywany jest przez testy integracyjne, nue ruszać go
            results = []
        elif tytul == PUBMED_TITLE_MULTIPLE:
            # ten warunek wykorzystywany jest przez testy integracyjne, nie ruszać go
            results = [None, None]
        else:
            results = get_data_from_ncbi(tytul)

        if len(results) == 0:
            return JsonResponse({"error": PUBMED_PO_TYTULE_BRAK})

        if len(results) > 1:
            return JsonResponse({"error": PUBMED_PO_TYTULE_WIELE})

        return JsonResponse(extract_data(results[0]))
