from django.db import transaction
from django.http import JsonResponse
from django.http.response import HttpResponseNotFound
from django.views.generic import View

from bpp.models import Autor, Autor_Dyscyplina, Uczelnia, Zrodlo
from bpp.models.abstract import POLA_PUNKTACJI
from bpp.models.praca_habilitacyjna import Praca_Habilitacyjna
from bpp.models.zrodlo import Punktacja_Zrodla


class RokHabilitacjiView(View):
    def post(self, request, *args, **kw):
        try:
            autor = Autor.objects.get(pk=int(request.POST.get("autor_pk")))
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

        # d = dict([(pole, str(getattr(pz, pole))) for pole in POLA_PUNKTACJI])
        d = {pole: getattr(pz, pole) for pole in POLA_PUNKTACJI}
        return JsonResponse(d)


class UploadPunktacjaZrodlaView(View):
    def ok(self):
        return JsonResponse({"result": "ok"})

    @transaction.atomic
    def post(self, request, zrodlo_id, rok, *args, **kw):
        try:
            z = Zrodlo.objects.get(pk=zrodlo_id)
        except Zrodlo.DoesNotExist:
            return HttpResponseNotFound("Zrodlo")

        kw_punktacji = {}
        for element in list(request.POST.keys()):
            if element in POLA_PUNKTACJI:
                if request.POST.get(element) != "":
                    kw_punktacji[element] = request.POST.get(element) or "0.0"

        try:
            pz = Punktacja_Zrodla.objects.get(zrodlo=z, rok=rok)
        except Punktacja_Zrodla.DoesNotExist:
            Punktacja_Zrodla.objects.create(zrodlo=z, rok=rok, **kw_punktacji)
            return self.ok()

        if request.POST.get("overwrite") == "1":
            for key, value in list(kw_punktacji.items()):
                setattr(pz, key, value or "0.0")
            pz.save()
            return self.ok()
        return JsonResponse(dict(result="exists"))


def ostatnia_jednostka(request, a):
    uczelnia = Uczelnia.objects.get_for_request(request)

    jed = a.aktualna_jednostka
    if jed is None:
        # Brak aktualnej jednostki, spróbuj podpowiedzieć obcą jednostkę:
        if uczelnia is None:
            return None

        else:
            # uczelnia is not None
            if uczelnia.obca_jednostka_id is not None:
                return uczelnia.obca_jednostka
    else:
        return jed


def ostatnia_dyscyplina(request, a, rok):
    uczelnia = Uczelnia.objects.get_for_request(request)

    if uczelnia is not None and uczelnia.podpowiadaj_dyscypliny and rok:
        ad = Autor_Dyscyplina.objects.filter(autor=a, rok=rok)

        if ad.exists():
            # Jest wpis Autor_Dyscyplina dla tego autora i roku.
            ad = ad.first()
            if (
                ad.dyscyplina_naukowa_id is not None
                and ad.subdyscyplina_naukowa_id is not None
            ):
                return None

            return ad.dyscyplina_naukowa or ad.subdyscyplina_naukowa


class OstatniaJednostkaIDyscyplinaView(View):
    """Zwraca jako JSON ostatnią jednostkę danego autora oraz ewentualnie jego
    dyscyplinę naukową, w sytuacji gdy jest ona jedna i określona na dany rok.
    """

    def post(self, request, *args, **kw):
        try:
            a = Autor.objects.get(pk=int(request.POST.get("autor_id", None)))
        except (Autor.DoesNotExist, TypeError, ValueError):
            return JsonResponse({"status": "error", "reason": "autor nie istnieje"})

        ost_jed = ostatnia_jednostka(request, a)

        ret = {}

        if ost_jed is None:
            ret.update(dict(jednostka_id=None, nazwa=None, status="ok"))
        else:
            ret.update(
                dict(
                    jednostka_id=ost_jed.pk,
                    nazwa=ost_jed.nazwa,
                    status="ok",
                )
            )

        try:
            rok = int(request.POST.get("rok"))
        except (TypeError, ValueError):
            rok = None

        ost_dys = ostatnia_dyscyplina(request, a, rok)

        if ost_dys is not None:
            ret["dyscyplina_nazwa"] = ost_dys.nazwa
            ret["dyscyplina_id"] = ost_dys.pk
            ret["status"] = "ok"

        return JsonResponse(ret)
