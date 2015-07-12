# -*- encoding: utf-8 -*-
from django.db import transaction
from django.http import Http404
from django.http.response import HttpResponseNotFound
from django.views.generic import View
from bpp.models import Autor, Zrodlo
from bpp.models.abstract import POLA_PUNKTACJI
from bpp.models.zrodlo import Punktacja_Zrodla
from bpp.views.utils import JSONResponseMixin


class RokHabilitacjiView(JSONResponseMixin, View):
    def post(self, request, *args, **kw):
        try:
            autor = Autor.objects.get(pk=int(request.POST.get('autor_pk')))
        except Autor.DoesNotExist:
            return HttpResponseNotFound("Autor")

        habilitacja = autor.praca_habilitacyjna()
        if habilitacja is None:
            return HttpResponseNotFound("Habilitacja")

        return self.render_to_response({"rok": habilitacja.rok})


class PunktacjaZrodlaView(JSONResponseMixin, View):
    def post(self, request, zrodlo_id, rok, *args, **kw):

        try:
            z = Zrodlo.objects.get(pk=zrodlo_id)
        except Zrodlo.DoesNotExist:
            return HttpResponseNotFound("Zrodlo")

        try:
            pz = Punktacja_Zrodla.objects.get(zrodlo=z, rok=rok)
        except Punktacja_Zrodla.DoesNotExist:
            return HttpResponseNotFound("Rok")

        d = dict([(pole, str(getattr(pz, pole))) for pole in POLA_PUNKTACJI])
        return self.render_to_response(d)


class UploadPunktacjaZrodlaView(JSONResponseMixin, View):
    def ok(self):
        return self.render_to_response(dict(result='ok'))

    @transaction.commit_on_success
    def post(self, request, zrodlo_id, rok, *args, **kw):
        try:
            z = Zrodlo.objects.get(pk=zrodlo_id)
        except Zrodlo.DoesNotExist:
            return HttpResponseNotFound("Zrodlo")

        kw_punktacji = {}
        for element in request.POST.keys():
            if element in POLA_PUNKTACJI:
                if request.POST.get(element) != '':
                    kw_punktacji[element] = request.POST.get(element)

        try:
            pz = Punktacja_Zrodla.objects.get(zrodlo=z, rok=rok)
        except Punktacja_Zrodla.DoesNotExist:
            Punktacja_Zrodla.objects.create(
                zrodlo=z, rok=rok, **kw_punktacji)
            return self.ok()

        if request.POST.get("overwrite") == "1":
            for key, value in kw_punktacji.items():
                setattr(pz, key, value)
            pz.save()
            return self.ok()
        return self.render_to_response(dict(result="exists"))


class OstatniaJednostkaView(JSONResponseMixin, View):
    def post(self, request, *args, **kw):
        try:
            a = Autor.objects.get(pk=request.POST.get('autor_id', None))
        except Autor.DoesNotExist:
            return HttpResponseNotFound("Autor")

        jed = a.ostatnia_jednostka()
        if jed is None:
            return HttpResponseNotFound("Jednostka")

        return self.render_to_response(
            dict(jednostka_id=jed.pk, nazwa=jed.nazwa))