from rest_framework import viewsets

from api_v1.serializers.system import (
    Charakter_FormalnySerializer,
    Typ_KBNSerializer,
    JezykSerializer,
    Dyscyplina_NaukowaSerializer,
    KonferencjaSerializer,
    Seria_WydawniczaSerializer,
)
from bpp.models import (
    Charakter_Formalny,
    Typ_KBN,
    Jezyk,
    Dyscyplina_Naukowa,
    Konferencja,
    Seria_Wydawnicza,
)


class Seria_WydawniczaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Seria_Wydawnicza.objects.all()
    serializer_class = Seria_WydawniczaSerializer


class KonferencjaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Konferencja.objects.all()
    serializer_class = KonferencjaSerializer


class Dyscyplina_NaukowaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Dyscyplina_Naukowa.objects.all()
    serializer_class = Dyscyplina_NaukowaSerializer


class Charakter_FormalnyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Charakter_Formalny.objects.all()
    serializer_class = Charakter_FormalnySerializer


class Typ_KBNViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Typ_KBN.objects.all()
    serializer_class = Typ_KBNSerializer


class JezykViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Jezyk.objects.all()
    serializer_class = JezykSerializer
