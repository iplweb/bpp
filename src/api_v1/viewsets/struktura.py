from rest_framework import viewsets

from api_v1.serializers.struktura import (
    JednostkaSerializer,
    UczelniaSerializer,
)
from bpp.models import Jednostka, Uczelnia


class JednostkaViewSet(viewsets.ReadOnlyModelViewSet):
    # Widoczność (``widoczna``) NIE bramkuje już API — jednostki obce mają
    # ``widoczna=False``, ale autorzy obcy afiliują się do nich, więc
    # serializery emitują do nich hiperłącza i detail MUSI się rozwiązać
    # (inaczej harvester dostaje 404 i eksport pada). Jedynym wyznacznikiem
    # jest jawny opt-out ``nie_eksportuj_przez_api`` (domyślnie False =
    # wszystkie jednostki lecą przez API).
    queryset = Jednostka.objects.exclude(nie_eksportuj_przez_api=True)
    serializer_class = JednostkaSerializer


class UczelniaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Uczelnia.objects.all()
    serializer_class = UczelniaSerializer
