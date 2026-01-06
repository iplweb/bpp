from datetime import date, datetime

import pytest
from django.core.exceptions import ValidationError
from model_bakery import baker

from bpp.models import (
    Autor,
    Jezyk,
    Patent,
    Plec,
    Punktacja_Zrodla,
    Redakcja_Zrodla,
    Typ_Odpowiedzialnosci,
    Tytul,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Zrodlo,
)
from bpp.models.autor import Autor_Jednostka, Funkcja_Autora
from bpp.models.system import Charakter_Formalny
from bpp.tests.util import (
    any_autor,
    any_ciagle,
    any_jednostka,
    any_uczelnia,
    any_wydzial,
    any_zwarte,
)


@pytest.mark.django_db
def test_nazwa_i_skrot():
    """Test modelu z nazwą i skrótem."""
    a = Charakter_Formalny(nazwa="foo", skrot="bar")
    assert str(a) == "foo"


@pytest.mark.django_db
def test_tytul():
    """Test modelu Tytul."""
    t = baker.make(Tytul)
    str(t)


@pytest.mark.django_db
def test_wydzial():
    """Test modelu Wydzial."""
    u = any_uczelnia()
    w = any_wydzial(nazwa="Lekarski", uczelnia=u)
    assert str(w) == "Lekarski"


@pytest.fixture
def jednostka_setup(db):
    """Fixture dla testów jednostki."""
    Typ_Odpowiedzialnosci.objects.get_or_create(nazwa="autor", skrot="aut.")
    Funkcja_Autora.objects.get_or_create(nazwa="kierownik", skrot="kier.")


def test_jednostka(jednostka_setup):
    """Test modelu Jednostka."""
    from django.conf import settings

    any_wydzial(skrot="BAR")
    j = any_jednostka(nazwa="foo", wydzial_skrot="BAR")

    # Check if wydzial should be included in the string representation
    if getattr(settings, "DJANGO_BPP_UCZELNIA_UZYWA_WYDZIALOW", True) and getattr(
        settings, "DJANGO_BPP_SKROT_WYDZIALU_W_NAZWIE_JEDNOSTKI", True
    ):
        assert str(j) == "foo (BAR)"
    else:
        assert str(j) == "foo"


def test_obecni_autorzy(jednostka_setup):
    """Test pobierania obecnych autorów jednostki."""
    j1 = any_jednostka()

    a1 = baker.make(Autor)
    a2 = baker.make(Autor)
    a3 = baker.make(Autor)

    j1.dodaj_autora(a1, rozpoczal_prace=date(2012, 1, 1))
    j1.dodaj_autora(a2, zakonczyl_prace=date(2012, 12, 31))
    j1.dodaj_autora(a3)

    obecni = j1.obecni_autorzy()

    assert a1 in obecni
    assert a2 not in obecni
    assert a3 in obecni


def test_kierownik(jednostka_setup):
    """Test pobierania kierownika jednostki."""
    j1 = any_jednostka()
    assert j1.kierownik() is None

    a1 = baker.make(Autor)
    j1.dodaj_autora(a1, funkcja=Funkcja_Autora.objects.get(nazwa="kierownik"))

    assert j1.kierownik() == a1


def test_prace_w_latach(jednostka_setup):
    """Test pobierania lat prac jednostki."""
    j1 = any_jednostka()

    a1 = baker.make(Autor)

    wc = any_ciagle(rok=2012)
    Wydawnictwo_Ciagle_Autor.objects.create(
        rekord=wc,
        autor=a1,
        jednostka=j1,
        typ_odpowiedzialnosci=baker.make(Typ_Odpowiedzialnosci),
    )

    wc = any_ciagle(rok=2013)
    Wydawnictwo_Ciagle_Autor.objects.create(
        rekord=wc,
        autor=a1,
        jednostka=j1,
        typ_odpowiedzialnosci=baker.make(Typ_Odpowiedzialnosci),
    )

    assert list(j1.prace_w_latach()) == [2012, 2013]


@pytest.mark.django_db
def test_autor():
    """Test modelu Autor."""
    j = baker.make(Autor, imiona="Omg", nazwisko="Lol", tytul=None)
    assert str(j) == "Lol Omg"

    t = Tytul.objects.create(nazwa="daktur", skrot="dar")
    j = baker.make(Autor, imiona="Omg", nazwisko="Lol", tytul=t)
    assert str(j) == "Lol Omg, dar"

    j.poprzednie_nazwiska = "Kowalski"
    assert str(j) == "Lol Omg (Kowalski), dar"

    assert j.get_full_name() == "Omg Lol (Kowalski)"
    assert j.get_full_name_surname_first() == "Lol (Kowalski) Omg"


@pytest.mark.django_db
def test_afiliacja_na_rok():
    """Test sprawdzania afiliacji autora na rok."""
    w = any_wydzial()
    n = any_wydzial(skrot="w2", nazwa="w2")
    j = any_jednostka(wydzial=w)
    a = baker.make(Autor)

    aj = Autor_Jednostka.objects.create(
        autor=a, jednostka=j, funkcja=baker.make(Funkcja_Autora)
    )

    assert a.afiliacja_na_rok(2030, w) is None
    assert a.afiliacja_na_rok(2030, n) is None

    aj.rozpoczal_prace = date(2012, 1, 1)
    aj.save()

    assert a.afiliacja_na_rok(2030, w) is True
    assert a.afiliacja_na_rok(2011, w) is None
    assert a.afiliacja_na_rok(2030, n) is None

    aj.zakonczyl_prace = date(2013, 12, 31)
    aj.save()

    assert a.afiliacja_na_rok(2030, w) is None
    assert a.afiliacja_na_rok(2011, w) is None
    assert a.afiliacja_na_rok(2012, w) is True
    assert a.afiliacja_na_rok(2030, n) is None


@pytest.mark.django_db
def test_dodaj_jednostke():
    """Test dodawania jednostki do autora."""
    f = baker.make(Funkcja_Autora)
    a = baker.make(Autor, imiona="Foo", nazwisko="Bar", tytul=None)
    w = any_wydzial(nazwa="WL", skrot="WL")
    w2 = any_wydzial(nazwa="XX", skrot="YY")
    j = any_jednostka(wydzial=w)
    j2 = any_jednostka(wydzial=w2)

    def ma_byc(ile=1):
        assert Autor_Jednostka.objects.count() == ile

    a.dodaj_jednostke(j, 1912, f)
    ma_byc(1)

    a.dodaj_jednostke(j, 1913, f)
    ma_byc(1)

    a.dodaj_jednostke(j, 1914, f)
    ma_byc(1)

    a.dodaj_jednostke(j, 1913, f)
    ma_byc(1)

    a.dodaj_jednostke(j, 1920, f)
    ma_byc(2)

    a.dodaj_jednostke(j, 1921, f)
    ma_byc(2)

    a.dodaj_jednostke(j, 1960, f)
    ma_byc(3)

    lx = Autor_Jednostka.objects.all().order_by("rozpoczal_prace")
    assert lx[0].rozpoczal_prace == date(1912, 1, 1)
    assert lx[1].rozpoczal_prace == date(1920, 1, 1)

    assert lx[0].zakonczyl_prace == date(1914, 12, 31)
    assert lx[1].zakonczyl_prace == date(1921, 12, 31)

    assert a.afiliacja_na_rok(1912, w) is True
    assert a.afiliacja_na_rok(1913, w) is True
    assert a.afiliacja_na_rok(1914, w) is True
    assert a.afiliacja_na_rok(1914, w2) is None

    assert a.afiliacja_na_rok(1920, w) is True
    assert a.afiliacja_na_rok(1921, w) is True

    assert a.afiliacja_na_rok(1922, w) is None
    assert a.afiliacja_na_rok(1916, w) is None

    # Gdy jest wpisany tylko początek czasu pracy, traktujemy pracę
    # jako NIE zakończoną i każda data w przyszłości ma zwracać to miejsce
    Autor_Jednostka.objects.create(
        autor=a, jednostka=j2, rozpoczal_prace=date(2100, 1, 1)
    )
    assert a.afiliacja_na_rok(2200, w2) is True

    Autor_Jednostka.objects.all().delete()
    # Gdy nie ma dat początku i końca pracy, to funkcja ma zwracać NONE
    Autor_Jednostka.objects.create(autor=a, jednostka=j2)
    assert a.afiliacja_na_rok(2100, w2) is None
    assert a.afiliacja_na_rok(1100, w2) is None


@pytest.mark.django_db
def test_autor_save():
    """Test zapisu autora i generowania sortowania."""
    a = Autor.objects.create(nazwisko="von Foo", imiona="Bar")
    assert a.sort == "foobar"


@pytest.mark.django_db
def test_autor_prace_w_latach():
    """Test pobierania lat prac autora."""
    ROK = 2000

    a = baker.make(Autor)
    j = any_jednostka()
    w = baker.make(Wydawnictwo_Ciagle, rok=ROK)
    baker.make(Wydawnictwo_Ciagle_Autor, autor=a, jednostka=j, rekord=w)

    assert a.prace_w_latach()[0] == ROK


@pytest.fixture
def autor_jednostka_setup(db):
    """Fixture dla testów Autor_Jednostka."""
    Typ_Odpowiedzialnosci.objects.get_or_create(nazwa="autor", skrot="aut.")
    Funkcja_Autora.objects.get_or_create(skrot="kier.", nazwa="kierownik")


def test_autor_jednostka(autor_jednostka_setup):
    """Test modelu Autor_Jednostka."""
    f = Funkcja_Autora.objects.get(skrot="kier.")
    a = baker.make(Autor, imiona="Omg", nazwisko="Lol", tytul=None)
    j = any_jednostka(nazwa="Lol", skrot="L.")
    aj = Autor_Jednostka.objects.create(autor=a, jednostka=j, funkcja=f)
    assert str(aj) == "Lol Omg ↔ kierownik, L."

    aj = Autor_Jednostka.objects.create(autor=a, jednostka=j, funkcja=None)
    assert str(aj) == "Lol Omg ↔ L."

    aj.rozpoczal_prace = datetime(2012, 1, 1)
    aj.zakonczyl_prace = datetime(2012, 1, 2)
    aj.full_clean()

    aj.rozpoczal_prace = datetime(2013, 1, 1)
    aj.zakonczyl_prace = datetime(2011, 1, 1)
    with pytest.raises(ValidationError):
        aj.full_clean()


def test_defragmentuj(autor_jednostka_setup):
    """Test defragmentacji powiązań autor-jednostka."""
    w = any_wydzial()
    a = baker.make(Autor)

    j1 = any_jednostka(nazwa="X", wydzial=w)
    any_jednostka(nazwa="Y", wydzial=w)
    any_jednostka(nazwa="Z", wydzial=w)

    # Taka sytuacja ma miejsce przy imporcie danych
    Autor_Jednostka.objects.create(autor=a, jednostka=j1)
    Autor_Jednostka.objects.create(
        autor=a,
        jednostka=j1,
        rozpoczal_prace=date(2012, 1, 1),
        zakonczyl_prace=date(2012, 12, 31),
    )
    Autor_Jednostka.objects.create(
        autor=a,
        jednostka=j1,
        rozpoczal_prace=date(2013, 1, 1),
        zakonczyl_prace=date(2014, 12, 31),
    )
    Autor_Jednostka.objects.create(
        autor=a, jednostka=j1, rozpoczal_prace=date(2016, 1, 1)
    )

    Autor_Jednostka.objects.defragmentuj(a, j1)

    assert Autor_Jednostka.objects.all().count() == 2

    Autor_Jednostka.objects.all().delete()

    # Ta sytuacja ma miejsce przy powtórnym imporcie XLSa do nowego systemu
    Autor_Jednostka.objects.create(autor=a, jednostka=j1)
    Autor_Jednostka.objects.create(
        autor=a,
        jednostka=j1,
        rozpoczal_prace=date(2012, 1, 1),
        zakonczyl_prace=None,
    )
    Autor_Jednostka.objects.create(
        autor=a,
        jednostka=j1,
        rozpoczal_prace=date(2014, 1, 1),
        zakonczyl_prace=date(2015, 12, 31),
    )

    Autor_Jednostka.objects.defragmentuj(a, j1)
    aj = Autor_Jednostka.objects.all()[0]
    assert aj.rozpoczal_prace == date(2012, 1, 1)
    assert aj.zakonczyl_prace == date(2015, 12, 31)


@pytest.mark.django_db
def test_punktacja_zrodla():
    """Test modelu Punktacja_Zrodla."""
    z = baker.make(Zrodlo, nazwa="123 test")
    j = baker.make(Punktacja_Zrodla, rok="2012", impact_factor="0.5", zrodlo=z)
    assert str(j) == 'Punktacja źródła "123 test" za rok 2012'


@pytest.mark.django_db
def test_zrodlo():
    """Test modelu Zrodlo."""
    z = baker.make(Zrodlo, nazwa="foo")
    assert str(z) == "foo"

    z = baker.make(Zrodlo, nazwa="foo", nazwa_alternatywna="bar")
    assert str(z) == "foo"

    z = baker.make(
        Zrodlo, nazwa="foo", poprzednia_nazwa="bar", nazwa_alternatywna="quux"
    )
    assert str(z) == "foo (d. bar)"

    z = baker.make(Zrodlo, nazwa="foo", poprzednia_nazwa="quux")
    assert str(z) == "foo (d. quux)"


@pytest.mark.django_db
def test_zrodlo_prace_w_latach():
    """Test pobierania lat prac źródła."""
    z = baker.make(Zrodlo)
    any_ciagle(rok=2012, zrodlo=z)

    assert list(z.prace_w_latach()) == [2012]


@pytest.mark.django_db
def test_zrodlo_unicode():
    """Test reprezentacji unicode źródła."""
    z = Zrodlo(nazwa="foo", poprzednia_nazwa="bar")
    assert str(z) == "foo (d. bar)"


@pytest.fixture
def redakcja_zrodla_setup(db):
    """Fixture dla testów Redakcja_Zrodla."""
    Typ_Odpowiedzialnosci.objects.get_or_create(nazwa="autor", skrot="aut.")
    Plec.objects.get_or_create(skrot="M", nazwa="mężczyzna")
    Plec.objects.get_or_create(skrot="K", nazwa="kobieta")
    Tytul.objects.get_or_create(skrot="dr")


def test_redakcja_zrodla(redakcja_zrodla_setup):
    """Test modelu Redakcja_Zrodla."""
    a = baker.make(
        Autor,
        imiona="Jan",
        nazwisko="Kowalski",
        tytul=Tytul.objects.get(skrot="dr"),
        plec=Plec.objects.get(skrot="M"),
    )
    z = baker.make(Zrodlo, nazwa="LOL Zine")
    r = Redakcja_Zrodla.objects.create(zrodlo=z, redaktor=a, od_roku=2010, do_roku=None)

    assert str(r) == "Redaktorem od 2010 jest Kowalski Jan, dr"

    r.do_roku = 2012
    assert str(r) == "Redaktorem od 2010 do 2012 był Kowalski Jan, dr"

    a.plec = Plec.objects.get(skrot="K")
    assert str(r) == "Redaktorem od 2010 do 2012 była Kowalski Jan, dr"

    a.plec = None
    assert str(r) == "Redaktorem od 2010 do 2012 był(a) Kowalski Jan, dr"


@pytest.mark.django_db
def test_abstract():
    """Test abstrakcyjnych modeli."""
    a = baker.make(Autor, imiona="Omg", nazwisko="Lol", tytul=None)

    j = any_jednostka(skrot="foo")
    t = baker.make(Typ_Odpowiedzialnosci, skrot="X", nazwa="Y")
    r = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="AAA")
    b = Wydawnictwo_Ciagle_Autor.objects.create(
        autor=a, jednostka=j, typ_odpowiedzialnosci=t, rekord=r
    )
    assert str(b) == "Lol Omg - foo"
    assert str(r) == "AAA"
    assert str(t) == "Y"


@pytest.mark.django_db
def test_model_z_nazwa():
    """Test modelu z nazwą."""
    a = Jezyk.objects.create(nazwa="Foo", skrot="Bar")
    assert str(a) == "Foo"


@pytest.fixture
def tworzenie_modeli_setup(db):
    """Fixture dla testów tworzenia modeli autor-jednostka."""
    Typ_Odpowiedzialnosci.objects.get_or_create(nazwa="autor", skrot="aut.")


def test_tworzenie_modeli_autor_jednostka(tworzenie_modeli_setup):
    """Test automatycznego tworzenia powiązania autor-jednostka."""
    a = any_autor()
    j = any_jednostka()
    c = any_ciagle()
    c.dodaj_autora(a, j)

    # Utworzenie modelu Wydawnictwo_Ciagle_Autor powinno utworzyć model
    # Autor_Jednostka, będący powiązaniem autora a z jednostką j
    assert Autor_Jednostka.objects.filter(autor=a).count() == 1


def test_tworzenie_modeli_autor_jednostka_zwarte(tworzenie_modeli_setup):
    """Test automatycznego tworzenia powiązania autor-jednostka dla zwartych."""
    a = any_autor()
    j = any_jednostka()
    c = any_zwarte()
    c.dodaj_autora(a, j)

    # Utworzenie modelu Wydawnictwo_Zwarte_Autor powinno utworzyć model
    # Autor_Jednostka, będący powiązaniem autora a z jednostką j
    assert Autor_Jednostka.objects.filter(autor=a).count() == 1


@pytest.mark.django_db
def test_wydawnictwo_clean():
    """Test walidacji wydawnictwa."""
    for model in [any_ciagle, any_zwarte]:
        for skrot in ["PAT", "D", "H"]:
            try:
                instance = model(
                    charakter_formalny=Charakter_Formalny.objects.get(skrot=skrot)
                )
            except Charakter_Formalny.DoesNotExist:
                continue

            with pytest.raises(ValidationError):
                instance.clean_fields()


def test_patent_kasowanie(autor_jan_kowalski, jednostka, typy_odpowiedzialnosci):
    """Test kasowania patentu."""
    p = baker.make(Patent)
    p.dodaj_autora(autor_jan_kowalski, jednostka)
    p.delete()
