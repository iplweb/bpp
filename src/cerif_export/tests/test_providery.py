"""Testy providerów: stronicowanie keyset, ``from``/``until``, liczba zapytań.

Najważniejsze niezmienniki pilnowane tutaj:

* set ``publications`` łączy pięć modeli i **przejście granicy między nimi**
  nie może ani zgubić, ani zdublować rekordu;
* rekord z ``ostatnio_zmieniony IS NULL`` musi wyjść w harveście (bez
  ``COALESCE`` wypadłby i z sortowania, i z filtrów zakresu);
* liczba zapytań na stronę **nie rośnie** z liczbą rekordów — serializer
  dostaje komplet prefetchy i nie ma prawa dotknąć bazy.
"""

import datetime

import pytest
from django.contrib.sites.models import Site
from model_bakery import baker

from bpp.models.autor import Autor
from bpp.models.jednostka import Jednostka
from bpp.models.konferencja import Konferencja
from bpp.models.patent import Patent
from bpp.models.praca_doktorska import Praca_Doktorska
from bpp.models.praca_habilitacyjna import Praca_Habilitacyjna
from bpp.models.system import Charakter_Formalny, Status_Korekty, Typ_Odpowiedzialnosci
from bpp.models.uczelnia import Uczelnia
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from bpp.models.zrodlo import Zrodlo
from cerif_export import const
from cerif_export.identyfikatory import BlednyIdentyfikator, slug_dla
from cerif_export.kontekst import Kursor
from cerif_export.providers import (
    PROVIDERY,
    PROVIDERY_WG_SETU,
    provider_dla_modelu,
    provider_dla_setu,
)
from cerif_export.providers.base import ADNOTACJA_TS
from cerif_export.providers.publikacje import ADNOTACJA_COAR, coar_pracy

# -- helpery budujące dane ----------------------------------------------


def zbuduj_uczelnie(nazwa, skrot, domena):
    site = Site.objects.create(domain=domena, name=domena)
    return Uczelnia.objects.create(nazwa=nazwa, skrot=skrot, site=site)


def zbuduj_jednostke(uczelnia, nazwa, skrot):
    return Jednostka.objects.create(nazwa=nazwa, skrot=skrot, uczelnia=uczelnia)


def zbuduj_autora(nazwisko, pokazuj=True):
    return baker.make(Autor, nazwisko=nazwisko, imiona="Jan", pokazuj=pokazuj)


def ustaw_datestamp(model, pk, wartosc):
    """Ustaw ``ostatnio_zmieniony`` z pominięciem ``auto_now``.

    Pole ma ``auto_now=True``, więc zwykły ``save()`` nadpisałby wartość
    bieżącym czasem — jedyne wyjście to ``UPDATE`` przez queryset.
    """
    model.objects.filter(pk=pk).update(ostatnio_zmieniony=wartosc)


def dt(dzien):
    return datetime.datetime(2020, 1, dzien, 12, 0, 0, tzinfo=datetime.UTC)


# -- fixtures -----------------------------------------------------------


@pytest.fixture
def uczelnia_cerif(db):
    return zbuduj_uczelnie("Uczelnia CERIF", "UCE", "cerif.example.org")


@pytest.fixture
def jednostka_cerif(uczelnia_cerif):
    return zbuduj_jednostke(uczelnia_cerif, "Jednostka CERIF", "JCE")


@pytest.fixture
def typ_autor(db):
    return Typ_Odpowiedzialnosci.objects.get_or_create(
        skrot="aut.", defaults={"nazwa": "autor"}
    )[0]


@pytest.fixture
def status_ok(db):
    return Status_Korekty.objects.get_or_create(nazwa="po korekcie")[0]


@pytest.fixture
def autor_cerif(jednostka_cerif):
    return zbuduj_autora("Kowalski")


@pytest.fixture
def fabryka_wydawnictw(jednostka_cerif, typ_autor, status_ok, autor_cerif):
    """Zwraca funkcję tworzącą widoczne wydawnictwo z jednym autorstwem."""

    def zbuduj(model, **kwargs):
        kwargs.setdefault("status_korekty", status_ok)
        kwargs.setdefault("nie_eksportuj_przez_api", False)
        kwargs.setdefault("rok", 2020)
        rekord = baker.make(model, **kwargs)
        rekord.dodaj_autora(autor_cerif, jednostka_cerif)
        return rekord

    return zbuduj


@pytest.fixture
def provider_publikacji():
    return provider_dla_setu(const.SET_PUBLICATIONS)


# -- rejestr ------------------------------------------------------------


def test_rejestr_pokrywa_wszystkie_sety_profilu():
    """Profil wymaga dziewięciu setów — także tych, których BPP nie wypełnia."""
    assert set(PROVIDERY_WG_SETU) == set(const.WSZYSTKIE_SETY)
    assert len(PROVIDERY) == len(const.WSZYSTKIE_SETY)


def test_rejestr_odnajduje_provider_po_modelu():
    assert provider_dla_modelu(Wydawnictwo_Ciagle).set_spec == const.SET_PUBLICATIONS
    assert provider_dla_modelu(Zrodlo).set_spec == const.SET_PUBLICATIONS
    assert provider_dla_modelu(Autor).set_spec == const.SET_PERSONS
    assert provider_dla_modelu(Uczelnia).set_spec == const.SET_ORGUNITS
    assert provider_dla_modelu(Patent).set_spec == const.SET_PATENTS
    assert provider_dla_modelu(Konferencja).set_spec == const.SET_EVENTS


def test_rejestr_odrzuca_model_spoza_eksportu():
    with pytest.raises(BlednyIdentyfikator):
        provider_dla_modelu(Site)


def test_publikacje_nie_uzywaja_modelu_rekord(provider_publikacji):
    """Enumeracja idzie po pięciu konkretnych modelach, nie po ``Rekord``.

    ``Rekord`` zeruje ``tom``/``nr_zeszytu``/``strony`` i unionuje patenty —
    użycie go tutaj byłoby cichą utratą danych.
    """
    assert provider_publikacji.modele == [
        Wydawnictwo_Ciagle,
        Wydawnictwo_Zwarte,
        Praca_Doktorska,
        Praca_Habilitacyjna,
        Zrodlo,
    ]
    nazwy = {m.__name__ for m in provider_publikacji.modele}
    assert "Rekord" not in nazwy
    assert "Patent" not in nazwy


# -- stronicowanie keyset -----------------------------------------------


@pytest.mark.django_db
def test_strona_zwraca_kursor_wewnatrz_modelu(
    uczelnia_cerif, fabryka_wydawnictw, provider_publikacji
):
    for i in range(3):
        rekord = fabryka_wydawnictw(Wydawnictwo_Ciagle)
        ustaw_datestamp(Wydawnictwo_Ciagle, rekord.pk, dt(1 + i))

    obiekty, kursor = provider_publikacji.strona(uczelnia_cerif, rozmiar=2)

    assert len(obiekty) == 2
    assert kursor is not None
    assert kursor.slug == slug_dla(Wydawnictwo_Ciagle)
    assert kursor.pk == obiekty[-1].pk

    reszta, kolejny = provider_publikacji.strona(
        uczelnia_cerif, kursor=kursor, rozmiar=2
    )
    assert len(reszta) == 1
    assert kolejny is None


@pytest.mark.django_db
def test_strona_przechodzi_granice_miedzy_modelami(
    uczelnia_cerif, fabryka_wydawnictw, provider_publikacji
):
    """Granica ``wc`` → ``wz`` w obrębie jednego setu.

    Klucze główne kolidują między modelami, więc bez sluga w kursorze druga
    strona albo zgubiłaby rekordy, albo zwróciła duplikaty.
    """
    ciagle = [fabryka_wydawnictw(Wydawnictwo_Ciagle) for _ in range(2)]
    zwarte = [fabryka_wydawnictw(Wydawnictwo_Zwarte) for _ in range(2)]

    strony = list(_przejdz_wszystkie_strony(provider_publikacji, uczelnia_cerif, 3))

    assert [len(s) for s in strony] == [3, 1]

    zebrane = [(slug_dla(o), o.pk) for s in strony for o in s]
    oczekiwane = [(slug_dla(Wydawnictwo_Ciagle), o.pk) for o in ciagle] + [
        (slug_dla(Wydawnictwo_Zwarte), o.pk) for o in zwarte
    ]
    assert sorted(zebrane) == sorted(oczekiwane)
    assert len(zebrane) == len(set(zebrane)), "rekord wyszedł dwa razy"


@pytest.mark.django_db
def test_kursor_na_granicy_modelu_wskazuje_ostatni_wydany_rekord(
    uczelnia_cerif, fabryka_wydawnictw, provider_publikacji
):
    """Wyczerpanie modelu NIE produkuje pozycji syntetycznej.

    Kursor zawsze wskazuje ostatni faktycznie wydany rekord. Wcześniejszy
    wariant zwracał tu ``Kursor(slug=<kolejny model>, ts=EPOKA, pk=0)``,
    co miało dwie wady: wznowienie od takiej pozycji wymagało osobnej
    ścieżki w kodzie, a gdy wszystkie kolejne modele były puste, harvester
    dostawał resumption token prowadzący do pustej strony.
    """
    for _ in range(2):
        fabryka_wydawnictw(Wydawnictwo_Ciagle)
    for _ in range(2):
        fabryka_wydawnictw(Wydawnictwo_Zwarte)

    obiekty, kursor = provider_publikacji.strona(uczelnia_cerif, rozmiar=2)

    assert {slug_dla(o) for o in obiekty} == {slug_dla(Wydawnictwo_Ciagle)}
    assert kursor is not None
    assert kursor.slug == slug_dla(Wydawnictwo_Ciagle)
    assert kursor.pk == obiekty[-1].pk

    reszta, kolejny = provider_publikacji.strona(
        uczelnia_cerif, kursor=kursor, rozmiar=2
    )
    assert {slug_dla(o) for o in reszta} == {slug_dla(Wydawnictwo_Zwarte)}
    assert kolejny is None


@pytest.mark.django_db
def test_brak_tokenu_gdy_kolejne_modele_sa_puste(
    uczelnia_cerif, fabryka_wydawnictw, provider_publikacji
):
    """Strona wypełniona co do rekordu, a dalej pustka → kursor ``None``.

    Regresja: wcześniej sam fakt, że strona wyszła pełna, wystarczał do
    wydania tokenu — harvester dostawał go nawet wtedy, gdy nie było już
    czego pobrać.
    """
    for _ in range(2):
        fabryka_wydawnictw(Wydawnictwo_Ciagle)

    obiekty, kursor = provider_publikacji.strona(uczelnia_cerif, rozmiar=2)

    assert len(obiekty) == 2
    assert kursor is None


@pytest.mark.django_db
def test_strona_obejmuje_wszystkie_piec_modeli(
    uczelnia_cerif,
    jednostka_cerif,
    fabryka_wydawnictw,
    status_ok,
    provider_publikacji,
):
    """Pełny harvest setu ``publications`` po jednym rekordzie każdego typu."""
    wc = fabryka_wydawnictw(Wydawnictwo_Ciagle)
    wz = fabryka_wydawnictw(Wydawnictwo_Zwarte)
    pd = baker.make(
        Praca_Doktorska,
        jednostka=jednostka_cerif,
        autor=zbuduj_autora("Doktorant"),
        status_korekty=status_ok,
        rok=2020,
    )
    ph = baker.make(
        Praca_Habilitacyjna,
        jednostka=jednostka_cerif,
        autor=zbuduj_autora("Habilitant"),
        status_korekty=status_ok,
        rok=2020,
    )

    zrodlo = baker.make(Zrodlo, nazwa="Czasopismo", skrot="Czas.")
    wc.zrodlo = zrodlo
    wc.save()

    zebrane = [
        (slug_dla(o), o.pk)
        for strona in _przejdz_wszystkie_strony(provider_publikacji, uczelnia_cerif, 2)
        for o in strona
    ]

    assert sorted(zebrane) == sorted(
        [
            (slug_dla(Wydawnictwo_Ciagle), wc.pk),
            (slug_dla(Wydawnictwo_Zwarte), wz.pk),
            (slug_dla(Praca_Doktorska), pd.pk),
            (slug_dla(Praca_Habilitacyjna), ph.pk),
            (slug_dla(Zrodlo), zrodlo.pk),
        ]
    )


@pytest.mark.django_db
def test_kursor_spoza_setu_podnosi_blad(uczelnia_cerif, provider_publikacji):
    with pytest.raises(BlednyIdentyfikator):
        provider_publikacji.strona(
            uczelnia_cerif, kursor=Kursor(slug="au", ts=const.EPOKA, pk=0)
        )


# -- datestampy ---------------------------------------------------------


@pytest.mark.django_db
def test_rekord_z_nullowym_datestampem_nie_ginie(
    uczelnia_cerif, fabryka_wydawnictw, provider_publikacji
):
    """``ostatnio_zmieniony IS NULL`` → traktowany jak EPOKA, nie znika."""
    z_nullem = fabryka_wydawnictw(Wydawnictwo_Ciagle)
    ustaw_datestamp(Wydawnictwo_Ciagle, z_nullem.pk, None)

    zwykly = fabryka_wydawnictw(Wydawnictwo_Ciagle)
    ustaw_datestamp(Wydawnictwo_Ciagle, zwykly.pk, dt(5))

    obiekty, _ = provider_publikacji.strona(uczelnia_cerif)
    pk_wc = [o.pk for o in obiekty if isinstance(o, Wydawnictwo_Ciagle)]

    assert z_nullem.pk in pk_wc
    # EPOKA jest najstarsza, więc rekord z NULL-em idzie pierwszy.
    assert pk_wc[0] == z_nullem.pk
    assert getattr(obiekty[0], ADNOTACJA_TS) == const.EPOKA_DT


@pytest.mark.django_db
def test_rekord_z_nullowym_datestampem_lapie_sie_w_zakres(
    uczelnia_cerif, fabryka_wydawnictw, provider_publikacji
):
    """Rekord z NULL-em musi dać się zharvestować filtrem ``until``."""
    z_nullem = fabryka_wydawnictw(Wydawnictwo_Ciagle)
    ustaw_datestamp(Wydawnictwo_Ciagle, z_nullem.pk, None)

    obiekty, _ = provider_publikacji.strona(uczelnia_cerif, do=dt(1))
    assert [o.pk for o in obiekty if isinstance(o, Wydawnictwo_Ciagle)] == [z_nullem.pk]


@pytest.mark.django_db
def test_filtry_od_do_zawezaja_wynik(
    uczelnia_cerif, fabryka_wydawnictw, provider_publikacji
):
    stary = fabryka_wydawnictw(Wydawnictwo_Ciagle)
    ustaw_datestamp(Wydawnictwo_Ciagle, stary.pk, dt(1))

    srodkowy = fabryka_wydawnictw(Wydawnictwo_Ciagle)
    ustaw_datestamp(Wydawnictwo_Ciagle, srodkowy.pk, dt(10))

    nowy = fabryka_wydawnictw(Wydawnictwo_Ciagle)
    ustaw_datestamp(Wydawnictwo_Ciagle, nowy.pk, dt(20))

    obiekty, _ = provider_publikacji.strona(uczelnia_cerif, od=dt(5), do=dt(15))
    assert [o.pk for o in obiekty] == [srodkowy.pk]

    obiekty, _ = provider_publikacji.strona(uczelnia_cerif, od=dt(5))
    assert [o.pk for o in obiekty] == [srodkowy.pk, nowy.pk]

    obiekty, _ = provider_publikacji.strona(uczelnia_cerif, do=dt(15))
    assert [o.pk for o in obiekty] == [stary.pk, srodkowy.pk]


@pytest.mark.django_db
def test_najstarszy_datestamp_bierze_minimum_ze_wszystkich_modeli(
    uczelnia_cerif, fabryka_wydawnictw, provider_publikacji
):
    wc = fabryka_wydawnictw(Wydawnictwo_Ciagle)
    ustaw_datestamp(Wydawnictwo_Ciagle, wc.pk, dt(20))

    wz = fabryka_wydawnictw(Wydawnictwo_Zwarte)
    ustaw_datestamp(Wydawnictwo_Zwarte, wz.pk, dt(3))

    assert provider_publikacji.najstarszy_datestamp(uczelnia_cerif) == dt(3)


@pytest.mark.django_db
def test_najstarszy_datestamp_pustego_setu_to_none(uczelnia_cerif, provider_publikacji):
    assert provider_publikacji.najstarszy_datestamp(uczelnia_cerif) is None


# -- pojedynczy rekord --------------------------------------------------


@pytest.mark.django_db
def test_pojedynczy_zwraca_obiekt_i_none(
    uczelnia_cerif, fabryka_wydawnictw, provider_publikacji
):
    widoczny = fabryka_wydawnictw(Wydawnictwo_Ciagle)
    ukryty = fabryka_wydawnictw(Wydawnictwo_Ciagle, nie_eksportuj_przez_api=True)

    assert (
        provider_publikacji.pojedynczy(
            uczelnia_cerif, Wydawnictwo_Ciagle, widoczny.pk
        ).pk
        == widoczny.pk
    )
    assert (
        provider_publikacji.pojedynczy(uczelnia_cerif, Wydawnictwo_Ciagle, ukryty.pk)
        is None
    )


# -- typ COAR prac dyplomowych ------------------------------------------


@pytest.mark.django_db
def test_coar_pracy_bierze_wartosc_ze_slownika(db):
    Charakter_Formalny.objects.filter(skrot="D").delete()
    Charakter_Formalny.objects.create(
        nazwa="Praca doktorska",
        skrot="D",
        coar_type="http://purl.org/coar/resource_type/wlasny",
    )
    assert coar_pracy(Praca_Doktorska) == ("http://purl.org/coar/resource_type/wlasny")


@pytest.mark.django_db
def test_coar_pracy_ma_fallback_gdy_brak_wiersza_slownika(db):
    from cerif_export.slowniki import coar

    Charakter_Formalny.objects.filter(skrot__in=["D", "H"]).delete()
    assert coar_pracy(Praca_Doktorska) == coar.DOCTORAL_THESIS
    assert coar_pracy(Praca_Habilitacyjna) == coar.THESIS


@pytest.mark.django_db
def test_praca_niesie_gotowy_typ_coar_bez_dotykania_slownika(
    uczelnia_cerif, jednostka_cerif, status_ok, provider_publikacji
):
    """Serializer nie może wołać ``charakter_formalny`` (lazy DB hit)."""
    baker.make(
        Praca_Doktorska,
        jednostka=jednostka_cerif,
        autor=zbuduj_autora("Doktorant"),
        status_korekty=status_ok,
        rok=2020,
    )
    obiekty, _ = provider_publikacji.strona(uczelnia_cerif)
    praca = next(o for o in obiekty if isinstance(o, Praca_Doktorska))
    assert getattr(praca, ADNOTACJA_COAR).startswith("http://purl.org/coar/")


# -- liczba zapytań -----------------------------------------------------


def dotknij_publikacje(obiekty):
    """Udawany serializer: sięgnij po wszystko, po co sięgnie ``cerif/``."""
    for obj in obiekty:
        if isinstance(obj, Zrodlo):
            str(obj.rodzaj)
            continue

        str(obj.tytul_oryginalny)
        str(obj.status_korekty)
        str(obj.jezyk)
        str(obj.konferencja)
        list(obj.slowa_kluczowe.all())

        if isinstance(obj, (Praca_Doktorska, Praca_Habilitacyjna)):
            str(obj.autor)
            str(obj.jednostka)
            getattr(obj, ADNOTACJA_COAR)
            continue

        str(obj.charakter_formalny)
        list(obj.dodatkowe_tytuly.all())
        list(obj.streszczenia.all())
        for autorstwo in obj.autorzy_set.all():
            str(autorstwo.autor)
            str(autorstwo.jednostka)
            str(autorstwo.typ_odpowiedzialnosci)

        if isinstance(obj, Wydawnictwo_Ciagle):
            str(obj.zrodlo)
        else:
            str(obj.wydawnictwo_nadrzedne)


# Budżet zapytań na stronę setu publications, ustalony przy DWÓCH rekordach
# na model. Ten sam budżet musi wystarczyć przy dwudziestu — na tym polega
# test poniżej.
BUDZET_ZAPYTAN_PUBLIKACJE = 20


@pytest.mark.django_db
@pytest.mark.parametrize("ile", [2, 20])
def test_liczba_zapytan_nie_rosnie_z_liczba_rekordow(
    ile,
    uczelnia_cerif,
    jednostka_cerif,
    fabryka_wydawnictw,
    status_ok,
    provider_publikacji,
    django_assert_max_num_queries,
):
    """Jedyny sposób, żeby wyłapać przypadkowy lazy-load w serializerze."""
    zrodlo = baker.make(Zrodlo, nazwa="Czasopismo Q", skrot="Cz. Q")
    for _ in range(ile):
        fabryka_wydawnictw(Wydawnictwo_Ciagle, zrodlo=zrodlo)
        fabryka_wydawnictw(Wydawnictwo_Zwarte)

    with django_assert_max_num_queries(BUDZET_ZAPYTAN_PUBLIKACJE):
        obiekty, _ = provider_publikacji.strona(uczelnia_cerif, rozmiar=1000)
        dotknij_publikacje(obiekty)

    assert len(obiekty) == 2 * ile + 1


@pytest.mark.django_db
@pytest.mark.parametrize("ile", [2, 20])
def test_zbiory_widocznosci_to_stala_liczba_zapytan(
    ile,
    uczelnia_cerif,
    fabryka_wydawnictw,
    provider_publikacji,
    django_assert_max_num_queries,
):
    """Jedno zapytanie na typ encji, niezależnie od rozmiaru partii."""
    zrodlo = baker.make(Zrodlo, nazwa="Czasopismo W", skrot="Cz. W")
    konferencja = baker.make(Konferencja, nazwa="Konferencja W")
    for _ in range(ile):
        fabryka_wydawnictw(Wydawnictwo_Ciagle, zrodlo=zrodlo, konferencja=konferencja)

    obiekty, _ = provider_publikacji.strona(uczelnia_cerif, rozmiar=1000)

    with django_assert_max_num_queries(5):
        zbiory = provider_publikacji.zbiory_widocznosci(uczelnia_cerif, obiekty)

    assert zbiory.zrodla == frozenset({zrodlo.pk})
    assert zbiory.konferencje == frozenset({konferencja.pk})


# -- providery puste ----------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "set_spec",
    [
        const.SET_PRODUCTS,
        const.SET_EQUIPMENTS,
    ],
)
def test_provider_pusty_odpowiada_zerem_rekordow(set_spec, uczelnia_cerif):
    """Sety muszą istnieć („even if unpopulated"), ale nic nie zwracają.

    Zostały już tylko dwa takie sety. ``openaire_cris_projects``
    i ``openaire_cris_funding`` mają — od wprowadzenia modeli ``Projekt``
    i ``Finansowanie`` — własne providery: ich pusta odpowiedź zależy
    dziś od zawartości bazy, a nie od klasy providera, i jest sprawdzana
    w ``test_eksport_projektow.py``.
    """
    provider = provider_dla_setu(set_spec)

    assert provider.strona(uczelnia_cerif) == ([], None)
    assert provider.najstarszy_datestamp(uczelnia_cerif) is None
    assert provider.pojedynczy(uczelnia_cerif, None, 1) is None
    assert provider.zbiory_widocznosci(uczelnia_cerif, []).autorzy == frozenset()


# -- brak tenanta -------------------------------------------------------


@pytest.mark.django_db
def test_provider_bez_uczelni_podnosi_blad(provider_publikacji):
    """Cicha degradacja do pustej odpowiedzi udawałaby poprawny harvest."""
    with pytest.raises(ValueError):
        provider_publikacji.queryset(None, Wydawnictwo_Ciagle)


# -- helper -------------------------------------------------------------


def _przejdz_wszystkie_strony(provider, uczelnia, rozmiar):
    """Przejdź cały set stronami, pilnując, żeby pętla się skończyła."""
    kursor = None
    for _ in range(50):
        obiekty, kursor = provider.strona(uczelnia, kursor=kursor, rozmiar=rozmiar)
        if obiekty:
            yield obiekty
        if kursor is None:
            return
    raise AssertionError("Stronicowanie nie zakończyło się po 50 stronach")
