import django_filters
from rest_framework import viewsets

from api_v1.permissions import widzi_dane_osobowe
from api_v1.serializers.autor import (
    Autor_JednostkaSerializer,
    AutorSerializer,
    Funkcja_AutoraSerializer,
    TytulSerializer,
)
from api_v1.throttling import SearchAnonThrottle, SearchUserThrottle
from bpp.models import Autor, Autor_Jednostka, Funkcja_Autora, Tytul


class AutorFilterSet(django_filters.rest_framework.FilterSet):
    ostatnio_zmieniony = django_filters.DateTimeFromToRangeFilter("ostatnio_zmieniony")
    nazwisko = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        fields = ["ostatnio_zmieniony", "nazwisko"]
        model = Autor


class AutorViewSet(viewsets.ReadOnlyModelViewSet):
    # Bazowy queryset BEZ filtra widoczności — zawężenie robi get_queryset()
    # dla każdego bez uprawnień (``widzi_dane_osobowe``).
    # ``jednostki`` to M2M serializowane many=True — bez prefetcha jedno
    # zapytanie NA AUTORA. Pozostałe relacje serializera są hyperlinkowane
    # (DRF czyta samo FK id z wiersza, ``use_pk_only_optimization``).
    queryset = Autor.objects.all().prefetch_related("jednostki")
    serializer_class = AutorSerializer
    filterset_class = AutorFilterSet
    # Filtr nazwisko__icontains skanuje bez indeksu prefiksu — opt-in
    # throttling kosztownego endpointu wyszukiwania (globalny wyłączony).
    throttle_classes = [SearchAnonThrottle, SearchUserThrottle]

    def get_queryset(self):
        # Autor z ``pokazuj_w_api=False`` NIE znika z API (hiperłącza
        # z publikacji nie mogą prowadzić do 404) — serializer zwraca dla
        # niego okrojony obiekt „dane ukryte”. Ale gdy w żądaniu jest
        # filtr (np. ``?nazwisko=``), ukryci są wykluczani: dopasowanie
        # okrojonego obiektu po nazwisku ujawniałoby tożsamość ukrytego.
        # Redaktor/superuser widzi wszystkich, w pełnej postaci.
        qs = super().get_queryset()
        if widzi_dane_osobowe(self.request):
            return qs
        if set(self.request.query_params) & set(AutorFilterSet.base_filters):
            return qs.filter(pokazuj_w_api=True)
        return qs


class Funkcja_AutoraViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Funkcja_Autora.objects.all()
    serializer_class = Funkcja_AutoraSerializer


class Autor_JednostkaViewSet(viewsets.ReadOnlyModelViewSet):
    # Bazowy queryset BEZ filtra widoczności — zawężenie robi get_queryset()
    # dla każdego bez uprawnień (analogicznie do AutorViewSet).
    queryset = Autor_Jednostka.objects.all()
    serializer_class = Autor_JednostkaSerializer

    def get_queryset(self):
        # Bez uprawnień redaktorskich nie widać powiązań zatrudnienia autora
        # ukrytego w API (autor.pokazuj_w_api=False) — jednostka, daty pracy
        # i PK autora byłyby widoczne mimo że AutorViewSet ukrywa jego dane.
        # Redaktor/superuser widzi wszystkich.
        qs = super().get_queryset()
        if widzi_dane_osobowe(self.request):
            return qs
        return qs.filter(autor__pokazuj_w_api=True)


class TytulViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tytul.objects.all()
    serializer_class = TytulSerializer
