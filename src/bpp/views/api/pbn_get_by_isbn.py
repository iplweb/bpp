# -*- encoding: utf-8 -*-

from django.http import JsonResponse
from django.views.generic.base import View

from import_common.normalization import normalize_isbn
from pbn_api.integrator import _pobierz_prace_po_elemencie

from bpp.models import Uczelnia
from bpp.views.api.const import PUBMED_BRAK_PARAMETRU


class GetPBNPublicationsByISBN(View):
    def post(self, request, *args, **kw):
        ni = normalize_isbn(request.POST.get("t", "").strip()[:1024])

        rok = request.POST.get("rok", "").strip()[:1024]
        try:
            rok = int(rok)
        except BaseException:
            rok = None

        # tytul = request.POST.get("tytul")

        if not ni:
            return JsonResponse({"error": PUBMED_BRAK_PARAMETRU})

        uczelnia = Uczelnia.objects.default
        if not uczelnia:
            return JsonResponse({"error": "W systemie brak obiektu Uczelnia"})

        client = uczelnia.pbn_client(request.user.pbn_token)

        ret = _pobierz_prace_po_elemencie(
            client,
            "isbn",
            ni,
            # title=tytul[: len(tytul) // 3 * 4],
            year=rok,
            matchuj=True,
        )

        if ret:
            return JsonResponse({"id": ret[0].pbn_uid.pk})

        return JsonResponse({"id": ni})
