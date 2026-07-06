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


def _jednostka_w_wydziale(uczelnia, wydzial, parent=None):
    """Jednostka należąca do ``wydzial`` w modelu PO retargecie (II-1 / 0459).

    Faza B (#438): ``Jednostka.wydzial`` to self-FK do korzenia z DB-constraint
    → nie da się ustawić ``wydzial_id`` na pk Wydzialu (stan sprzed 0457 jest
    nieodtwarzalny). Jednostka wisi więc pod węzłem-lustrem wydziału (root),
    a denorm wylicza ``wydzial`` = ten korzeń. ``apply_faza_b_i4`` uruchamiamy
    na tak ustrukturyzowanych danych (re-parent płaskich = no-op; testujemy
    przepisanie historii / nested-set / idempotencję)."""
    if parent is None:
        parent = _wezel(wydzial)
    return baker.make(Jednostka, uczelnia=uczelnia, parent=parent)


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
    j = _jednostka_w_wydziale(uczelnia, w)

    # Faza B (#438), II-1: jednostka jest już pod węzłem-lustrem (stan po
    # retargecie). ``_apply`` (re-parent płaskich) jest tu no-opem — sprawdzamy
    # że NIE psuje istniejącej struktury (idempotencja).
    assert j.parent_id == wezel.pk

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
    katedra = _jednostka_w_wydziale(uczelnia, w)
    zaklad = _jednostka_w_wydziale(uczelnia, w, parent=katedra)
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
    j = _jednostka_w_wydziale(uczelnia, w2)
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
    katedra = _jednostka_w_wydziale(uczelnia, w2)
    zaklad = _jednostka_w_wydziale(uczelnia, w2, parent=katedra)
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
    katedra = _jednostka_w_wydziale(uczelnia, w)
    zaklad = _jednostka_w_wydziale(uczelnia, w, parent=katedra)

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
    katedra = _jednostka_w_wydziale(uczelnia, w)
    zaklad = _jednostka_w_wydziale(uczelnia, w, parent=katedra)
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


@pytest.mark.django_db
def test_krok3_pomija_promowana_jednostke_nie_fabrykuje_historii(uczelnia):
    """Finding 1 (#438): krok 3 (``_wpis_historii_wezlow``) NIE tworzy wpisu
    historii dla PROMOWANEJ realnej jednostki (``jest_lustrem=False``), nawet
    gdy ma ona ``legacy_wydzial_id`` wskazujący istniejący, ZAMKNIĘTY Wydzial.

    To stan re-runu: po kroku 6 promowana jednostka ma ``legacy_wydzial_id``.
    Bez markera ``jest_lustrem`` krok 3 brał ją za lustro i tworzył
    ``Jednostka_Rodzic(parent=None, do=zamkniecie)`` → zamknięta historia na
    ŻYWEJ jednostce → ``aktualna=False`` (cicha korupcja). Reprodukcja
    recenzenta, ale wprost na kroku (harness self-FK ``wydzial`` uniemożliwia
    ustawienie ``legacy=Wydzial.pk`` przez ``_czlonek``)."""
    w = baker.make(
        Wydzial,
        uczelnia=uczelnia,
        otwarcie=date(2000, 1, 1),
        zamkniecie=date(2010, 1, 1),  # ZAMKNIĘTY — dawałby do=2010-01-01
    )
    # Promowana realna jednostka: legacy=w.id, ale jest_lustrem=False.
    promowana = baker.make(Jednostka, uczelnia=uczelnia, parent=None)
    Jednostka.objects.filter(pk=promowana.pk).update(
        legacy_wydzial_id=w.id, jest_lustrem=False
    )

    _mig._wpis_historii_wezlow(global_apps)

    # ŻADNEGO wpisu historii dla promowanej (krok 3 pomija nie-lustra):
    assert not Jednostka_Rodzic.objects.filter(jednostka=promowana).exists()


@pytest.mark.django_db
def test_promocja_ukrytego_wydzialu_ukrywa_jednostke(uczelnia):
    """#438: promocja 1-jednostkowego UKRYTEGO wydziału → promowana jednostka
    też UKRYTA (przejmuje rolę wydziału). Bez tego ukryty „wydmuszka"-wydział
    znikał, a jego jedyna, WIDOCZNA jednostka zostawała widoczna.

    ``Wydzial.id == mirror.legacy_wydzial_id`` (harness): dzięki temu FK ``wydzial``
    członka (self-FK do Jednostki o pk == legacy) pozostaje ważny, a lookup
    widoczności wydziału po ``legacy`` znajduje właściwy Wydzial."""
    mirror = _lustro_wydzialu(uczelnia)  # legacy = mirror.pk
    baker.make(Wydzial, id=mirror.legacy_wydzial_id, uczelnia=uczelnia, widoczny=False)
    jedyna = _czlonek(uczelnia, mirror)
    Jednostka.objects.filter(pk=jedyna.pk).update(widoczna=True)  # sama widoczna

    _promuj()

    jedyna.refresh_from_db()
    assert jedyna.parent_id is None  # promowana do roota
    assert jedyna.widoczna is False  # przejęła niewidoczność ukrytego wydziału


@pytest.mark.django_db
def test_promocja_widocznego_wydzialu_zostawia_widocznosc_jednostki(uczelnia):
    """#438 (kontrast): WIDOCZNY wydział NIE forsuje widoczności — promowana
    zostaje ze swoją własną (tu: widoczna)."""
    mirror = _lustro_wydzialu(uczelnia)
    baker.make(Wydzial, id=mirror.legacy_wydzial_id, uczelnia=uczelnia, widoczny=True)
    jedyna = _czlonek(uczelnia, mirror)
    Jednostka.objects.filter(pk=jedyna.pk).update(widoczna=True)

    _promuj()

    jedyna.refresh_from_db()
    assert jedyna.parent_id is None
    assert jedyna.widoczna is True  # widoczny wydział → własna widoczność zostaje


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


@pytest.mark.django_db
def test_post_delete_nie_kasuje_lustra_z_konsumentem_0460(uczelnia):
    """#438: bezdzietny węzeł-lustro, na który wskazuje FK konsumenta z 0460
    (tu: ``Patent.wydzial``, SET_NULL), NIE może zostać skasowany przez
    ``post_delete`` Wydziału — inaczej kasowanie CICHO zeruje/kaskaduje cudze
    dane (Patent traci przypięty wydział; ``Opi_2012`` skaskadowałby wiersz;
    ``Kierunek`` rzuciłby ProtectedError → rollback kasowania Wydziału). Guard
    bezdzietności nie wystarcza: sprawdzał tylko dzieci-Jednostki, nie
    przepięte FK. Węzeł jest „transientny" (kasowalny) TYLKO gdy nic go nie
    referencuje."""
    from bpp.models.patent import Patent

    w = baker.make(Wydzial, uczelnia=uczelnia)
    wezel = _wezel(w)
    patent = baker.make(Patent, wydzial=wezel)

    w.delete()

    assert Jednostka.objects.filter(pk=wezel.pk).exists()
    patent.refresh_from_db()
    assert patent.wydzial_id == wezel.pk


# ---------------------------------------------------------------------------
# (h) #438 — 1-jednostkowy wydział: promocja do roota zamiast pustej wydmuszki
# ---------------------------------------------------------------------------
#
# Uwaga o realizmie testów: ``apply_faza_b_i4`` uruchamiamy na ŻYWYM schemacie
# (``global_apps``), gdzie ``Jednostka.wydzial`` to zdenormalizowany self-FK do
# KORZENIA (retarget 0459 już zastosowany). Tożsamość „jednostka należy do
# wydziału W" z etapu PRZED-retargetowego (``wydzial_id == Wydzial.pk``) jest na
# żywym schemacie nieodtwarzalna wprost (self-FK + denorm). Odtwarzamy ją
# WIERNIE dla logiki kroku 0: węzeł-lustro ma ``legacy_wydzial_id`` ustawione na
# WŁASNY pk (dowolny poprawny klucz, tu = pk lustra, by FK ``wydzial`` członka
# miał na co wskazywać), a członek ma ``wydzial_id == mirror.legacy_wydzial_id``.
# Krok 0 filtruje DOKŁADNIE ``wydzial_id == mirror.legacy_wydzial_id`` — więc
# ta konstrukcja ćwiczy realną ścieżkę identyfikacji i całą mechanikę promocji
# (odpięcie, usunięcie lustra, brak wiszących FK, nested-set).


def _rodzaj(nazwa):
    from bpp.models.rodzaj_jednostki import RodzajJednostki

    return RodzajJednostki.objects.get_or_create(nazwa=nazwa)[0]


def _lustro_wydzialu(uczelnia, legacy=None):
    """Root ``Jednostka`` w roli SYNTETYCZNEGO węzła-lustra
    (``legacy_wydzial_id`` ustawione, ``rodzaj="Wydział"`` — jak realne lustra
    z 0455/``struktura_konwersja``).

    Domyślnie ``legacy_wydzial_id = własny pk`` — dowolny poprawny klucz, przy
    którym FK ``Jednostka.wydzial`` (self-FK) członka może go wskazywać bez
    naruszenia więzów (pk lustra ISTNIEJE w ``bpp_jednostka``).

    ``jest_lustrem=True`` jest ISTOTNE: krok 0 promocji, kroki 3/4 historii i
    sygnał kasujący identyfikują lustro po TYM markerze (stabilnym, nie po
    edytowalnej nazwie rodzaju), odróżniając je od promowanej realnej jednostki
    (``jest_lustrem=False``). ``rodzaj="Wydział"`` zostaje dla realizmu
    (prawdziwe lustra mają ten rodzaj dla wyświetlania w stylu wydziału)."""
    mirror = baker.make(
        Jednostka, uczelnia=uczelnia, parent=None, rodzaj=_rodzaj("Wydział")
    )
    legacy = legacy if legacy is not None else mirror.pk
    Jednostka.objects.filter(pk=mirror.pk).update(
        legacy_wydzial_id=legacy, jest_lustrem=True
    )
    mirror.refresh_from_db()
    return mirror


def _czlonek(uczelnia, mirror, parent=None):
    """REALNA jednostka będąca członkiem wydziału ``mirror`` w sensie
    PRZED-retargetowym: ``wydzial_id == mirror.legacy_wydzial_id``,
    ``rodzaj="Standard"`` (NIE lustro). ``parent``: None (płaska) albo
    org-rodzic (jednostka spoza wydziału)."""
    j = baker.make(
        Jednostka, uczelnia=uczelnia, parent=parent, rodzaj=_rodzaj("Standard")
    )
    Jednostka.objects.filter(pk=j.pk).update(wydzial_id=mirror.legacy_wydzial_id)
    j.refresh_from_db()
    return j


def _promuj():
    """Krok 0 (promocja) + krok 6 (ustawienie ``legacy_wydzial_id`` promowanym)
    — jak w ``apply_faza_b_i4``, ale bez kroków 2–5. Zwraca mapę promowanych."""
    promoted = _mig._promuj_jednoelementowe_wydzialy(global_apps)
    _mig._ustaw_legacy_promowanym(global_apps, promoted)
    return promoted


@pytest.mark.django_db
def test_jednoelementowy_wydzial_plaski_promuje_do_roota(uczelnia):
    """Wydział z 1 PŁASKĄ jednostką → jednostka promowana do roota
    (``parent=None``), węzeł-lustro USUNIĘTY (brak wydmuszki), a promowana
    jednostka PRZEJMUJE ``legacy_wydzial_id`` zastąpionego wydziału (#438,
    krok 6 — by mapowania 0460/0463 ją obejmowały)."""
    mirror = _lustro_wydzialu(uczelnia)
    legacy = mirror.legacy_wydzial_id
    j = _czlonek(uczelnia, mirror)  # płaska (parent=None)

    promoted = _promuj()

    assert promoted == {j.pk: legacy}
    j.refresh_from_db()
    assert j.parent_id is None  # root
    assert j.legacy_wydzial_id == legacy  # przejęła identyfikator wydziału
    assert not Jednostka.objects.filter(pk=mirror.pk).exists()  # brak wydmuszki
    assert Jednostka.objects.filter(pk=j.pk).exists()


@pytest.mark.django_db
def test_jednoelementowy_wydzial_org_rodzic_odpina_i_promuje(uczelnia):
    """Wydział z 1 jednostką mającą ORG-RODZICA (odpowiednik RN-2 →
    „Prorektor ds nauki") → jednostka ODPIĘTA od org-rodzica i promowana do
    roota; org-rodzic ŻYJE dalej; węzeł-lustro usunięty."""
    org_rodzic = baker.make(Jednostka, uczelnia=uczelnia, parent=None)
    mirror = _lustro_wydzialu(uczelnia)
    j = _czlonek(uczelnia, mirror, parent=org_rodzic)
    assert j.parent_id == org_rodzic.pk

    _promuj()

    j.refresh_from_db()
    assert j.parent_id is None  # odpięta od org-rodzica, root
    assert Jednostka.objects.filter(pk=org_rodzic.pk).exists()  # org-rodzic żyje
    assert not Jednostka.objects.filter(pk=mirror.pk).exists()


@pytest.mark.django_db
def test_lustro_z_nieoczekiwanym_dzieckiem_nie_kasowane(uczelnia):
    """Guard (#438): nieoczekiwane dziecko wpięte BEZPOŚREDNIO pod lustro
    (ręczny re-parent w oknie A→B) z ``wydzial_id=NULL`` (nie liczone jako
    członek → count członków == 1) — krok 0 MUSI pominąć ten wydział, inaczej
    ``mirror.delete()`` CASCADE-uje obce dziecko + jego poddrzewo."""
    org_rodzic = baker.make(Jednostka, uczelnia=uczelnia, parent=None)
    mirror = _lustro_wydzialu(uczelnia)
    jedyna = _czlonek(uczelnia, mirror, parent=org_rodzic)  # 1 członek

    obce = baker.make(Jednostka, uczelnia=uczelnia, parent=mirror)
    # wydzial_id NULL → obce NIE jest członkiem (count == 1); bez guardu krok 0
    # promowałby ``jedyna`` i kasował lustro → CASCADE po parent zabrałby obce.
    Jednostka.objects.filter(pk=obce.pk).update(wydzial_id=None)

    _promuj()

    assert Jednostka.objects.filter(pk=mirror.pk).exists()  # lustro NIE skasowane
    assert Jednostka.objects.filter(pk=obce.pk).exists()  # obce dziecko ŻYJE
    jedyna.refresh_from_db()
    assert jedyna.parent_id == org_rodzic.pk  # NIE promowana (wydział pominięty)


@pytest.mark.django_db
def test_promocja_bez_wiszacych_jednostka_rodzic(uczelnia):
    """Po promocji ŻADEN wpis ``Jednostka_Rodzic`` nie wskazuje usuniętego
    lustra (naiwny backfill 0456 wskazał je w lustro → CASCADE sprząta)."""
    mirror = _lustro_wydzialu(uczelnia)
    j = _czlonek(uczelnia, mirror)
    wpis = baker.make(Jednostka_Rodzic, jednostka=j, parent=mirror, od=None, do=None)

    _promuj()

    assert not Jednostka_Rodzic.objects.filter(pk=wpis.pk).exists()  # skasowany
    assert not Jednostka_Rodzic.objects.filter(parent_id=mirror.pk).exists()
    assert not Jednostka_Rodzic.objects.filter(jednostka_id=mirror.pk).exists()


@pytest.mark.django_db
def test_dwuelementowy_wydzial_zachowuje_lustro(uczelnia):
    """REGRESJA: wydział z ≥2 jednostkami → lustro POZOSTAJE, jednostki bez
    zmian (promocja dotyczy DOKŁADNIE jednej jednostki)."""
    mirror = _lustro_wydzialu(uczelnia)
    m1 = _czlonek(uczelnia, mirror)
    m2 = _czlonek(uczelnia, mirror)

    _promuj()

    assert Jednostka.objects.filter(pk=mirror.pk).exists()  # lustro żyje
    m1.refresh_from_db()
    m2.refresh_from_db()
    assert m1.parent_id is None and m2.parent_id is None  # niezmienione


@pytest.mark.django_db
def test_zeroelementowy_wydzial_zachowuje_lustro(uczelnia):
    """Wydział z 0 jednostek → lustro POZOSTAJE (dotychczasowe zachowanie)."""
    mirror = _lustro_wydzialu(uczelnia)

    _promuj()

    assert Jednostka.objects.filter(pk=mirror.pk).exists()


@pytest.mark.django_db
def test_pelny_apply_promuje_jednostke_root_nested_set(uczelnia):
    """Pełny ``apply_faza_b_i4``: 1-jednostkowy wydział → jednostka jest ROOTEM
    z poprawnym nested-set (samodzielne drzewo: lft=1/rght=2/level=0), lustra
    brak; kroki 2–5 spójne z brakiem lustra."""
    mirror = _lustro_wydzialu(uczelnia)
    legacy = mirror.legacy_wydzial_id
    j = _czlonek(uczelnia, mirror)

    _apply()

    assert not Jednostka.objects.filter(pk=mirror.pk).exists()
    j.refresh_from_db()
    assert j.parent_id is None
    # Krok 6 (po nested-set): promowana jednostka przejmuje legacy wydziału.
    assert j.legacy_wydzial_id == legacy
    assert j.level == 0
    assert j.lft == 1
    assert j.rght == 2  # samodzielne drzewo (bez dzieci)
    # Jedyny root → samodzielne tree_id; brak wpisu historii po usuniętym lustrze.
    assert not Jednostka_Rodzic.objects.filter(parent_id=mirror.pk).exists()


@pytest.mark.django_db
def test_promocja_idempotentna(uczelnia):
    """Ponowny krok 0 nie zmienia już-promowanej struktury (lustro nie
    istnieje, ``wydzial_id`` członka nie zmieniło się przez re-parent)."""
    mirror = _lustro_wydzialu(uczelnia)
    j = _czlonek(uczelnia, mirror)

    _promuj()
    j.refresh_from_db()
    first = (j.parent_id, Jednostka.objects.filter(pk=mirror.pk).exists())

    _promuj()  # re-run
    j.refresh_from_db()
    second = (j.parent_id, Jednostka.objects.filter(pk=mirror.pk).exists())

    assert first == second == (None, False)


@pytest.mark.django_db
def test_post_delete_nie_kasuje_promowanej_jednostki(uczelnia):
    """#438: promowana REALNA jednostka (I-4/0457 krok 6) niesie
    ``legacy_wydzial_id`` starego wydziału, ale ``rodzaj != "Wydział"`` — sygnał
    ``post_delete`` Wydziału (``usun_wezel_lustro_wydzialu``) kasuje TYLKO
    syntetyczne lustra (``jest_lustrem=True``), więc promowana jednostka z
    dorobkiem PRZEŻYWA kasowanie starego Wydziału. Bez markera lustra byłby to
    wektor utraty danych.

    Stan końcowy konstruujemy wprost (lustro + promowana o tym samym
    ``legacy_wydzial_id``) — mechanikę promocja→legacy testuje osobno
    ``test_jednoelementowy_wydzial_plaski_promuje_do_roota``."""
    w = baker.make(Wydzial, uczelnia=uczelnia)

    # Syntetyczne lustro (jest_lustrem=True) o legacy == w.id — MA zginąć.
    lustro = baker.make(
        Jednostka, uczelnia=uczelnia, parent=None, rodzaj=_rodzaj("Wydział")
    )
    Jednostka.objects.filter(pk=lustro.pk).update(
        legacy_wydzial_id=w.id, jest_lustrem=True
    )

    # Promowana realna jednostka (jest_lustrem=False) o TYM SAMYM legacy — ZOSTAJE.
    promowana = baker.make(
        Jednostka, uczelnia=uczelnia, parent=None, rodzaj=_rodzaj("Standard")
    )
    Jednostka.objects.filter(pk=promowana.pk).update(legacy_wydzial_id=w.id)

    w.delete()

    assert not Jednostka.objects.filter(pk=lustro.pk).exists()  # lustro sprzątnięte
    assert Jednostka.objects.filter(pk=promowana.pk).exists()  # promowana żyje
