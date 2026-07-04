"""Faza B / issue #438 — I-4 (migracja 0457).

Testy ustawienia FAKTYCZNEJ struktury drzewa: re-parent płaskich jednostek pod
węzeł-wydział, przepisanie historii sub-jednostek na krawędź realnego rodzica,
własny wpis historii węzła-wydziału (z derywacją ``aktualna``), przeliczenie
nested-set oraz guard ``post_delete`` Wydziału (bezdzietność).

Logika migracji 0457 (``apply_faza_b_i4``) operuje na żywych tabelach i jest
idempotentna, więc testy budują scenariusz przez REALNE modele, wołają funkcję
forward (na realnym rejestrze ``apps``) i asertują wynik.
"""

from datetime import date, timedelta
from importlib import import_module

import pytest
from django.apps import apps as global_apps
from model_bakery import baker

from bpp.models import Jednostka, Jednostka_Rodzic, Uczelnia, Wydzial
from bpp.models.struktura_konwersja import znajdz_lub_utworz_wezel_wydzialu

# Nazwa modułu migracji zaczyna się cyfrą — import przez importlib.
_mig = import_module("bpp.migrations.0457_faza_b_i4")


def _apply():
    _mig.apply_faza_b_i4(global_apps, None)


def _wezel(wydzial):
    wezel, _ = znajdz_lub_utworz_wezel_wydzialu(wydzial)
    return wezel


@pytest.fixture
def uczelnia(db):
    return baker.make(Uczelnia)


# ---------------------------------------------------------------------------
# (a) płaska jednostka z wydziałem → MPTT parent == węzeł-wydział
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_plaska_jednostka_pod_wezlem_wydzialu(uczelnia):
    w = baker.make(Wydzial, uczelnia=uczelnia)
    wezel = _wezel(w)
    j = baker.make(Jednostka, uczelnia=uczelnia, parent=None, wydzial=w)

    assert j.parent_id is None

    _apply()

    j.refresh_from_db()
    wezel.refresh_from_db()
    assert j.parent_id == wezel.pk
    descendants = wezel.get_descendants().values_list("pk", flat=True)
    assert j.pk in set(descendants)


# ---------------------------------------------------------------------------
# (b) sub-jednostka (zakład pod katedrą) → MPTT parent niezmieniony (katedra),
#     wpis historii przepisany na katedrę (nie węzeł-wydział)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_subjednostka_historia_na_krawedzi_realnego_rodzica(uczelnia):
    w = baker.make(Wydzial, uczelnia=uczelnia)
    wezel = _wezel(w)
    katedra = baker.make(Jednostka, uczelnia=uczelnia, parent=None, wydzial=w)
    zaklad = baker.make(Jednostka, uczelnia=uczelnia, parent=katedra, wydzial=w)
    # Historia sub-jednostki po backfillu I-3 wskazuje węzeł-wydział.
    wpis = baker.make(
        Jednostka_Rodzic, jednostka=zaklad, parent=wezel, od=None, do=None
    )

    _apply()

    zaklad.refresh_from_db()
    wpis.refresh_from_db()
    # MPTT parent sub-jednostki NIEZMIENIONY:
    assert zaklad.parent_id == katedra.pk
    # Wpis historii przepisany na krawędź realnego rodzica (katedra):
    assert wpis.parent_id == katedra.pk


# ---------------------------------------------------------------------------
# (c) direct-child historyczne wpisy NIENARUSZONE (różne wydziały w czasie)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_direct_child_historia_nienaruszona(uczelnia):
    w1 = baker.make(Wydzial, uczelnia=uczelnia)
    w2 = baker.make(Wydzial, uczelnia=uczelnia)
    wezel1 = _wezel(w1)
    wezel2 = _wezel(w2)
    # Płaska jednostka, obecnie w w2:
    j = baker.make(Jednostka, uczelnia=uczelnia, parent=None, wydzial=w2)
    # Historia: kiedyś w1 (zamknięty), teraz w2 (otwarty).
    stary = baker.make(
        Jednostka_Rodzic,
        jednostka=j,
        parent=wezel1,
        od=date(2000, 1, 1),
        do=date(2010, 1, 1),
    )
    biezacy = baker.make(
        Jednostka_Rodzic, jednostka=j, parent=wezel2, od=date(2010, 1, 2), do=None
    )

    _apply()

    stary.refresh_from_db()
    biezacy.refresh_from_db()
    # Direct-child: oba wpisy NIETKNIĘTE (prawdziwa historia wydziałów):
    assert stary.parent_id == wezel1.pk
    assert biezacy.parent_id == wezel2.pk
    # Bieżący wpis wskazuje węzeł == żywy MPTT parent:
    j.refresh_from_db()
    assert j.parent_id == biezacy.parent_id


# ---------------------------------------------------------------------------
# (d) węzeł-wydział ma własny wpis od/do; zamknięty → aktualna=False;
#     przyszłe zamknięcie → do=None
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_wezel_wpis_zamkniety_wydzial_aktualna_false(uczelnia):
    w = baker.make(
        Wydzial,
        uczelnia=uczelnia,
        otwarcie=date(1990, 1, 1),
        zamkniecie=date(2010, 1, 1),  # w przeszłości
    )
    wezel = _wezel(w)

    _apply()

    wpis = Jednostka_Rodzic.objects.get(jednostka=wezel, parent__isnull=True)
    assert wpis.od == date(1990, 1, 1)
    assert wpis.do == date(2010, 1, 1)
    wezel.refresh_from_db()
    # Sygnał zderywował aktualna z zamkniętego wpisu:
    assert wezel.aktualna is False


@pytest.mark.django_db
def test_wezel_wpis_przyszle_zamkniecie_do_none(uczelnia):
    przyszlosc = date.today() + timedelta(days=365)
    w = baker.make(
        Wydzial, uczelnia=uczelnia, otwarcie=date(1990, 1, 1), zamkniecie=przyszlosc
    )
    wezel = _wezel(w)

    _apply()

    wpis = Jednostka_Rodzic.objects.get(jednostka=wezel, parent__isnull=True)
    assert wpis.do is None  # clamp przyszłego zamknięcia (CHECK do<NOW)
    wezel.refresh_from_db()
    assert wezel.aktualna is True


@pytest.mark.django_db
def test_wezel_wpis_otwarcie_po_zamknieciu_do_none(uczelnia):
    # Patologia dat: otwarcie > zamkniecie → daterange niepoprawny → do=None.
    w = baker.make(
        Wydzial,
        uczelnia=uczelnia,
        otwarcie=date(2010, 1, 1),
        zamkniecie=date(2000, 1, 1),
    )
    wezel = _wezel(w)

    _apply()

    wpis = Jednostka_Rodzic.objects.get(jednostka=wezel, parent__isnull=True)
    assert wpis.od == date(2010, 1, 1)
    assert wpis.do is None


# ---------------------------------------------------------------------------
# Patologia kroku 4: wiele różnych wydziałów przy niezmiennym MPTT-rodzicu
# → NIE przepisuje (log + skip)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_subjednostka_wiele_wydzialow_nie_przepisuje(uczelnia, capsys):
    w1 = baker.make(Wydzial, uczelnia=uczelnia)
    w2 = baker.make(Wydzial, uczelnia=uczelnia)
    wezel1 = _wezel(w1)
    wezel2 = _wezel(w2)
    katedra = baker.make(Jednostka, uczelnia=uczelnia, parent=None, wydzial=w2)
    zaklad = baker.make(Jednostka, uczelnia=uczelnia, parent=katedra, wydzial=w2)
    # Sub-jednostka z DWOMA różnymi wydziałami w historii:
    w_stary = baker.make(
        Jednostka_Rodzic,
        jednostka=zaklad,
        parent=wezel1,
        od=date(2000, 1, 1),
        do=date(2010, 1, 1),
    )
    w_nowy = baker.make(
        Jednostka_Rodzic, jednostka=zaklad, parent=wezel2, od=date(2010, 1, 2), do=None
    )

    _apply()

    w_stary.refresh_from_db()
    w_nowy.refresh_from_db()
    # NIE przepisane — zostają na węzłach-wydziałach (do ręcznego przeglądu):
    assert w_stary.parent_id == wezel1.pk
    assert w_nowy.parent_id == wezel2.pk
    assert "PATOLOGIA" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# (e) nested-set poprawny (lft<rght, get_descendants działa)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_nested_set_poprawny(uczelnia):
    w = baker.make(Wydzial, uczelnia=uczelnia)
    wezel = _wezel(w)
    katedra = baker.make(Jednostka, uczelnia=uczelnia, parent=None, wydzial=w)
    zaklad = baker.make(Jednostka, uczelnia=uczelnia, parent=katedra, wydzial=w)

    _apply()

    for node in Jednostka.objects.filter(pk__in=[wezel.pk, katedra.pk, zaklad.pk]):
        assert node.lft < node.rght

    wezel.refresh_from_db()
    katedra.refresh_from_db()
    zaklad.refresh_from_db()
    # Drzewo: wezel → katedra → zaklad, w jednym tree_id.
    assert katedra.parent_id == wezel.pk
    assert zaklad.parent_id == katedra.pk
    assert wezel.tree_id == katedra.tree_id == zaklad.tree_id
    poddrzewo = set(
        wezel.get_descendants(include_self=True).values_list("pk", flat=True)
    )
    assert poddrzewo == {wezel.pk, katedra.pk, zaklad.pk}


# ---------------------------------------------------------------------------
# (f) re-run migracji idempotentny
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_migracja_idempotentna(uczelnia):
    w = baker.make(
        Wydzial, uczelnia=uczelnia, otwarcie=date(1990, 1, 1), zamkniecie=None
    )
    wezel = _wezel(w)
    katedra = baker.make(Jednostka, uczelnia=uczelnia, parent=None, wydzial=w)
    zaklad = baker.make(Jednostka, uczelnia=uczelnia, parent=katedra, wydzial=w)
    baker.make(Jednostka_Rodzic, jednostka=zaklad, parent=wezel, od=None, do=None)

    _apply()

    def snapshot():
        katedra.refresh_from_db()
        zaklad.refresh_from_db()
        wezel.refresh_from_db()
        return (
            katedra.parent_id,
            zaklad.parent_id,
            (katedra.lft, katedra.rght, katedra.tree_id, katedra.level),
            (zaklad.lft, zaklad.rght, zaklad.tree_id, zaklad.level),
            (wezel.lft, wezel.rght, wezel.tree_id, wezel.level),
            Jednostka_Rodzic.objects.filter(
                jednostka=wezel, parent__isnull=True
            ).count(),
            Jednostka_Rodzic.objects.get(jednostka=zaklad).parent_id,
        )

    first = snapshot()
    _apply()  # re-run
    second = snapshot()

    assert first == second
    # Guard idempotencji wpisu węzła: dokładnie 1 wpis (parent NULL):
    assert (
        Jednostka_Rodzic.objects.filter(jednostka=wezel, parent__isnull=True).count()
        == 1
    )


# ---------------------------------------------------------------------------
# (g) guard post_delete: węzeł z dziećmi PRZEŻYWA; bezdzietny transient znika
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_post_delete_guard_wezel_z_dziecmi_przezywa(uczelnia):
    """Guard bezdzietności: węzeł-lustro z realnym dzieckiem NIE ginie przy
    kasowaniu Wydziału, więc jego CASCADE (na ``Jednostka.parent`` i
    ``Jednostka_Rodzic.parent``) nie niszczy realnej struktury.

    Uwaga (stan I-4): ``Jednostka.wydzial`` to WCIĄŻ FK→Wydzial z CASCADE
    (retarget na denorm-korzeń dopiero w B-II). Dziecko z ``wydzial=w``
    zginęłoby przez TEN FK niezależnie od guardu — dlatego testujemy guard w
    izolacji dzieckiem z ``wydzial=None`` (świat po B-II), które przeżywa
    tylko dzięki guardowi na krawędzi lustra."""
    w = baker.make(Wydzial, uczelnia=uczelnia)
    wezel = _wezel(w)
    # Dziecko podpięte pod lustro, bez FK wydzial→w (nie ginie przez tamten
    # CASCADE) — przeżycie zależy WYŁĄCZNIE od guardu. NIE dodajemy wpisu
    # Jednostka_Rodzic(parent=wezel): sygnał zderywowałby wtedy wydzial=w z
    # parent.legacy_wydzial_id i dziecko zginęłoby przez FK wydzial→Wydzial.
    dziecko = baker.make(Jednostka, uczelnia=uczelnia, parent=wezel, wydzial=None)

    w.delete()

    # Węzeł-lustro MA dzieci → guard blokuje delete. Gdyby lustro zginęło, jego
    # CASCADE (Jednostka.parent + Jednostka_Rodzic.parent) zniszczyłby realną
    # strukturę. Lustro i dziecko PRZEŻYWAJĄ:
    assert Jednostka.objects.filter(pk=wezel.pk).exists()
    assert Jednostka.objects.filter(pk=dziecko.pk).exists()


@pytest.mark.django_db
def test_post_delete_guard_bezdzietny_wezel_znika(uczelnia):
    w = baker.make(Wydzial, uczelnia=uczelnia)
    wezel = _wezel(w)
    wid = wezel.pk

    # Bez podpinania dzieci (transient lustro).
    assert not Jednostka.objects.filter(parent=wezel).exists()

    w.delete()

    assert not Jednostka.objects.filter(pk=wid).exists()
