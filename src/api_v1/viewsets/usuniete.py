import datetime

from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.fields import DateTimeField
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from api_v1.serializers.usuniete import UsunietySerializer
from bpp.models import (
    Autor,
    Patent,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)

#: Modele soft-delete wystawiane jako nagrobki. Klucz to nazwa w odpowiedzi.
#: Wszystkie sześć potwierdzone jako ``SoftDeleteModel`` (fazy 02 i 04) —
#: model bez ``deleted_objects`` NIE ma tu prawa się znaleźć, bo endpoint
#: milknie wtedy dopiero w produkcji.
MODELE_NAGROBKOW = {
    "wydawnictwo_ciagle": Wydawnictwo_Ciagle,
    "wydawnictwo_zwarte": Wydawnictwo_Zwarte,
    "patent": Patent,
    "praca_doktorska": Praca_Doktorska,
    "praca_habilitacyjna": Praca_Habilitacyjna,
    "autor": Autor,
}

#: Parametr zapytania -> lookup na ``deleted_at``. Nazwy jak
#: ``DateTimeFromToRangeFilter`` w pozostałych viewsetach
#: (``?ostatnio_zmieniony_after=``), żeby klient nie musiał się uczyć
#: drugiej konwencji.
FILTRY_ZAKRESU = {
    "usuniety_od_after": "deleted_at__gte",
    "usuniety_od_before": "deleted_at__lte",
}

#: Zastępnik daty przy sortowaniu wierszy z ``deleted_at IS NULL``.
_NAJSTARSZY = datetime.datetime.min.replace(tzinfo=datetime.UTC)


class UsunieteViewSet(viewsets.ViewSet):
    """Rekordy usunięte (w koszu) — sam identyfikator i znacznik czasu.

    ⚠️ Znaczy WĘŻEJ niż nagrobek OAI-PMH. Tam nagrobek to „przestało być
    eksportowane" (dopełnienie ekspozycji), bo ``deletedRecord`` jest
    obietnicą wobec harvestera. REST takiej obietnicy nie składa, więc tu
    wychodzi wyłącznie kosz. Rekord ukryty przez ``nie_eksportuj_przez_api``
    dostanie nagrobek w OAI, ale NIE pojawi się tutaj (decyzja D5 specu
    2026-08-15).

    Treści rekordu nie wystawiamy nigdy — patrz ``UsunietySerializer``.

    Sortowanie rosnąco po dacie usunięcia: konsument przyrostowy przesuwa
    kursor do przodu, więc najstarsze musi iść pierwsze.
    """

    serializer_class = UsunietySerializer
    pagination_class = None

    # Domyślne ``DjangoModelPermissionsOrAnonReadOnly`` wymaga ``queryset``
    # albo ``get_queryset()``, a ten viewset łączy sześć modeli i żadnego
    # pojedynczego querysetu nie ma. Dla GET tamta klasa i tak nie żąda
    # uprawnień (mapa uprawnień ma dla odczytu pustą listę), więc ``AllowAny``
    # odtwarza zachowanie pozostałych endpointów DANE, nie rozluźniając go.
    # Realną kontrolą ekspozycji jest bramka ``z_bramka_api_v1(grupa=DANE)``
    # z ``api_v1/urls.py`` i przełącznik ``Uczelnia.api_v1_dane_bibliograficzne``.
    permission_classes = [AllowAny]

    def list(self, request):
        warunki = self._warunki_zakresu(request)

        wiersze = []
        for nazwa, model in MODELE_NAGROBKOW.items():
            queryset = model.deleted_objects.filter(**warunki)
            # Filtrujemy na querysecie każdego modelu, nie na sklejonej
            # liście: inaczej baza oddawałaby cały kosz, a Python wyrzucał
            # z niego większość.
            wiersze.extend(
                {"model": nazwa, "pk": pk, "usuniety_od": usuniety_od}
                for pk, usuniety_od in queryset.values_list("pk", "deleted_at")
            )

        # ``deleted_at`` bywa NULL na wierszach sprzed wprowadzenia pola —
        # trzymamy je na końcu zamiast wywalać się na porównaniu z ``None``.
        wiersze.sort(
            key=lambda w: (w["usuniety_od"] is None, w["usuniety_od"] or _NAJSTARSZY)
        )

        return Response({"results": UsunietySerializer(wiersze, many=True).data})

    def _warunki_zakresu(self, request):
        """Przetłumacz parametry zakresu na filtry ``deleted_at``.

        Data nieparsowalna daje 400, nie ciche pominięcie filtra: klient
        przyrostowy dostałby wtedy cały kosz i uznał, że to wszystko
        zniknęło od jego ostatniego odpytania.
        """
        pole = DateTimeField()
        warunki = {}
        for parametr, lookup in FILTRY_ZAKRESU.items():
            wartosc = request.query_params.get(parametr)
            if not wartosc:
                continue
            try:
                warunki[lookup] = pole.to_internal_value(wartosc)
            except ValidationError as wyjatek:
                raise ValidationError({parametr: wyjatek.detail}) from wyjatek
        return warunki
