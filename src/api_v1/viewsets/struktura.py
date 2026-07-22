from rest_framework import viewsets

from api_v1.serializers.struktura import (
    JednostkaSerializer,
    UczelniaSerializer,
)
from bpp.models import Jednostka, Uczelnia


class JednostkaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Jednostka.objects.widoczne()
    serializer_class = JednostkaSerializer


class UczelniaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Uczelnia.objects.all()
    serializer_class = UczelniaSerializer
