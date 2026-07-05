from datetime import date, datetime, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from model_bakery import baker

from bpp.models.struktura import Jednostka, Jednostka_Rodzic, Uczelnia, Wydzial


@pytest.mark.django_db
def test_denorm_wydzial_kaskada_glebokie_drzewo():
    """Faza B (#438), II-1: denorm ``wydzial`` == KORZEŃ drzewa MPTT na KAŻDYM
    poziomie (wydział→instytut→katedra→zakład). To inwariant, na którym stoją
    wszystkie raporty poddrzewa; wcześniej asertowany tylko dla direct-childa."""
    from denorm import denorms

    u = baker.make(Uczelnia)
    root = baker.make(Jednostka, uczelnia=u, parent=None)
    instytut = baker.make(Jednostka, uczelnia=u, parent=root)
    katedra = baker.make(Jednostka, uczelnia=u, parent=instytut)
    zaklad = baker.make(Jednostka, uczelnia=u, parent=katedra)

    denorms.flush()
    for j in (root, instytut, katedra, zaklad):
        j.refresh_from_db()

    assert root.wydzial_id is None  # korzeń → NULL
    assert instytut.wydzial_id == root.pk  # głębokość 1
    assert katedra.wydzial_id == root.pk  # głębokość 2
    assert zaklad.wydzial_id == root.pk  # głębokość 3


@pytest.mark.django_db
def test_denorm_wydzial_reparent_przelicza_cale_poddrzewo():
    """Re-parent poddrzewa pod inny korzeń → ``wydzial`` CAŁEGO poddrzewa
    (nie tylko przenoszonego węzła) przelicza się na nowy korzeń po
    ``denorms.flush()`` — kaskada tranzytywna denorm."""
    from denorm import denorms

    u = baker.make(Uczelnia)
    root1 = baker.make(Jednostka, uczelnia=u, parent=None)
    root2 = baker.make(Jednostka, uczelnia=u, parent=None)
    katedra = baker.make(Jednostka, uczelnia=u, parent=root1)
    zaklad = baker.make(Jednostka, uczelnia=u, parent=katedra)

    denorms.flush()
    katedra.refresh_from_db()
    zaklad.refresh_from_db()
    assert katedra.wydzial_id == root1.pk
    assert zaklad.wydzial_id == root1.pk

    # Przenieś katedrę (wraz z zakładem) spod root1 pod root2.
    katedra.parent = root2
    katedra.save()
    denorms.flush()

    katedra.refresh_from_db()
    zaklad.refresh_from_db()
    assert katedra.wydzial_id == root2.pk
    # Kluczowe: zakład (głębiej niż przenoszony węzeł) też przelicza korzeń.
    assert zaklad.wydzial_id == root2.pk


def _wezel(wydzial):
    """LAZY węzeł-lustro Jednostka dla wydziału (#438) — tworzony przy linku.

    Metryczka historyczna wskazuje teraz węzeł-rodzic (Jednostka), a wydział
    mapuje na węzeł o ``legacy_wydzial_id == wydzial.id`` (get-or-create).
    """
    from bpp.models.struktura_konwersja import znajdz_lub_utworz_wezel_wydzialu

    return znajdz_lub_utworz_wezel_wydzialu(wydzial)[0]


@pytest.mark.django_db
def test_jednostka_wydzial_aktualna():
    """Sprawdź, czy dodanie obiektów Jednostka_Rodzic zmodyfikuje atrybut
    ``aktualna`` na obiekcie Jednostka.

    Faza B (#438), II-1: sygnał NIE utrzymuje już ``wydzial`` — po retargecie
    ``Jednostka.wydzial`` jest zdenormalizowanym self-FK do korzenia drzewa
    MPTT (``parent``), a NIE derywatem z historii ``Jednostka_Rodzic``. Tu
    testujemy więc tylko ``aktualna`` (``j`` jest rootem → ``wydzial`` NULL)."""

    u = baker.make(Uczelnia)
    w = baker.make(Wydzial, uczelnia=u)
    j = baker.make(Jednostka, uczelnia=u)

    assert j.wydzial is None

    jw = Jednostka_Rodzic.objects.create(jednostka=j, parent=_wezel(w))

    j.refresh_from_db()
    assert j.aktualna

    jw.do = datetime.now().date() - timedelta(days=30)
    jw.save()

    j.refresh_from_db()
    assert j.aktualna is False

    jw.delete()
    j.refresh_from_db()
    assert j.wydzial is None
    assert j.aktualna is False


@pytest.mark.django_db(transaction=True)
def test_jednostka_before_insert():
    """Faza B (#438): trigger walidacyjny bpp_jednostka_sprawdz_uczelnia_id
    został zdjęty (federacja, Zasada #4 — bez zamiennika). Przypisanie
    jednostki do wydziału z innej uczelni NIE rzuca już wyjątku na poziomie
    bazy — zapis się udaje."""

    u1 = baker.make(Uczelnia)
    u2 = baker.make(Uczelnia)

    w1 = baker.make(Wydzial, uczelnia=u1)
    w2 = baker.make(Wydzial, uczelnia=u2)

    # Cross-uczelnia — po zdjęciu triggera zapisuje się bez błędu. Faza B
    # (#438): przynależność do wydziału wyrażamy przez MPTT ``parent`` (węzeł-
    # lustro), a ``wydzial`` (denorm) wylicza się jako korzeń.
    j = baker.make(Jednostka, uczelnia=u2, parent=_wezel(w1))
    j.refresh_from_db()
    assert j.wydzial == _wezel(w1)

    j2 = baker.make(Jednostka, uczelnia=u2, parent=_wezel(w2))

    for elem in [j, j2, w2, w1, u2, u1]:
        elem.delete()


@pytest.mark.django_db(transaction=True)
def test_jednostka_wydzial_before_insert():
    """Faza B (#438): trigger bpp_jednostka_wydzial_sprawdz_uczelnia_id
    zdjęty (federacja — bez zamiennika). Przypisanie jednostki do wydziału
    z innej uczelni przez metryczkę historyczną NIE rzuca już wyjątku na
    poziomie bazy. (Walidacja uczelni została też usunięta z
    Jednostka_Rodzic.clean() — patrz test_jednostka_rodzic_cross_uczelnia.)"""

    u1 = baker.make(Uczelnia)
    u2 = baker.make(Uczelnia)

    w1 = baker.make(Wydzial, uczelnia=u1)
    w2 = baker.make(Wydzial, uczelnia=u2)

    j1 = baker.make(Jednostka, uczelnia=u1)
    assert j1.wydzial is None

    # Cross-uczelnia — zapisuje się bez wyjątku po zdjęciu triggera. Faza B
    # (#438), II-1: historia ``Jednostka_Rodzic`` NIE steruje już ``wydzial``
    # (denorm z MPTT ``parent``), więc nie asertujemy tu ``wydzial``.
    jw_cross = Jednostka_Rodzic.objects.create(jednostka=j1, parent=_wezel(w2))
    j1.refresh_from_db()
    jw_cross.delete()

    jw = Jednostka_Rodzic.objects.create(jednostka=j1, parent=_wezel(w1))

    for elem in (jw, j1, w2, w1, u2, u1):
        elem.delete()


@pytest.mark.django_db(transaction=True)
def test_jednostka_wydzial_time_trigger():
    """Sprawdź, czy nie da się przypisać jednej tej samej jednostki do dwóch
    wydziałów w tym samym czasie"""

    u1 = baker.make(Uczelnia)
    w1 = baker.make(Wydzial, uczelnia=u1)

    w2 = baker.make(Wydzial, uczelnia=u1)
    j1 = baker.make(Jednostka, uczelnia=u1)

    jw1 = Jednostka_Rodzic.objects.create(
        jednostka=j1,
        parent=_wezel(w1),
    )

    jw2 = Jednostka_Rodzic(jednostka=j1, parent=_wezel(w2), od=date(2001, 1, 1))
    with pytest.raises(IntegrityError):
        jw2.save()

    jw2 = Jednostka_Rodzic(jednostka=j1, parent=_wezel(w2), do=date(2001, 1, 1))
    with pytest.raises(IntegrityError):
        jw2.save()

    for elem in u1, w1, j1, jw1:
        elem.delete()


@pytest.mark.django_db(transaction=True)
def test_jednostka_wydzial_bez_dat_do_w_przyszlosci_constraint():
    """Sprawdź, czy przypisanie daty 'do' w przyszłości da błąd"""
    u1 = baker.make(Uczelnia)
    w1 = baker.make(Wydzial, uczelnia=u1)
    j1 = baker.make(Jednostka, uczelnia=u1)
    jw = Jednostka_Rodzic(
        jednostka=j1,
        parent=_wezel(w1),
        od=date.today() - timedelta(days=30),
        do=date.today(),
    )

    with pytest.raises(IntegrityError):
        jw.save()

    for elem in u1, w1, j1:
        elem.delete()


@pytest.mark.django_db(transaction=True)
def test_jednostka_wydzial_time_trigger_delete_1():
    """Faza B (#438): stary trigger bpp_jednostka_ustaw_wydzial_aktualna
    rzucał wyjątek DB przy zmianie jednostka_id. Trigger zdjęty — zapis na
    poziomie bazy już NIE rzuca (guard „zmiana ID jednostki nie jest
    obsługiwana" żyje teraz tylko w Jednostka_Rodzic.clean(), co pokrywa
    test_jednostka_wydzial_save_trigger_zmiana_jednostka_id). Sygnał po
    zapisie przelicza pola dla nowej jednostki."""

    u1 = baker.make(Uczelnia)
    w1 = baker.make(Wydzial, uczelnia=u1)

    j1 = baker.make(Jednostka, uczelnia=u1)
    j2 = baker.make(Jednostka, uczelnia=u1)

    jw1 = Jednostka_Rodzic.objects.create(
        jednostka=j1,
        parent=_wezel(w1),
    )

    jw1.jednostka = j2
    # Po zdjęciu triggera zapis się udaje (brak wyjątku DB):
    jw1.save()

    j2.refresh_from_db()
    # Faza B (#438), II-1: ``wydzial`` nie jest już derywatem historii.
    assert j2.aktualna is True

    for elem in u1, w1, j1, j2, jw1:
        elem.delete()


@pytest.mark.django_db
def test_jednostka_wydzial_time_trigger_delete_2():
    """Sprawdź, czy po dodaniu wartości do metryczki historycznej możliwe
    będzie usunięcie tychże (że nie wywali wówczas triggera)"""

    u1 = baker.make(Uczelnia)
    w1 = baker.make(Wydzial, uczelnia=u1)
    j1 = baker.make(Jednostka, uczelnia=u1)

    jw1 = Jednostka_Rodzic.objects.create(
        jednostka=j1,
        parent=_wezel(w1),
    )

    jw1.delete()

    j1.refresh_from_db()

    assert j1.wydzial is None
    assert j1.aktualna is False

    for elem in u1, w1, j1:
        elem.delete()


@pytest.mark.django_db
def test_jednostka_wydzial_save_trigger_zakres_dat():
    """Sprawdź, walidacja obiektu Jednostka_Rodzic zwróci prawidłowy błąd dla dwóch zachodzących na siebie
    zakresów dat przy przypisaniu."""

    u1 = baker.make(Uczelnia)
    w1 = baker.make(Wydzial, uczelnia=u1)
    w2 = baker.make(Wydzial, uczelnia=u1)

    j1 = baker.make(Jednostka, uczelnia=u1)

    jw1 = Jednostka_Rodzic.objects.create(  # noqa
        jednostka=j1, parent=_wezel(w1), od=date(2000, 1, 1), do=date(2000, 2, 1)
    )

    jw2 = Jednostka_Rodzic(
        jednostka=j1, parent=_wezel(w2), od=date(2000, 1, 15), do=date(2000, 2, 20)
    )

    with pytest.raises(ValidationError):
        jw2.clean()

    jw2 = Jednostka_Rodzic(
        jednostka=j1, parent=_wezel(w2), od=date(2001, 1, 15), do=None
    )

    # ValidationError nie został podniesiony
    jw2.clean()


@pytest.mark.django_db
def test_jednostka_wydzial_save_trigger_zmiana_jednostka_id():
    """Sprawdź, czy walidacja obiektu Jednostka_Rodzic zwróci prawidłowy błąd przy próbie zmiany jednostka_id,
    któro to z kolei nie jest obsługiwane przez triggery bazodanowe."""

    u1 = baker.make(Uczelnia)
    w1 = baker.make(Wydzial, uczelnia=u1)
    w2 = baker.make(Wydzial, uczelnia=u1)  # noqa

    j1 = baker.make(Jednostka, uczelnia=u1)
    j2 = baker.make(Jednostka, uczelnia=u1)

    jw1 = Jednostka_Rodzic.objects.create(
        jednostka=j1, parent=_wezel(w1), od=date(2000, 1, 1), do=date(2000, 2, 1)
    )

    jw1.jednostka = j2

    with pytest.raises(ValidationError):
        jw1.clean()


@pytest.mark.django_db
def test_jednostka_rodzic_cross_uczelnia_clean_nie_rzuca():
    """Faza B (#438): walidacja równości uczelni usunięta z
    Jednostka_Rodzic.clean() (federacja, Zasada #4). Krawędź między-uczelniana
    (jednostka uczelni u1, węzeł-rodzic uczelni u2) NIE rzuca już
    ValidationError."""

    u1 = baker.make(Uczelnia)
    w1 = baker.make(Wydzial, uczelnia=u1)  # noqa

    u2 = baker.make(Uczelnia)
    w2 = baker.make(Wydzial, uczelnia=u2)

    j1 = baker.make(Jednostka, uczelnia=u1)

    jw = Jednostka_Rodzic(jednostka=j1, parent=_wezel(w2))

    # Brak ValidationError — federacja dopuszcza krawędź między-uczelnianą:
    jw.clean()


@pytest.mark.django_db
def test_jednostka_save_trigger_data_w_przyszlosci():
    """Sprawdź, czy podanie daty "do" w przyszłości nie przejdzie"""
    u1 = baker.make(Uczelnia)
    w1 = baker.make(Wydzial, uczelnia=u1)
    j1 = baker.make(Jednostka, uczelnia=u1)
    jw = Jednostka_Rodzic(
        jednostka=j1,
        parent=_wezel(w1),
        od=date.today() - timedelta(days=30),
        do=date.today(),
    )

    with pytest.raises(ValidationError):
        jw.clean()


@pytest.mark.django_db
def test_jednostka_save_trigger_dwa_zakresy_bug():
    u1 = baker.make(Uczelnia)
    w1 = baker.make(Wydzial, uczelnia=u1)
    w2 = baker.make(Wydzial, uczelnia=u1)
    j1 = baker.make(Jednostka, uczelnia=u1)

    Jednostka_Rodzic.objects.create(
        jednostka=j1, parent=_wezel(w1), od=None, do=datetime(2013, 1, 1)
    )

    jw = Jednostka_Rodzic.objects.create(
        jednostka=j1, parent=_wezel(w2), od=datetime(2013, 1, 2), do=None
    )

    # Faza B (#438), II-1: ``wydzial`` nie jest już derywatem historii
    # (denorm z MPTT ``parent``). Testujemy, że wielozakresowa historia
    # zapisuje się bez błędu i że sygnał utrzymuje ``aktualna``.
    j1.refresh_from_db()
    assert j1.aktualna is True

    jw.do = datetime(2013, 1, 3)
    jw.save()

    Jednostka_Rodzic.objects.create(
        jednostka=j1, parent=_wezel(w1), od=datetime(2013, 1, 4), do=None
    )

    j1.refresh_from_db()
    assert j1.aktualna is True


@pytest.mark.django_db
def test_wyczysc_przypisania_wariant_1(wydzial, jednostka):
    Jednostka_Rodzic.objects.create(
        parent=_wezel(wydzial), jednostka=jednostka, od=None, do=date(2012, 6, 1)
    )
    Jednostka_Rodzic.objects.wyczysc_przypisania(
        jednostka, date(2012, 1, 1), date(2012, 12, 31)
    )
    assert jednostka.wydzial_dnia(date(2011, 12, 31)) == wydzial
    assert jednostka.wydzial_dnia(date(2012, 1, 1)) is None
    assert jednostka.wydzial_dnia(date(2012, 6, 1)) is None
    assert jednostka.wydzial_dnia(date(2012, 12, 31)) is None
    assert jednostka.wydzial_dnia(date(2013, 1, 1)) is None


@pytest.mark.django_db
def test_wyczysc_przypisania_wariant_2(wydzial, jednostka):
    Jednostka_Rodzic.objects.create(parent=_wezel(wydzial), jednostka=jednostka)
    Jednostka_Rodzic.objects.wyczysc_przypisania(
        jednostka, date(2012, 1, 1), date(2012, 12, 31)
    )
    assert jednostka.wydzial_dnia(date(2011, 12, 31)) == wydzial
    assert jednostka.wydzial_dnia(date(2012, 1, 1)) is None
    assert jednostka.wydzial_dnia(date(2012, 6, 1)) is None
    assert jednostka.wydzial_dnia(date(2012, 12, 31)) is None
    assert jednostka.wydzial_dnia(date(2013, 1, 1)) == wydzial


@pytest.mark.django_db
def test_wyczysc_przypisania_wariant_3(wydzial, jednostka):
    Jednostka_Rodzic.objects.create(
        parent=_wezel(wydzial), jednostka=jednostka, od=date(2012, 6, 1), do=None
    )
    Jednostka_Rodzic.objects.wyczysc_przypisania(
        jednostka, date(2012, 1, 1), date(2012, 12, 31)
    )
    assert jednostka.wydzial_dnia(date(2011, 12, 31)) is None
    assert jednostka.wydzial_dnia(date(2012, 1, 1)) is None
    assert jednostka.wydzial_dnia(date(2012, 6, 1)) is None
    assert jednostka.wydzial_dnia(date(2012, 12, 31)) is None
    assert jednostka.wydzial_dnia(date(2013, 1, 1)) == wydzial


@pytest.mark.django_db
def test_wyczysc_przypisania_wariant_corner_case_left(wydzial, jednostka):
    Jednostka_Rodzic.objects.create(
        parent=_wezel(wydzial),
        jednostka=jednostka,
        od=date(2011, 12, 31),
        do=date(2012, 12, 31),
    )
    Jednostka_Rodzic.objects.wyczysc_przypisania(
        jednostka, date(2012, 1, 1), date(2012, 12, 31)
    )
    assert jednostka.wydzial_dnia(date(2011, 12, 31)) == wydzial
    assert jednostka.wydzial_dnia(date(2012, 1, 1)) is None


@pytest.mark.django_db
def test_wyczysc_przypisania_zakres_w_calosci_wewnatrz_parenta(wydzial, jednostka):
    """Branch 3: od >= parent_od and do <= parent_do → cały rekord usuwany."""
    Jednostka_Rodzic.objects.create(
        parent=_wezel(wydzial),
        jednostka=jednostka,
        od=date(2012, 3, 1),
        do=date(2012, 9, 30),
    )
    Jednostka_Rodzic.objects.wyczysc_przypisania(
        jednostka, date(2012, 1, 1), date(2012, 12, 31)
    )
    assert not Jednostka_Rodzic.objects.filter(
        jednostka=jednostka, parent=_wezel(wydzial)
    ).exists()


@pytest.mark.django_db
def test_wyczysc_przypisania_zakres_obejmuje_parenta(wydzial, jednostka):
    """Branch 2: od < parent_od and do > parent_do → split na dwa rekordy.
    Wcześniej brakowało jawnego testu na "lewy bok" splitu."""
    Jednostka_Rodzic.objects.create(
        parent=_wezel(wydzial),
        jednostka=jednostka,
        od=date(2010, 1, 1),
        do=date(2014, 12, 31),
    )
    Jednostka_Rodzic.objects.wyczysc_przypisania(
        jednostka, date(2012, 1, 1), date(2012, 12, 31)
    )
    assert (
        Jednostka_Rodzic.objects.filter(
            jednostka=jednostka, parent=_wezel(wydzial)
        ).count()
        == 2
    )
    assert jednostka.wydzial_dnia(date(2011, 12, 31)) == wydzial
    assert jednostka.wydzial_dnia(date(2012, 6, 1)) is None
    assert jednostka.wydzial_dnia(date(2013, 1, 1)) == wydzial
    assert jednostka.wydzial_dnia(date(2014, 12, 31)) == wydzial


@pytest.mark.django_db
def test_wyczysc_przypisania_wiele_zakresow_w_jednym_wywolaniu(wydzial, jednostka):
    """Wiele zachodzących na siebie z parentem rekordów — wszystkie powinny
    zostać prawidłowo zmodyfikowane w jednym wywołaniu."""
    # Trzy nieprzenikające się rekordy, wszystkie zachodzą na 2012:
    Jednostka_Rodzic.objects.create(
        parent=_wezel(wydzial),
        jednostka=jednostka,
        od=date(2010, 1, 1),
        do=date(2012, 3, 31),
    )
    Jednostka_Rodzic.objects.create(
        parent=_wezel(wydzial),
        jednostka=jednostka,
        od=date(2012, 5, 1),
        do=date(2012, 8, 31),
    )
    Jednostka_Rodzic.objects.create(
        parent=_wezel(wydzial),
        jednostka=jednostka,
        od=date(2012, 10, 1),
        do=date(2014, 12, 31),
    )

    Jednostka_Rodzic.objects.wyczysc_przypisania(
        jednostka, date(2012, 1, 1), date(2012, 12, 31)
    )

    # W całym 2012 ma nie być żadnego przypisania:
    assert jednostka.wydzial_dnia(date(2012, 6, 15)) is None
    assert jednostka.wydzial_dnia(date(2012, 11, 15)) is None
    # Przed i po 2012 — przypisania zachowane:
    assert jednostka.wydzial_dnia(date(2010, 6, 1)) == wydzial
    assert jednostka.wydzial_dnia(date(2013, 6, 1)) == wydzial


@pytest.mark.django_db
def test_wyczysc_przypisania_parent_od_none_wymaga_parent_do(wydzial, jednostka):
    """Bez parent_od funkcja porównuje None z date — to wybucha TypeError-em.
    Dokumentujemy aktualny kontrakt: caller MUSI podać parent_od.

    Jeśli to się kiedyś zmieni, ten test też trzeba zaktualizować."""
    Jednostka_Rodzic.objects.create(
        parent=_wezel(wydzial),
        jednostka=jednostka,
        od=date(2010, 1, 1),
        do=date(2014, 12, 31),
    )

    with pytest.raises(TypeError):
        Jednostka_Rodzic.objects.wyczysc_przypisania(
            jednostka, parent_od=None, parent_do=date(2012, 12, 31)
        )
