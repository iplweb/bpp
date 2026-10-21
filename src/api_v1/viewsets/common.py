from django.utils.functional import cached_property
from rest_framework.pagination import PageNumberPagination

from bpp.models import Uczelnia
from bpp.util.uczelnia_scope import scope_publikacje_do_uczelni


class UkryjStatusyKorektyMixin:
    @cached_property
    def ukryte_statusy(self):
        uczelnia = Uczelnia.objects.get_for_request(self.request)
        if uczelnia:
            ukryte_statusy = uczelnia.ukryte_statusy("api")
            return ukryte_statusy

    def get_queryset(self):
        queryset = super().get_queryset()

        if self.ukryte_statusy:
            queryset = queryset.exclude(status_korekty_id__in=self.ukryte_statusy)

        return queryset


class UkryjNieEksportowaneMixin:
    """Ukrywa child-rekordy, których rekord nadrzędny ma ustawioną flagę
    ``nie_eksportuj_przez_api``.

    Główne viewsety publikacji filtrują to na poziomie rekordu, ale endpointy
    podrzędne (streszczenia, autorstwa, identyfikatory zewnętrznych baz) jadą
    na globalnym querysecie modelu-dziecka — bez tego mixina anonimowy
    użytkownik mógłby enumerować ich PK i wyciągać dane rekordu chronionego.

    ``parent_lookup`` to nazwa relacji prowadzącej do rekordu nadrzędnego
    (domyślnie ``rekord``); nadpisz na podklasie, jeśli child używa innej.
    """

    parent_lookup = "rekord"

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.exclude(
            **{f"{self.parent_lookup}__nie_eksportuj_przez_api": True}
        )


class UkryjStatusyKorektyRekorduMixin:
    """Wersja :class:`UkryjStatusyKorektyMixin` dla endpointów podrzędnych.

    Ukrywa child-rekordy, których rekord nadrzędny ma status korekty ukryty
    dla API (``ukryte_statusy("api")``). Parent viewsety robią to bezpośrednio
    (pole ``status_korekty`` na rekordzie); child docierają do statusu przez
    relację ``parent_lookup``. Uzupełnia :class:`UkryjNieEksportowaneMixin`
    o wymiar statusów korekty — oba stosowane razem dają na pod-zasobie tę
    samą widoczność co na rekordzie-rodzicu.
    """

    parent_lookup = "rekord"

    def get_queryset(self):
        queryset = super().get_queryset()

        uczelnia = Uczelnia.objects.get_for_request(self.request)
        if uczelnia:
            ukryte_statusy = uczelnia.ukryte_statusy("api")
            if ukryte_statusy:
                queryset = queryset.exclude(
                    **{f"{self.parent_lookup}__status_korekty_id__in": ukryte_statusy}
                )

        return queryset


class ZawezDoUczelniMixin:
    """Zawęża publikacje (i ich pod-zasoby) do uczelni z bieżącego ``Host``.

    Domyka dryf polityki widoczności (#808): ``/api/v1/szukaj/``,
    ``/api/v1/zapytanie/rekord/`` i endpointy „recent" stosują
    ``api_v1.scoping.scope_rekord_api`` (uczelnia + ukryte statusy +
    ``nie_eksportuj_przez_api``), a typowane viewsety miały tylko dwie
    ostatnie warstwy — w instalacji wielouczelnianej oddawały rekordy
    wszystkich uczelni. Reguła atrybucji jest ta sama co dla ``Rekord``
    (``scope_publikacje_do_uczelni``); w instalacji jednouczelnianej no-op.

    ``uczelnia_lookup`` — ścieżka ORM do ``Jednostka`` autorstwa; endpointy
    podrzędne nadpisują ją ścieżką przez rekord nadrzędny.
    """

    uczelnia_lookup = "autorzy_set__jednostka"

    def get_queryset(self):
        queryset = super().get_queryset()
        uczelnia = Uczelnia.objects.get_for_request(self.request)
        return scope_publikacje_do_uczelni(queryset, uczelnia, self.uczelnia_lookup)


class StreszczeniaPagination(PageNumberPagination):
    page_size = 1
    page_size_query_param = "page_size"
    max_page_size = 5
