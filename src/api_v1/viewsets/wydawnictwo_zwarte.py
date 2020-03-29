from rest_framework import viewsets
from api_v1.serializers.wydawnictwo_zwarte import (
    Wydawnictwo_ZwarteSerializer,
    Wydawnictwo_Zwarte_AutorSerializer,
)
from bpp.models import Wydawnictwo_Zwarte, Wydawnictwo_Zwarte_Autor


class Wydawnictwo_Zwarte_AutorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Wydawnictwo_Zwarte_Autor.objects.all()
    serializer_class = Wydawnictwo_Zwarte_AutorSerializer


class Wydawnictwo_ZwarteViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Wydawnictwo_Zwarte.objects.all()
    serializer_class = Wydawnictwo_ZwarteSerializer
