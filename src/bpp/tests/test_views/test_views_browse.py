try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

import pytest
from django.contrib.auth.models import Group
from model_bakery import baker

from bpp.models import Autor, Jednostka, Uczelnia, Wydzial
from bpp.models.cache import Rekord
from bpp.models.system import Charakter_Formalny, Typ_Odpowiedzialnosci
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor
from bpp.tests.util import (
    any_autor,
    any_ciagle,
    any_doktorat,
    any_habilitacja,
    any_jednostka,
)
from bpp.util import rebuild_contenttypes
from bpp.views.browse import AutorView, AutorzyView


class FakeUnauthenticatedUser:
    def is_authenticated(self):
        return False


@pytest.fixture
def setup_group(db):
    """Fixture tworzący grupę wprowadzania danych."""
    Group.objects.get_or_create(name="wprowadzanie danych")


@pytest.mark.django_db
def test_root_empty(setup_group, logged_in_client):
    res = logged_in_client.get("/")
    assert res.status_code == 200
    assert b"W systemie nie ma" in res.content


@pytest.mark.django_db
def test_root_with_uczelnia(setup_group, logged_in_client):
    Uczelnia.objects.create(nazwa="uczelnia 123", skrot="uu123")
    res = logged_in_client.get("/", follow=False)
    assert b"uczelnia 123" in res.content


@pytest.mark.django_db
def test_browse_wydzial(setup_group, logged_in_client):
    u = Uczelnia.objects.create(nazwa="uczelnia", skrot="uu")
    Wydzial.objects.create(nazwa="wydzial", uczelnia=u)
    res = logged_in_client.get(reverse("bpp:browse_uczelnia", args=("uu",)))
    assert res.status_code == 200
    assert "Wybierz wydział" in res.content.decode()


@pytest.mark.django_db
def test_browse_jednostka(setup_group, logged_in_client):
    u = Uczelnia.objects.create(nazwa="uczelnia", skrot="uu")
    w = Wydzial.objects.create(nazwa="wydzial", uczelnia=u)
    j = Jednostka.objects.create(nazwa="jednostka", wydzial=w, uczelnia=u)

    res = logged_in_client.get(reverse("bpp:browse_jednostka", args=(j.slug,)))
    assert res.status_code == 200
    assert b"jednostka" in res.content


@pytest.mark.django_db
def test_browse_autorzy_get_queryset(setup_group):
    view = AutorzyView()

    class FakeRequest:
        GET = dict(search="Autor")

        def __init__(self):
            self.user = FakeUnauthenticatedUser()

    view.request = FakeRequest()
    autor = baker.make(Autor, nazwisko="Autor", imiona="Foo")
    view.kwargs = dict(literka="A")

    q = view.get_queryset()
    assert autor in list(q)


@pytest.mark.django_db
def test_browse_autorzy_get_context_data(setup_group):
    view = AutorzyView()

    class FakeRequest:
        GET = dict(search="Autor")

        def __init__(self):
            self.user = FakeUnauthenticatedUser()

    view.request = FakeRequest()
    baker.make(Autor, nazwisko="Autor", imiona="Foo")
    view.kwargs = dict(literka="A")

    view.object_list = []
    d = view.get_context_data()
    assert d["wybrana"] == "A"
    assert d["flt"] == "Autor"


@pytest.fixture
def setup_autor_view(db):
    """Fixture przygotowujący dane dla testów AutorView."""
    Group.objects.get_or_create(name="wprowadzanie danych")
    rebuild_contenttypes()


@pytest.mark.django_db
def test_browse_autor_get_context_data(setup_autor_view):
    av = AutorView()
    av.object = baker.make(Autor)
    d = av.get_context_data()
    assert "publikacje" in d["typy"]


@pytest.mark.django_db
def test_browse_autor_habilitacyjna_doktorska(setup_autor_view, logged_in_client):
    a = baker.make(Autor)
    kw = dict(autor=a, tytul_oryginalny="X", tytul="Y", uwagi="Z")
    any_doktorat(**kw)
    any_habilitacja(**kw)
    res = logged_in_client.get(reverse("bpp:browse_autor", args=(a.slug,)))
    assert b"Praca doktorska" in res.content
    assert b"Praca habilitacyjna" in res.content


@pytest.mark.django_db
def test_browse_autor_no_edit_link(setup_autor_view, logged_in_client):
    a = baker.make(Autor)
    res = logged_in_client.get(reverse("bpp:browse_autor", args=(a.slug,)))
    assert b"Otw\xc3\xb3rz do edycji" not in res.content  # "Otwórz do edycji" w UTF-8


@pytest.mark.django_db
def test_browse_autor_staff_has_edit_link(setup_autor_view, superuser_client):
    a = baker.make(Autor)
    res = superuser_client.get(reverse("bpp:browse_autor", args=(a.slug,)))
    assert "Otwórz do edycji" in res.content.decode()


@pytest.fixture
def oai_data(db, logged_in_client):
    """Fixture przygotowujący dane dla testów OAI."""
    rebuild_contenttypes()

    aut, ign = Typ_Odpowiedzialnosci.objects.get_or_create(skrot="aut.", nazwa="autor")

    ch, ign = Charakter_Formalny.objects.get_or_create(
        skrot="AC", nazwa="Artykuł w czasopismie", nazwa_w_primo="Artykuł"
    )

    ch2, ign = Charakter_Formalny.objects.get_or_create(skrot="KOM", nazwa="Komentarz")

    c = any_ciagle(tytul_oryginalny="Test foo bar", charakter_formalny=ch)

    c2 = any_ciagle(
        tytul_oryginalny="TEGO NIE BEDZIE bo nie ma nazwa_w_primo dla typu KOM",
        charakter_formalny=Charakter_Formalny.objects.get(skrot="KOM"),
    )

    a = any_autor()
    j = any_jednostka()

    for rekord in c, c2:
        Wydawnictwo_Ciagle_Autor.objects.create(
            rekord=rekord, autor=a, jednostka=j, typ_odpowiedzialnosci=aut
        )

    Rekord.objects.full_refresh()

    cnt = Rekord.objects.all().count()
    assert cnt == 2

    return {"c": c, "client": logged_in_client}


def test_oai_get_record(oai_data):
    client = oai_data["client"]
    c = oai_data["c"]

    url = reverse("bpp:oai")
    identifier = f"oai:bpp.umlub.pl:Wydawnictwo_Ciagle/{c.pk}"
    res = client.get(
        url,
        data={
            "verb": "GetRecord",
            "metadataPrefix": "oai_dc",
            "identifier": identifier,
        },
    )
    assert res.status_code == 200
    assert b"foo" in res.content


def test_oai_list_records(oai_data):
    client = oai_data["client"]

    url = reverse("bpp:oai")

    res = client.get(url, data={"verb": "ListRecords", "metadataPrefix": "oai_dc"})
    assert res.status_code == 200
    assert b"foo" in res.content
    assert b"TEGO NIE BEDZIE" not in res.content
