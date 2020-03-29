from rest_framework import viewsets

from api_v1.serializers.struktura import (
    JednostkaSerializer,
    WydzialSerializer,
    UczelniaSerializer,
)
from bpp.models import Jednostka, Wydzial, Uczelnia


class JednostkaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Jednostka.objects.all()
    serializer_class = JednostkaSerializer


class WydzialViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Wydzial.objects.all()
    serializer_class = WydzialSerializer


class UczelniaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Uczelnia.objects.all()
    serializer_class = UczelniaSerializer
