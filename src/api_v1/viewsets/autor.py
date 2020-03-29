from rest_framework import viewsets

from api_v1.serializers.autor import (
    AutorSerializer,
    Funkcja_AutoraSerializer,
    TytulSerializer,
    Autor_JednostkaSerializer,
)
from bpp.models import Autor, Funkcja_Autora, Tytul, Autor_Jednostka


class AutorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Autor.objects.all()
    serializer_class = AutorSerializer


class Funkcja_AutoraViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Funkcja_Autora.objects.all()
    serializer_class = Funkcja_AutoraSerializer


class Autor_JednostkaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Autor_Jednostka.objects.all()
    serializer_class = Autor_JednostkaSerializer


class TytulViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tytul.objects.all()
    serializer_class = TytulSerializer
