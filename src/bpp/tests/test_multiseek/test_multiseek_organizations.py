"""
Testy obiektów zapytań multiseek związanych z jednostkami i wydziałami.

Ten moduł zawiera testy dla QueryObject dotyczących organizacji:
- JednostkaQueryObject - wyszukiwanie po jednostce
- WydzialQueryObject - wyszukiwanie po wydziale
- PierwszyWydzialQueryObject - wyszukiwanie po pierwszym wydziale
- PierwszaJednostkaQueryObject - wyszukiwanie po pierwszej jednostce
- AktualnaJednostkaAutoraQueryObject - wyszukiwanie po aktualnej jednostce autora
- ObcaJednostkaQueryObject - wyszukiwanie po obcej jednostce
- RodzajJednostkiQueryObject - wyszukiwanie po rodzaju jednostki
- KierunekStudiowQueryObject - wyszukiwanie po kierunku studiów
"""

import pytest
from multiseek import logic

from bpp.models.cache import Rekord
from bpp.multiseek_registry import (
    EQUAL_PLUS_SUB_FEMALE,
    EQUAL_PLUS_SUB_UNION_FEMALE,
    UNION,
    AktualnaJednostkaAutoraQueryObject,
    JednostkaQueryObject,
    KierunekStudiowQueryObject,
    ObcaJednostkaQueryObject,
    PierwszaJednostkaQueryObject,
    PierwszyWydzialQueryObject,
    RodzajJednostkiQueryObject,
    WydzialQueryObject,
)

pytestmark = pytest.mark.serial


def test_JednostkaQueryObject(jednostka):
    n = JednostkaQueryObject()

    ret = n.real_query(jednostka, logic.EQUAL)
    assert ret is not None

    ret = n.real_query(jednostka, logic.DIFFERENT)
    assert ret is not None

    ret = n.real_query(jednostka, UNION)
    assert ret is not None

    ret = n.real_query(None, logic.EQUAL)
    assert ret is not None

    ret = n.real_query(None, logic.DIFFERENT)
    assert ret is not None

    ret = n.real_query(None, UNION)
    assert ret is not None

    ret = n.real_query(jednostka, EQUAL_PLUS_SUB_FEMALE)
    assert ret is not None

    ret = n.real_query(jednostka, EQUAL_PLUS_SUB_UNION_FEMALE)
    assert ret is not None


def test_WydzialQueryObject(wydzial):
    # Faza B (#438): „wydział" w multiseeku to jednostka-korzeń (self-FK),
    # więc real_query przyjmuje root-Jednostkę (węzeł-lustro), nie Wydzial.

    root = wydzial
    n = WydzialQueryObject()

    ret = n.real_query(root, logic.EQUAL)
    Rekord.objects.filter(ret)

    ret = n.real_query(root, logic.DIFFERENT)
    Rekord.objects.filter(ret)

    ret = n.real_query(root, UNION)
    Rekord.objects.filter(ret)

    ret = n.real_query(None, logic.EQUAL)
    Rekord.objects.filter(ret)

    ret = n.real_query(None, logic.DIFFERENT)
    Rekord.objects.filter(ret)

    ret = n.real_query(None, UNION)
    Rekord.objects.filter(ret)


def test_PierwszyWydzialQueryObject(wydzial):

    root = wydzial
    n = PierwszyWydzialQueryObject()

    ret = n.real_query(root, logic.EQUAL)
    Rekord.objects.filter(ret)

    ret = n.real_query(root, logic.DIFFERENT)
    Rekord.objects.filter(ret)

    ret = n.real_query(root, UNION)
    Rekord.objects.filter(ret)

    ret = n.real_query(None, logic.EQUAL)
    Rekord.objects.filter(ret)

    ret = n.real_query(None, logic.DIFFERENT)
    Rekord.objects.filter(ret)

    ret = n.real_query(None, UNION)
    Rekord.objects.filter(ret)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "logic_arg",
    [logic.EQUAL, UNION, EQUAL_PLUS_SUB_FEMALE, EQUAL_PLUS_SUB_UNION_FEMALE],
)
def test_PierwszaJednostka_realQuery(
    wydawnictwo_zwarte, autor_jan_kowalski, jednostka, logic_arg
):
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)

    r = Rekord.objects.filter(
        PierwszaJednostkaQueryObject().real_query(jednostka, logic_arg)
    )

    assert len(r) == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "param",
    [
        logic.EQUAL,
        logic.DIFFERENT,
        EQUAL_PLUS_SUB_FEMALE,
    ],
)
def test_AktualnaJednostkaAutoraQueryObject(jednostka, param):
    res = AktualnaJednostkaAutoraQueryObject().real_query(jednostka, param)
    assert res is not None


@pytest.mark.django_db
def test_ObcaJednostkaQueryObject(
    wydawnictwo_zwarte,
    autor_jan_kowalski,
    obca_jednostka,
):
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, obca_jednostka, afiliuje=False)

    res = ObcaJednostkaQueryObject().real_query(True, logic.EQUAL)
    assert Rekord.objects.filter(res).count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "param",
    [
        logic.EQUAL,
        logic.DIFFERENT,
    ],
)
def test_RodzajJednostkiQueryObject(param):
    # Faza B (#438), III-1: wartość to nazwa słownikowa ``RodzajJednostki``
    # (FK), nie kod starego CharField.
    ret = RodzajJednostkiQueryObject().real_query("Standard", param)
    assert Rekord.objects.filter(*(ret,)).count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "param",
    [
        logic.EQUAL,
        logic.DIFFERENT,
    ],
)
def test_KierunekStudiowQueryObject(param, kierunek_studiow):
    ret = KierunekStudiowQueryObject().real_query(kierunek_studiow, param)
    assert Rekord.objects.filter(*(ret,)).count() == 0


# --- #438: nierozwiązywalna wartość (value_from_web → None) → PUSTY wynik ----


@pytest.mark.django_db
def test_WydzialQueryObject_none_value_yields_empty_match(
    wydawnictwo_zwarte, autor_jan_kowalski, jednostka
):
    """#438/F4: nierozwiązywalny pk wydziału (``value_from_web`` → None) MUSI dać
    PUSTY wynik ("głośny brak dopasowania"), a nie szeroki match. Bez guardu
    ``Q(autorzy__jednostka__wydzial=None)`` łapie KAŻDEGO autora w
    jednostce-korzeniu (denorm ``wydzial`` = NULL dla rootów)."""
    jednostka.parent = None
    jednostka.wydzial = None
    jednostka.save()
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)
    assert Rekord.objects.count() == 1  # sanity: rekord w cache

    ret = WydzialQueryObject().real_query(None, logic.EQUAL)
    assert Rekord.objects.filter(ret).count() == 0


@pytest.mark.django_db
def test_JednostkaQueryObject_none_value_different_yields_empty_match(
    wydawnictwo_zwarte, autor_jan_kowalski, jednostka
):
    """#438: value=None + operator DIFFERENT NIE może dać
    ``~Q(autorzy__jednostka=None)`` = "wszystkie rekordy z autorem w jednostce".
    Nierozwiązywalna wartość → pusto, niezależnie od operatora."""
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)
    assert Rekord.objects.count() == 1

    ret = JednostkaQueryObject().real_query(None, logic.DIFFERENT)
    assert Rekord.objects.filter(ret).count() == 0


@pytest.mark.django_db
def test_KierunekStudiowQueryObject_none_value_yields_empty_match(
    wydawnictwo_zwarte, autor_jan_kowalski, jednostka
):
    """#438: nierozwiązywalny pk kierunku (``value_from_web`` → None, np.
    skasowany kierunek w zapisanym searchu) → PUSTY wynik. Bez guardu
    ``Q(autorzy__kierunek_studiow=None)`` łapie WSZYSTKIE rekordy z autorem
    bez kierunku (przytłaczająca większość), a DIFFERENT odwraca w "prawie
    wszystko"."""
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)
    assert Rekord.objects.count() == 1

    ret = KierunekStudiowQueryObject().real_query(None, logic.EQUAL)
    assert Rekord.objects.filter(ret).count() == 0


# --- #438: pole „Jednostka nadrzędna" (odpowiednik „Wydział" dla uczelni bez
#     wydziałów, ale ze strukturą drzewa jednostek) ---


def _req(uczelnia):
    """Lekki request z ustawionym cache ``_uczelnia`` -- ``get_for_request``
    zwraca go bez zapytania do bazy (patrz ``Uczelnia.get_for_request``)."""
    import types

    return types.SimpleNamespace(_uczelnia=uczelnia)


@pytest.mark.django_db
def test_JednostkaNadrzedna_enabled_uczelnia_bez_wydzialow_ze_struktura(uczelnia):
    from bpp.multiseek_registry import JednostkaNadrzednaQueryObject
    from bpp.tests.util import any_jednostka

    uczelnia.uzywaj_wydzialow = False
    uczelnia.save()
    korzen = any_jednostka(
        nazwa="Instytut Główny IG", uczelnia=uczelnia, wydzial=None, parent=None
    )
    any_jednostka(nazwa="Dział IG", uczelnia=uczelnia, wydzial=None, parent=korzen)

    assert JednostkaNadrzednaQueryObject().option_enabled(_req(uczelnia)) is True


@pytest.mark.django_db
def test_JednostkaNadrzedna_ukryte_gdy_uczelnia_uzywa_wydzialow(uczelnia):
    # Uczelnia z wydziałami: strukturę obsługuje pole „Wydział", nowe ukryte.
    from bpp.multiseek_registry import JednostkaNadrzednaQueryObject
    from bpp.tests.util import any_jednostka

    uczelnia.uzywaj_wydzialow = True
    uczelnia.save()
    korzen = any_jednostka(
        nazwa="Wydział W", uczelnia=uczelnia, wydzial=None, parent=None
    )
    any_jednostka(nazwa="Katedra W", uczelnia=uczelnia, wydzial=None, parent=korzen)

    assert JednostkaNadrzednaQueryObject().option_enabled(_req(uczelnia)) is False


@pytest.mark.django_db
def test_JednostkaNadrzedna_ukryte_gdy_plaska_struktura(uczelnia):
    from bpp.multiseek_registry import JednostkaNadrzednaQueryObject
    from bpp.tests.util import any_jednostka

    uczelnia.uzywaj_wydzialow = False
    uczelnia.save()
    any_jednostka(nazwa="Korzeń płaski", uczelnia=uczelnia, wydzial=None, parent=None)

    assert JednostkaNadrzednaQueryObject().option_enabled(_req(uczelnia)) is False


def test_JednostkaNadrzedna_ukryte_gdy_brak_uczelni():
    from bpp.multiseek_registry import JednostkaNadrzednaQueryObject

    assert JednostkaNadrzednaQueryObject().option_enabled(_req(None)) is False


@pytest.mark.django_db
def test_Wydzial_option_enabled_bez_zmian_regresja(uczelnia):
    # Regresja: „Wydział" nadal sterowane WYŁĄCZNIE flagą ``uzywaj_wydzialow``.
    uczelnia.uzywaj_wydzialow = False
    uczelnia.save()
    assert WydzialQueryObject().option_enabled(_req(uczelnia)) is False

    uczelnia.uzywaj_wydzialow = True
    uczelnia.save()
    assert WydzialQueryObject().option_enabled(_req(uczelnia)) is True
