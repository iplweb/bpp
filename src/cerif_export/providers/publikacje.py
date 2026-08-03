"""Provider setu ``openaire_cris_publications``.

Set łączy **pięć** modeli, wyczerpywanych sekwencyjnie w kolejności
``wc``, ``wz``, ``pd``, ``ph``, ``zr``. Enumeracja NIE idzie po ``Rekord``
ani po widoku ``bpp_rekord``:

1. ``Rekord`` zeruje ``tom``, ``nr_zeszytu`` i ``strony``
   (``src/bpp/models/cache/rekord.py``), a to są ``Volume``, ``Issue``
   i ``StartPage``/``EndPage`` profilu CERIF;
2. widok unionuje także patenty (``bpp/migrations/0001_widoki_rekord.sql``),
   a patenty są w CERIF osobną encją w osobnym secie.

Tu mieszkają też predykaty widoczności ``Zrodlo`` i ``Konferencja``. Obie te
encje nie mają FK do uczelni ani pola opt-out — są widoczne **wyłącznie**
przez to, że wskazuje na nie eksportowana publikacja tego tenanta. Bez tego
warunku każdy tenant wyeksportowałby cały współdzielony słownik jako własny.
Definicje siedzą tutaj, a nie w ``konferencje.py``, bo są pochodną reguł
publikacji — inaczej powstałby cykl importów.
"""

from django.db.models import CharField, Prefetch, Q, Value

from bpp.models.konferencja import Konferencja
from bpp.models.praca_doktorska import Praca_Doktorska
from bpp.models.praca_habilitacyjna import Praca_Habilitacyjna
from bpp.models.system import Charakter_Formalny
from bpp.models.wydawnictwo_ciagle import (
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Ciagle_Streszczenie,
    Wydawnictwo_Ciagle_Tytul,
)
from bpp.models.wydawnictwo_zwarte import (
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
    Wydawnictwo_Zwarte_Streszczenie,
    Wydawnictwo_Zwarte_Tytul,
)
from bpp.models.zrodlo import Zrodlo
from cerif_export import const
from cerif_export.identyfikatory import BlednyIdentyfikator, slug_dla
from cerif_export.kontekst import ZbioryWidocznosci
from cerif_export.providers.base import ProviderEncji
from cerif_export.providers.jednostki import (
    widoczne_jednostki,
    widoczne_pk,
    wymagaj_uczelni,
)
from cerif_export.providers.osoby import widoczni_autorzy
from cerif_export.slowniki import coar

# Wydawnictwa: mają ``nie_eksportuj_przez_api`` i model autorstwa.
MODELE_WYDAWNICTW = (Wydawnictwo_Ciagle, Wydawnictwo_Zwarte)

# Prace dyplomowe: pojedyncze FK ``autor``/``jednostka``, BEZ pola opt-out
# (``ModelOpcjonalnieNieEksportowanyDoAPI`` nie jest w ich MRO — filtr po
# ``nie_eksportuj_przez_api`` dałby tu ``FieldError``).
MODELE_PRAC = (Praca_Doktorska, Praca_Habilitacyjna)

# Adnotacja z gotowym URI COAR dla prac dyplomowych — patrz ``coar_pracy``.
ADNOTACJA_COAR = "_cerif_coar"

# model pracy -> (skrót charakteru formalnego, URI awaryjny)
_COAR_PRAC = {
    Praca_Doktorska: ("D", coar.DOCTORAL_THESIS),
    Praca_Habilitacyjna: ("H", coar.THESIS),
}


# -- predykaty widoczności ----------------------------------------------


def _ukryte_statusy(uczelnia):
    """Podzapytanie ze statusami korekty wykluczonymi kanałem ``cerif``."""
    return uczelnia.ukryte_statusy("cerif")


def widoczne_wydawnictwa(model, uczelnia):
    """``Wydawnictwo_Ciagle``/``Zwarte`` eksportowane dla tej uczelni.

    Scope tenanta idzie przez model autorstwa (``pk__in`` z podzapytania,
    nie ``JOIN`` + ``DISTINCT``) — dzięki temu wynik da się bez efektów
    ubocznych zagnieżdżać w kolejnym podzapytaniu (``widoczne_zrodla``,
    ``widoczne_konferencje``).
    """
    wymagaj_uczelni(uczelnia)
    return (
        model.objects.exclude(status_korekty_id__in=_ukryte_statusy(uczelnia))
        .filter(nie_eksportuj_przez_api=False)
        .filter(
            pk__in=model.autor_rekordu_klass.objects.filter(
                jednostka__uczelnia=uczelnia
            ).values("rekord_id")
        )
    )


def widoczne_prace(model, uczelnia):
    """``Praca_Doktorska``/``Habilitacyjna`` eksportowane dla tej uczelni.

    Brak pola opt-out (świadomie — dołożenie go to osobna zmiana produktowa),
    scope tenanta przez bezpośredni FK ``jednostka``.
    """
    wymagaj_uczelni(uczelnia)
    return model.objects.exclude(
        status_korekty_id__in=_ukryte_statusy(uczelnia)
    ).filter(jednostka__uczelnia=uczelnia)


def widoczne_dla_modelu(model, uczelnia):
    """Predykat widoczności właściwy dla podanego modelu publikacji."""
    if model in MODELE_WYDAWNICTW:
        return widoczne_wydawnictwa(model, uczelnia)
    if model in MODELE_PRAC:
        return widoczne_prace(model, uczelnia)
    if model is Zrodlo:
        return widoczne_zrodla(uczelnia)
    raise BlednyIdentyfikator(
        f"Model {model!r} nie należy do setu {const.SET_PUBLICATIONS}"
    )


def widoczne_zrodla(uczelnia):
    """Źródła wskazywane przez co najmniej jedno widoczne wydawnictwo ciągłe.

    Tylko ``Wydawnictwo_Ciagle`` ma FK ``zrodlo`` — zwarte, doktoraty i
    habilitacje nie wskazują kanału wydawniczego.
    """
    wymagaj_uczelni(uczelnia)
    return Zrodlo.objects.filter(
        pk__in=widoczne_wydawnictwa(Wydawnictwo_Ciagle, uczelnia)
        .filter(zrodlo__isnull=False)
        .values("zrodlo_id")
    )


def widoczne_konferencje(uczelnia):
    """Konferencje wskazywane przez co najmniej jedną widoczną publikację.

    ``konferencja`` jest na ``Wydawnictwo_Ciagle`` i ``Wydawnictwo_Zwarte``
    (mixin ``ModelZKonferencja``); prace dyplomowe jej nie mają.
    """
    wymagaj_uczelni(uczelnia)
    warunek = Q()
    for model in MODELE_WYDAWNICTW:
        warunek |= Q(
            pk__in=widoczne_wydawnictwa(model, uczelnia)
            .filter(konferencja__isnull=False)
            .values("konferencja_id")
        )
    return Konferencja.objects.filter(warunek)


# -- typ COAR prac dyplomowych ------------------------------------------


def coar_pracy(model) -> str:
    """URI COAR dla pracy doktorskiej/habilitacyjnej.

    PD/PH nie mają FK ``charakter_formalny`` — jest to ``cached_property``
    wołające ``Charakter_Formalny.objects.get(skrot="D")``. Wywołane z
    serializera byłoby to lazy DB-hit, a przy przemianowanym słowniku wprost
    ``DoesNotExist``. Rozstrzyga więc provider: raz na queryset, z fallbackiem
    na stałą profilu, gdy wiersza słownika nie ma.
    """
    skrot, awaryjny = _COAR_PRAC[model]
    coar_type = (
        Charakter_Formalny.objects.filter(skrot=skrot)
        .values_list("coar_type", flat=True)
        .first()
    )
    return coar_type or awaryjny


# -- prefetche ----------------------------------------------------------

_AUTORSTWA = {
    Wydawnictwo_Ciagle: Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte: Wydawnictwo_Zwarte_Autor,
}
_TYTULY = {
    Wydawnictwo_Ciagle: Wydawnictwo_Ciagle_Tytul,
    Wydawnictwo_Zwarte: Wydawnictwo_Zwarte_Tytul,
}
_STRESZCZENIA = {
    Wydawnictwo_Ciagle: Wydawnictwo_Ciagle_Streszczenie,
    Wydawnictwo_Zwarte: Wydawnictwo_Zwarte_Streszczenie,
}


def _prefetche_wydawnictwa(model):
    """Komplet prefetchy dla wydawnictwa ciągłego/zwartego.

    UWAGA: ``Element_Repozytorium`` (``FileLocations``) NIE jest tu
    prefetchowany. To ``GenericForeignKey`` bez odpowiadającej mu
    ``GenericRelation`` na modelach ``bpp`` — ``prefetch_related`` nie ma się
    czego złapać. Domknięcie tego wymaga zmiany w ``src/bpp/models/`` (dodania
    ``GenericRelation``), poza zakresem providerów.
    """
    return [
        "slowa_kluczowe",
        Prefetch(
            "autorzy_set",
            queryset=_AUTORSTWA[model]
            .objects.select_related("autor", "jednostka", "typ_odpowiedzialnosci")
            .order_by("kolejnosc"),
        ),
        Prefetch(
            "dodatkowe_tytuly",
            queryset=_TYTULY[model].objects.select_related("jezyk"),
        ),
        Prefetch(
            "streszczenia",
            queryset=_STRESZCZENIA[model].objects.select_related("jezyk_streszczenia"),
        ),
    ]


_SELECT_WYDAWNICTWA = (
    "charakter_formalny",
    "jezyk",
    "jezyk_alt",
    "jezyk_orig",
    "typ_kbn",
    "status_korekty",
    "konferencja",
    "openaccess_tryb_dostepu",
    "openaccess_wersja_tekstu",
    "openaccess_licencja",
    "openaccess_czas_publikacji",
)

_SELECT_PRACY = (
    "jezyk",
    "jezyk_alt",
    "jezyk_orig",
    "typ_kbn",
    "status_korekty",
    "wydawca",
    "jednostka",
    "jednostka__uczelnia",
    "autor",
    "autor__plec",
)


class ProviderPublikacji(ProviderEncji):
    """Publikacje wszystkich pięciu typów + kanały wydawnicze."""

    set_spec = const.SET_PUBLICATIONS
    typ_cerif = const.TYP_PUBLICATION
    modele = [
        Wydawnictwo_Ciagle,
        Wydawnictwo_Zwarte,
        Praca_Doktorska,
        Praca_Habilitacyjna,
        Zrodlo,
    ]

    def queryset(self, uczelnia, model):
        wymagaj_uczelni(uczelnia)

        if model is Wydawnictwo_Ciagle:
            return (
                widoczne_wydawnictwa(model, uczelnia)
                .select_related(*_SELECT_WYDAWNICTWA, "zrodlo", "zrodlo__jezyk")
                .prefetch_related(*_prefetche_wydawnictwa(model))
            )

        if model is Wydawnictwo_Zwarte:
            return (
                widoczne_wydawnictwa(model, uczelnia)
                .select_related(
                    *_SELECT_WYDAWNICTWA,
                    "wydawca",
                    "wydawnictwo_nadrzedne",
                    "seria_wydawnicza",
                )
                .prefetch_related(*_prefetche_wydawnictwa(model))
            )

        if model in MODELE_PRAC:
            return (
                widoczne_prace(model, uczelnia)
                .select_related(*_SELECT_PRACY)
                .prefetch_related("slowa_kluczowe")
                .annotate(
                    **{
                        ADNOTACJA_COAR: Value(
                            coar_pracy(model), output_field=CharField()
                        )
                    }
                )
            )

        if model is Zrodlo:
            return widoczne_zrodla(uczelnia).select_related(
                "rodzaj", "jezyk", "openaccess_licencja", "pbn_uid"
            )

        raise BlednyIdentyfikator(f"Model {model!r} nie należy do setu {self.set_spec}")

    def zbiory_widocznosci(self, uczelnia, obiekty) -> ZbioryWidocznosci:
        """Prekomputuj widoczność encji osadzanych przy publikacjach.

        Jedno zapytanie na typ encji, niezależnie od rozmiaru partii.
        Zbieranie kandydatów korzysta wyłącznie z prefetchy założonych w
        :meth:`queryset` — nie dotyka bazy.
        """
        wymagaj_uczelni(uczelnia)

        autorzy, jednostki, zrodla, konferencje = set(), set(), set(), set()
        nadrzedne = set()

        for obj in obiekty:
            if isinstance(obj, Zrodlo):
                # Kanał wydawniczy nie osadza encji sąsiadujących.
                continue

            zrodla.add(getattr(obj, "zrodlo_id", None))
            konferencje.add(getattr(obj, "konferencja_id", None))
            nadrzedne.add(getattr(obj, "wydawnictwo_nadrzedne_id", None))

            if isinstance(obj, MODELE_PRAC):
                # Promotor świadomie pomijany: COAR/CERIF nie zna tej roli.
                autorzy.add(obj.autor_id)
                jednostki.add(obj.jednostka_id)
                continue

            for autorstwo in obj.autorzy_set.all():
                autorzy.add(autorstwo.autor_id)
                jednostki.add(autorstwo.jednostka_id)

        return ZbioryWidocznosci(
            autorzy=widoczne_pk(widoczni_autorzy(uczelnia), autorzy),
            jednostki=widoczne_pk(widoczne_jednostki(uczelnia), jednostki),
            zrodla=widoczne_pk(widoczne_zrodla(uczelnia), zrodla),
            konferencje=widoczne_pk(widoczne_konferencje(uczelnia), konferencje),
            publikacje=frozenset(
                (slug_dla(Wydawnictwo_Zwarte), pk)
                for pk in widoczne_pk(
                    widoczne_wydawnictwa(Wydawnictwo_Zwarte, uczelnia), nadrzedne
                )
            ),
        )
