from django.db.models import CharField, Value
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.fields import DateTimeField
from rest_framework.permissions import AllowAny

from api_v1.pagination import BppLimitOffsetPagination
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

#: Ścieżki ORM do ``Uczelnia`` — reguła atrybucji jak w pozostałych
#: endpointach (``bpp.util.uczelnia_scope``): rekord należy do uczelni, gdy
#: którakolwiek jednostka na autorstwie do niej należy; autor — gdy był
#: kiedykolwiek zatrudniony w jej jednostce (FD#390) albo ma ją aktualnie.
ATRYBUCJA_UCZELNI = {
    "wydawnictwo_ciagle": ("autorzy_set__jednostka__uczelnia",),
    "wydawnictwo_zwarte": ("autorzy_set__jednostka__uczelnia",),
    "patent": ("autorzy_set__jednostka__uczelnia",),
    "praca_doktorska": ("jednostka__uczelnia",),
    "praca_habilitacyjna": ("jednostka__uczelnia",),
    "autor": (
        "autor_jednostka__jednostka__uczelnia",
        "aktualna_jednostka__uczelnia",
    ),
}

#: Parametr zapytania -> lookup na ``deleted_at``. Nazwy jak
#: ``DateTimeFromToRangeFilter`` w pozostałych viewsetach
#: (``?ostatnio_zmieniony_after=``), żeby klient nie musiał się uczyć
#: drugiej konwencji.
FILTRY_ZAKRESU = {
    "usuniety_od_after": "deleted_at__gte",
    "usuniety_od_before": "deleted_at__lte",
}

#: Nazwa kolumny z etykietą modelu w złączonym zapytaniu. Nie może kolidować
#: z żadnym polem sześciu modeli, bo ``annotate`` podniósłby wtedy błąd.
KOLUMNA_MODELU = "_etykieta_modelu"


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
    pagination_class = BppLimitOffsetPagination

    # Domyślne ``DjangoModelPermissionsOrAnonReadOnly`` wymaga ``queryset``
    # albo ``get_queryset()``, a ten viewset łączy sześć modeli i żadnego
    # pojedynczego querysetu nie ma. Dla GET tamta klasa i tak nie żąda
    # uprawnień (mapa uprawnień ma dla odczytu pustą listę), więc ``AllowAny``
    # odtwarza zachowanie pozostałych endpointów DANE, nie rozluźniając go.
    # Realną kontrolą ekspozycji jest bramka ``z_bramka_api_v1(grupa=DANE)``
    # z ``api_v1/urls.py`` i przełącznik ``Uczelnia.api_v1_dane_bibliograficzne``.
    permission_classes = [AllowAny]

    def get_queryset(self):
        """Jeden queryset ``UNION`` ponad sześcioma modelami kosza.

        DLACZEGO UNION, A NIE SKLEJANIE LIST W PYTHONIE: stronicowanie ma
        sens tylko wtedy, gdy schodzi do bazy. Gdyby każde żądanie pobierało
        cały kosz i dopiero potem wycinało z niego stronę, koszt jednej
        odpowiedzi zostałby ten sam co bez stronicowania — a klient robiłby
        teraz N żądań zamiast jednego, więc **łączna** praca by wzrosła.
        Tak `ORDER BY` i `LIMIT/OFFSET` wykonuje PostgreSQL, a wraca dokładnie
        tyle wierszy, ile mieści strona.

        Kolumny są trzy i we wszystkich sześciu gałęziach mają ten sam
        kształt (wymóg ``UNION``): etykieta modelu, klucz główny, data.
        Etykieta jest stałą wstrzykniętą przez ``Value`` — inaczej po
        złączeniu nie dałoby się odróżnić, z którego modelu pochodzi wiersz
        (klucze główne kolidują między modelami).

        Sortowanie ``(deleted_at, etykieta, pk)``: sama data nie wystarcza,
        bo dwa rekordy skasowane w tej samej mikrosekundzie miałyby
        niezdeterminowaną kolejność, a to na granicy strony znaczy zgubiony
        albo zdublowany wiersz. PostgreSQL sortuje ``NULL`` na końcu przy
        ``ASC``, więc wiersze sprzed wprowadzenia ``deleted_at`` lądują tam,
        gdzie wcześniej stawiał je sort w Pythonie.
        """
        warunki = self._warunki_zakresu(self.request)
        uczelnia = self._uczelnia_do_zawezenia(self.request)

        galezie = [
            self._zawez_do_uczelni(
                model.deleted_objects.filter(**warunki), nazwa, uczelnia
            )
            # ``order_by()`` bez argumentów CZYŚCI porządek domyślny modelu.
            # Bez tego każda gałąź wnosi swoje ``Meta.ordering``
            # (``Autor.sort``, ``Praca_Doktorska.rok, tytul_oryginalny``) —
            # sortowanie po kolumnach, których nawet nie wybieramy, w wyniku
            # i tak nadpisane przez ``ORDER BY`` całości. Czysty koszt, a przy
            # tym kolumny spoza listy SELECT-a wewnątrz ``UNION`` to
            # konstrukcja, której nie każdy silnik przyjmie.
            .order_by()
            .annotate(**{KOLUMNA_MODELU: Value(nazwa, output_field=CharField())})
            .values_list(KOLUMNA_MODELU, "pk", "deleted_at")
            for nazwa, model in MODELE_NAGROBKOW.items()
        ]

        zlaczone = galezie[0].union(*galezie[1:], all=True)
        return zlaczone.order_by("deleted_at", KOLUMNA_MODELU, "pk")

    def list(self, request):
        queryset = self.get_queryset()

        strona = self.paginator.paginate_queryset(queryset, request, view=self)
        wiersze = [
            {"model": nazwa, "pk": pk, "usuniety_od": usuniety_od}
            for nazwa, pk, usuniety_od in strona
        ]
        return self.paginator.get_paginated_response(
            UsunietySerializer(wiersze, many=True).data
        )

    @property
    def paginator(self):
        """Paginator instancji — ``ViewSet`` (w odróżnieniu od
        ``GenericViewSet``) nie dostaje go z gotowej implementacji."""
        if not hasattr(self, "_paginator"):
            self._paginator = self.pagination_class()
        return self._paginator

    @staticmethod
    def _uczelnia_do_zawezenia(request):
        """Uczelnia oglądającego albo ``None`` (≤1 uczelnia: bez zawężania).

        Kosz jest per uczelnia: w instalacji wielouczelnianej endpoint
        pokazuje WYŁĄCZNIE nagrobki rekordów bieżącej uczelni (z domeny).
        Gdy uczelni nie da się ustalić przy kilku uczelniach — pusto
        (fail-closed: identyfikatory cudzych skasowanych rekordów nie
        wyciekają).
        """
        from bpp.models import Uczelnia

        if Uczelnia.objects.count() <= 1:
            return None
        uczelnia = Uczelnia.objects.get_for_request(request)
        return uczelnia if uczelnia is not None else False

    @staticmethod
    def _zawez_do_uczelni(qs, nazwa, uczelnia):
        from django.db.models import Q

        if uczelnia is None:
            return qs
        if uczelnia is False:
            return qs.none()
        warunek = Q()
        for sciezka in ATRYBUCJA_UCZELNI[nazwa]:
            warunek |= Q(**{sciezka: uczelnia})
        # Podzapytanie po pk (bez JOIN + DISTINCT w gałęzi UNION). Lookup
        # przez relację nie pyta menedżera dziecka, więc autorstwa
        # publikacji z kosza są widoczne — i o to tu chodzi.
        pasujace = qs.model.global_objects.filter(warunek).values("pk")
        return qs.filter(pk__in=pasujace)

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
