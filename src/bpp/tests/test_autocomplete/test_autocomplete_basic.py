"""
Basic autocomplete tests.

Tests moved from tests_legacy/test_views/test_autocomplete.py.
These tests cover basic functionality of various autocomplete views.
"""

import pytest
from model_bakery import baker

from bpp.models import Autor, Charakter_Formalny, Jednostka, Zrodlo
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.tests.helpers import UserRequestFactory
from bpp.views import autocomplete


@pytest.mark.django_db
def test_wydawnictwo_nadrzedne_autocomplete():
    Charakter_Formalny.objects.get_or_create(skrot="ROZ", nazwa="Rozdział książki")
    Charakter_Formalny.objects.get_or_create(skrot="ROZS", nazwa="Rozdział skryptu")

    x = autocomplete.Wydawnictwo_NadrzedneAutocomplete()
    x.q = "foobar"
    assert len(x.get_queryset()) is not None


@pytest.mark.django_db
def test_jednostka_autocomplete():
    x = autocomplete.JednostkaAutocomplete()
    x.q = "foobar"
    assert len(x.get_queryset()) is not None


@pytest.mark.django_db
def test_public_jednostka_autocomplete():
    x = autocomplete.PublicJednostkaAutocomplete()
    x.q = "foobar"
    assert len(x.get_queryset()) is not None


@pytest.mark.django_db
def test_konferencja_autocomplete():
    x = autocomplete.KonferencjaAutocomplete()
    x.q = "foobar"
    assert len(x.get_queryset()) is not None


@pytest.mark.django_db
def test_seria_wydawnicza_autocomplete():
    x = autocomplete.Seria_WydawniczaAutocomplete()
    x.q = "foobar"
    assert len(x.get_queryset()) is not None


@pytest.mark.django_db
def test_zrodlo_autocomplete():
    x = autocomplete.ZrodloAutocomplete()
    x.q = "foobar"
    assert len(x.get_queryset()) is not None


@pytest.mark.django_db
def test_autor_autocomplete():
    x = autocomplete.AutorAutocomplete()
    x.q = "foobar"
    assert len(x.get_queryset()) is not None
    x.q = ":"
    assert len(x.get_queryset()) is not None

    assert x.create_object("test").pk == -1

    res = x.create_object("budnik jan")
    y = Autor.objects.get(pk=res.pk)
    assert y.imiona == "Jan"
    assert y.nazwisko == "Budnik"

    res = x.create_object("kotulowska-papis ilona joanna")
    y = Autor.objects.get(pk=res.pk)
    assert y.imiona == "Ilona Joanna"
    assert y.nazwisko == "Kotulowska-Papis"


@pytest.mark.django_db
def test_global_navigation_autocomplete(test_user):
    x = autocomplete.GlobalNavigationAutocomplete()

    class MockUser:
        is_anonymous = False

    x.request = UserRequestFactory(MockUser()).get("/")
    x.q = None
    x.get_result_label("foo")
    x.get(None)
    x.q = "foobar"
    assert len(x.get_queryset()) is not None


@pytest.mark.django_db
def test_global_navigation_autocomplete_query_for_id():
    baker.make(Wydawnictwo_Ciagle, pk=123)
    x = autocomplete.GlobalNavigationAutocomplete()
    x.q = "123"
    assert len(x.get_queryset()) == 1


@pytest.mark.django_db
def test_global_navigation_autocomplete_test_every_url(client):
    S = "Foobar 123"
    baker.make(Autor, nazwisko=S)
    baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=S)
    baker.make(Zrodlo, nazwa=S)
    baker.make(Jednostka, nazwa=S)

    x = autocomplete.GlobalNavigationAutocomplete()
    x.q = "Foo"
    res = x.get_results({"object_list": list(x.get_queryset())})

    cnt = 0
    for elem in res:
        for child in elem["children"]:
            # Sprawdź, czy global-nav-redir wygeneruje poprawne przekierowanie
            url = f"/global-nav-redir/{child['id']}/"
            response = client.get(url)
            assert response.status_code == 302
            cnt += 1

    assert cnt == 4


@pytest.mark.django_db
def test_zapisany_jako_autocomplete():
    x = autocomplete.ZapisanyJakoAutocomplete()
    a = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", poprzednie_nazwiska="")
    x.forwarded = dict(autor=str(a.id))
    # Original test was `self.assertTrue(len(x.get_list()), 3)` - truthy check
    assert len(x.get_list()) > 0


@pytest.mark.django_db
def test_podrzedna_publikacja_habilitacyjna_autocomplete():
    x = autocomplete.PodrzednaPublikacjaHabilitacyjnaAutocomplete()
    a = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", poprzednie_nazwiska="")
    x.forwarded = dict(autor=str(a.id))

    x.q = "foobar"
    assert len(x.get_queryset()) is not None


@pytest.mark.django_db
def test_global_navigation_autocomplete_alt():
    x = autocomplete.GlobalNavigationAutocomplete()
    x.q = "foobar"
    assert len(x.get_queryset()) is not None
