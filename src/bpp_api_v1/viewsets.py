from rest_framework import viewsets

from bpp.models import Zrodlo, Rodzaj_Zrodla
from bpp_api_v1.serializers import ZrodloSerializer, Rodzaj_ZrodlaSerializer


class ZrodloViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Zrodlo.objects.all()
    serializer_class = ZrodloSerializer
    filterset_fields = ["nazwa", "skrot", "rodzaj", "nazwa_alternatywna", "zasieg"]


class Rodzaj_ZrodlaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Rodzaj_Zrodla.objects.all()
    serializer_class = Rodzaj_ZrodlaSerializer
