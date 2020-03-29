from rest_framework import viewsets

from api_v1.serializers.wydawnictwo_ciagle import (
    Wydawnictwo_CiagleSerializer,
    Wydawnictwo_Ciagle_AutorSerializer,
    Wydawnictwo_Ciagle_Zewnetrzna_Baza_DanychSerializer,
)
from bpp.models import (
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Zewnetrzna_Baza_Danych,
)


class Wydawnictwo_Ciagle_AutorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Wydawnictwo_Ciagle_Autor.objects.all()
    serializer_class = Wydawnictwo_Ciagle_AutorSerializer


class Wydawnictwo_CiagleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Wydawnictwo_Ciagle.objects.all()
    serializer_class = Wydawnictwo_CiagleSerializer


class Wydawnictwo_Ciagle_Zewnetrzna_Baza_DanychViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Wydawnictwo_Ciagle_Zewnetrzna_Baza_Danych.objects.all()
    serializer_class = Wydawnictwo_Ciagle_Zewnetrzna_Baza_DanychSerializer
