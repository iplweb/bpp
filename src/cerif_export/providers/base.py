"""Kontrakt providera encji.

Provider odpowiada za dostęp do danych: zwraca strony obiektów ORM
scope'owanych do uczelni, z kompletem ``select_related``/``prefetch_related``
potrzebnym serializerowi, oraz prekomputuje zbiory widoczności.

Provider **nie wie nic** o XML-u, OAI-PMH ani o HTTP.
"""

from django.db.models import Value
from django.db.models.functions import Coalesce

from cerif_export import const, identyfikatory
from cerif_export.kontekst import Kursor, ZbioryWidocznosci

# Nazwa adnotacji z datą modyfikacji sprowadzoną do wartości nie-NULL.
ADNOTACJA_TS = "_cerif_ts"


def z_datestampem(queryset, pole="ostatnio_zmieniony"):
    """Dodaj adnotację ``_cerif_ts`` = DATE_TRUNC('second', COALESCE(pole, EPOKA)).

    ``ostatnio_zmieniony`` z ``ModelZAdnotacjami`` jest ``null=True``. Bez
    COALESCE rekordy z NULL-em wypadłyby zarówno z sortowania keyset, jak
    i z filtrów ``from``/``until`` — czyli po cichu nie trafiłyby do
    harvestu.

    Obcięcie do pełnych sekund NIE jest kosmetyką. ``Kursor.ts`` niesie
    datestamp w granularity profilu (``YYYY-MM-DDThh:mm:ssZ``), więc bez
    obcięcia klucz sortowania miałby mikrosekundy, a kursor już nie:
    warunek ``ts > kursor.ts`` przepuszczałby z powrotem rekord, na którym
    strona się skończyła, i harvester dostawał BY DUPLIKAT na każdej granicy
    strony. Po obcięciu wartość sortowana, wartość w kursorze i wartość
    w ``<datestamp>`` to dokładnie ta sama liczba; remisy w obrębie sekundy
    rozstrzyga ``pk``.
    """
    from django.db.models import DateTimeField
    from django.db.models.functions import Trunc

    return queryset.annotate(
        **{
            ADNOTACJA_TS: Trunc(
                Coalesce(
                    pole,
                    Value(const.EPOKA_DT),
                    output_field=DateTimeField(),
                ),
                "second",
                output_field=DateTimeField(),
            )
        }
    )


def na_datestamp(wartosc) -> str:
    """Sformatuj datę na potrzeby OAI-PMH (UTC, granularity z profilu)."""
    if wartosc is None:
        return const.EPOKA
    if getattr(wartosc, "tzinfo", None) is not None:
        from django.utils import timezone

        wartosc = wartosc.astimezone(timezone.utc)
    return wartosc.strftime(const.FORMAT_DATESTAMP)


class ProviderEncji:
    """Bazowa klasa providera.

    Podklasa deklaruje ``set_spec``, ``typ_cerif`` i ``modele`` (w porządku
    wyczerpywania) oraz implementuje ``queryset`` i ``zbiory_widocznosci``.
    """

    set_spec: str = ""
    typ_cerif: str = ""
    modele: list = []

    def queryset(self, uczelnia, model):
        """Bazowy queryset danego modelu, przefiltrowany regułami widoczności
        i z kompletem prefetchy potrzebnym serializerowi."""
        raise NotImplementedError

    def zbiory_widocznosci(self, uczelnia, obiekty) -> ZbioryWidocznosci:
        """Prekomputuj klucze encji sąsiadujących, które wyjdą w swoich
        setach — dla podanej partii obiektów."""
        raise NotImplementedError

    # -- stronicowanie keyset -------------------------------------------

    def strona(self, uczelnia, od=None, do=None, kursor=None, rozmiar=None):
        """Zwróć ``(obiekty, kolejny_kursor)``.

        Modele wyczerpywane są sekwencyjnie w kolejności ``self.modele``;
        w obrębie modelu porządek to ``(COALESCE(ostatnio_zmieniony, EPOKA),
        pk)``. Kursor niesie slug, bo klucze główne kolidują między modelami.

        Kursor zawsze wskazuje **ostatni wydany rekord**, nigdy pozycji
        syntetycznej. ``None`` w drugim elemencie znaczy, że nie ma już nic —
        i jest to sprawdzane sondą, a nie wnioskowane z tego, że strona
        wyszła pełna. Inaczej harvester dostawałby resumption token
        prowadzący do pustej strony.
        """
        rozmiar = rozmiar or const.ROZMIAR_STRONY
        modele = list(self.modele)
        if not modele or rozmiar <= 0:
            return [], None

        slugi = [identyfikatory.slug_dla(model) for model in modele]

        indeks_startowy = 0
        if kursor is not None:
            if kursor.slug not in slugi:
                raise identyfikatory.BlednyIdentyfikator(
                    f"Kursor wskazuje slug {kursor.slug!r} spoza tego setu"
                )
            indeks_startowy = slugi.index(kursor.slug)

        zebrane = []
        for indeks in range(indeks_startowy, len(modele)):
            model = modele[indeks]
            wewnetrzny = kursor if indeks == indeks_startowy else None

            brakuje = rozmiar - len(zebrane)
            # Pobieramy o jeden rekord za dużo — to sonda mówiąca, czy
            # w tym modelu zostało jeszcze cokolwiek.
            partia = list(
                self._strona_modelu(uczelnia, model, od, do, wewnetrzny, brakuje + 1)
            )

            if len(partia) > brakuje:
                partia = partia[:brakuje]
                zebrane.extend(partia)
                return zebrane, self._kursor(slugi[indeks], partia[-1])

            zebrane.extend(partia)

            if len(zebrane) >= rozmiar:
                # Strona pełna, bieżący model wyczerpany (sonda nic nie
                # dołożyła). Token wydajemy tylko, gdy realnie jest co
                # jeszcze pokazać.
                if self._istnieje_dalej(uczelnia, modele, indeks, od, do):
                    return zebrane, self._kursor(slugi[indeks], zebrane[-1])
                return zebrane, None

        return zebrane, None

    def _istnieje_dalej(self, uczelnia, modele, indeks, od, do):
        """Czy w modelach po ``indeks`` został jeszcze jakikolwiek rekord?"""
        for model in modele[indeks + 1 :]:
            if self._strona_modelu(uczelnia, model, od, do, None, 1):
                return True
        return False

    def _kursor(self, slug, obiekt):
        """Kursor wskazujący podany rekord.

        Znacznik idzie przez ``na_datestamp``, bo adnotacja ``_cerif_ts``
        jest już obcięta do sekundy przez ``Trunc`` w SQL-u — klucz
        sortowania i ``<datestamp>`` w odpowiedzi OAI to ta sama wartość.
        Rekordy z tej samej sekundy rozróżnia ``pk`` w drugim członie
        warunku keyset, więc nic się nie dubluje ani nie gubi.
        """
        return Kursor(
            slug=slug,
            ts=na_datestamp(getattr(obiekt, ADNOTACJA_TS, None)),
            pk=obiekt.pk,
        )

    def _strona_modelu(self, uczelnia, model, od, do, kursor, limit):
        from django.db.models import Q

        qs = z_datestampem(self.queryset(uczelnia, model))

        if od is not None:
            qs = qs.filter(**{f"{ADNOTACJA_TS}__gte": od})
        if do is not None:
            qs = qs.filter(**{f"{ADNOTACJA_TS}__lte": do})

        if kursor is not None:
            qs = qs.filter(
                Q(**{f"{ADNOTACJA_TS}__gt": kursor.ts})
                | Q(**{ADNOTACJA_TS: kursor.ts, "pk__gt": kursor.pk})
            )

        return qs.order_by(ADNOTACJA_TS, "pk")[:limit]

    # -- pozostałe operacje ---------------------------------------------

    def pojedynczy(self, uczelnia, model, pk):
        """Pojedynczy obiekt albo ``None``, gdy niewidoczny."""
        return z_datestampem(self.queryset(uczelnia, model)).filter(pk=pk).first()

    def najstarszy_datestamp(self, uczelnia):
        """Najstarszy datestamp w secie albo ``None``, gdy set pusty."""
        najstarszy = None
        for model in self.modele:
            wiersz = (
                z_datestampem(self.queryset(uczelnia, model))
                .order_by(ADNOTACJA_TS)
                .values_list(ADNOTACJA_TS, flat=True)
                .first()
            )
            if wiersz is not None and (najstarszy is None or wiersz < najstarszy):
                najstarszy = wiersz
        return najstarszy


class ProviderPusty(ProviderEncji):
    """Provider setu, który istnieje, ale nie ma zawartości.

    Profil wymaga, żeby wszystkie dziewięć setów było zadeklarowane —
    także te, których BPP nie wypełnia (products, equipment, projects,
    funding).
    """

    modele: list = []

    def queryset(self, uczelnia, model):
        raise NotImplementedError("Set pusty nie ma modeli")

    def zbiory_widocznosci(self, uczelnia, obiekty) -> ZbioryWidocznosci:
        return ZbioryWidocznosci()

    def strona(self, uczelnia, od=None, do=None, kursor=None, rozmiar=None):
        return [], None

    def pojedynczy(self, uczelnia, model, pk):
        return None

    def najstarszy_datestamp(self, uczelnia):
        return None
