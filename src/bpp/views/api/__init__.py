# -*- encoding: utf-8 -*-
from django.db import transaction
from django.http import Http404, JsonResponse
from django.http.response import HttpResponseNotFound
from django.views.generic import View
from bpp.models import Autor, Zrodlo
from bpp.models.abstract import POLA_PUNKTACJI
from bpp.models.praca_habilitacyjna import Praca_Habilitacyjna
from bpp.models.zrodlo import Punktacja_Zrodla


class RokHabilitacjiView(View):
    def post(self, request, *args, **kw):
        try:
            autor = Autor.objects.get(pk=int(request.POST.get('autor_pk')))
        except Autor.DoesNotExist:
            return HttpResponseNotFound("Autor")

        try:
            habilitacja = autor.praca_habilitacyjna
        except Praca_Habilitacyjna.DoesNotExist:
            return HttpResponseNotFound("Habilitacja")

        return JsonResponse({"rok": habilitacja.rok})


class PunktacjaZrodlaView(View):
    def post(self, request, zrodlo_id, rok, *args, **kw):

        try:
            z = Zrodlo.objects.get(pk=zrodlo_id)
        except Zrodlo.DoesNotExist:
            return HttpResponseNotFound("Zrodlo")

        try:
            pz = Punktacja_Zrodla.objects.get(zrodlo=z, rok=rok)
        except Punktacja_Zrodla.DoesNotExist:
            return HttpResponseNotFound("Rok")

        #d = dict([(pole, str(getattr(pz, pole))) for pole in POLA_PUNKTACJI])
        d = dict([(pole, getattr(pz, pole)) for pole in POLA_PUNKTACJI])
        return JsonResponse(d)


class UploadPunktacjaZrodlaView(View):
    def ok(self):
        return JsonResponse({'result': 'ok'})

    @transaction.atomic
    def post(self, request, zrodlo_id, rok, *args, **kw):
        try:
            z = Zrodlo.objects.get(pk=zrodlo_id)
        except Zrodlo.DoesNotExist:
            return HttpResponseNotFound("Zrodlo")

        kw_punktacji = {}
        for element in list(request.POST.keys()):
            if element in POLA_PUNKTACJI:
                if request.POST.get(element) != '':
                    kw_punktacji[element] = request.POST.get(element) or "0.0"

        try:
            pz = Punktacja_Zrodla.objects.get(zrodlo=z, rok=rok)
        except Punktacja_Zrodla.DoesNotExist:
            Punktacja_Zrodla.objects.create(
                zrodlo=z, rok=rok, **kw_punktacji)
            return self.ok()

        if request.POST.get("overwrite") == "1":
            for key, value in list(kw_punktacji.items()):
                setattr(pz, key, value or "0.0")
            pz.save()
            return self.ok()
        return JsonResponse(dict(result="exists"))


class OstatniaJednostkaView(View):
    def post(self, request, *args, **kw):
        try:
            a = Autor.objects.get(pk=request.POST.get('autor_id', None))
        except Autor.DoesNotExist:
            return HttpResponseNotFound("Autor")

        jed = a.aktualna_jednostka
        if jed is None:
            return HttpResponseNotFound("Jednostka")

        return JsonResponse(
            dict(jednostka_id=jed.pk, nazwa=jed.nazwa))
