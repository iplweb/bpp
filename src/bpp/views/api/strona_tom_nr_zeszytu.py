# -*- encoding: utf-8 -*-
from braces.views import LoginRequiredMixin
from django.http.response import JsonResponse
from django.views.generic.base import View

from bpp.models.abstract import wez_zakres_stron, parse_informacje


class StronaTomNrZeszytuView(LoginRequiredMixin, View):
    def post(self, request, *args, **kw):
        szczegoly = request.POST.get('s', '').strip()
        informacje = request.POST.get('i', '').strip()

        tom = parse_informacje(informacje, "tom")
        nr_zeszytu = parse_informacje(informacje, "numer")

        return JsonResponse({
            'strony': wez_zakres_stron(szczegoly),
            'tom': tom,
            'nr_zeszytu': nr_zeszytu

        })