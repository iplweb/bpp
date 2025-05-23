import pytest
from model_bakery import baker

from import_common.core import matchuj_dyscypline
from import_dyscyplin.core import matchuj_autora, matchuj_jednostke, matchuj_wydzial

from bpp.models import Autor, Dyscyplina_Naukowa, Jednostka, Tytul, Wydzial


@pytest.mark.parametrize(
    "szukany_string",
    [
        "II Lekarski",
        "II Lekarski ",
        "ii lekarski",
        "   ii lekarski  ",
    ],
)
def test_matchuj_wydzial(szukany_string, db):
    baker.make(Wydzial, nazwa="I Lekarski")
    w2 = baker.make(Wydzial, nazwa="II Lekarski")

    assert matchuj_wydzial(szukany_string) == w2


@pytest.mark.parametrize(
    "szukany_string",
    ["Jednostka Pierwsza", "  Jednostka Pierwsza  \t", "jednostka pierwsza"],
)
def test_matchuj_jednostke(szukany_string, uczelnia, wydzial, db):
    j1 = baker.make(
        Jednostka, nazwa="Jednostka Pierwsza", wydzial=wydzial, uczelnia=uczelnia
    )
    baker.make(
        Jednostka,
        nazwa="Jednostka Pierwsza i Jeszcze",
        wydzial=wydzial,
        uczelnia=uczelnia,
    )

    assert matchuj_jednostke(szukany_string) == j1


def test_matchuj_autora_imiona_nazwisko(autor_jan_nowak):
    a = matchuj_autora("Jan", "Nowak", jednostka=None)
    assert a == autor_jan_nowak


def test_matchuj_autora_imiona_nazwisko_dwa_imiona_w_matchu(autor_jan_nowak):
    a = matchuj_autora("Jan Tadeusz Wiśniowiecki", "Nowak", jednostka=None)
    assert a == autor_jan_nowak


@pytest.mark.django_db
def test_matchuj_autora_po_aktualnej_jednostce():
    j1 = baker.make(Jednostka)
    j2 = baker.make(Jednostka)

    a1 = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    a1.dodaj_jednostke(j1)

    a2 = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    a2.dodaj_jednostke(j2)

    a = matchuj_autora(imiona="Jan", nazwisko="Kowalski", jednostka=None)
    assert a is None

    a = matchuj_autora(imiona="Jan", nazwisko="Kowalski", jednostka=j1)
    assert a == a1

    a = matchuj_autora(imiona="Jan", nazwisko="Kowalski", jednostka=j2)
    assert a == a2


@pytest.mark.django_db
def test_matchuj_autora_po_jednostce():
    j1 = baker.make(Jednostka)
    j2 = baker.make(Jednostka)

    a1 = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    a1.dodaj_jednostke(j1)
    a1.aktualna_jednostka = None
    a1.save()

    a2 = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    a2.dodaj_jednostke(j2)
    a2.aktualna_jednostka = None
    a2.save()

    a = matchuj_autora(imiona="Jan", nazwisko="Kowalski", jednostka=j1)
    assert a == a1

    a = matchuj_autora(imiona="Jan", nazwisko="Kowalski", jednostka=j2)
    assert a == a2


@pytest.mark.django_db
def test_matchuj_autora_po_tytule():
    t = Tytul.objects.create(nazwa="prof hab", skrot="lol.")

    baker.make(Jednostka)

    a1 = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    a1.tytul = t
    a1.save()

    baker.make(Autor, imiona="Jan", nazwisko="Kowalski")

    a = matchuj_autora(
        imiona="Jan",
        nazwisko="Kowalski",
    )
    # Jeżeli szukamy autora a jest podobny w systemie to matchuj tego ktory ma tytuł lub orcid
    assert a.pk == a1.pk

    a = matchuj_autora(imiona="Jan", nazwisko="Kowalski", tytul_str="lol.")
    assert a.pk == a1.pk


@pytest.mark.django_db
def test_matchuj_autora_tytul_bug(jednostka):
    matchuj_autora("Kowalski", "Jan", jednostka, tytul_str="Doktur")
    assert True


@pytest.mark.parametrize(
    "kod,nazwa",
    [
        ("403_0", "aoijsdf"),
        ("403_0", None),
        (None, "foo"),
        ("403_0", "aoijsdf     "),
        ("403", "aoijsdf"),
        ("4.3", "aoijsdf"),
        ("nieno", "foo"),
        ("xxx", "foo (dziedzina nauk bylejakich)"),
    ],
)
@pytest.mark.django_db
def test_matchuj_dyscypline(kod, nazwa):
    d = Dyscyplina_Naukowa.objects.create(nazwa="foo", kod="4.3")

    assert matchuj_dyscypline(kod, nazwa) == d


@pytest.mark.django_db
def test_matchuj_dyscypline_o_Ziemi():
    NAZWA = "nauki o Ziemi i środowisku"
    d = Dyscyplina_Naukowa.objects.create(kod="123", nazwa=NAZWA)
    assert matchuj_dyscypline(kod=None, nazwa=NAZWA).pk == d.pk
