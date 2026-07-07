try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

import pytest
from django.contrib.auth.models import Group
from model_bakery import baker

from bpp.models import Autor, Jednostka, RodzajJednostki
from bpp.models.cache import Rekord
from bpp.models.system import Charakter_Formalny, Typ_Odpowiedzialnosci
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor
from bpp.tests.util import (
    any_autor,
    any_ciagle,
    any_doktorat,
    any_habilitacja,
    any_jednostka,
    any_uczelnia,
)
from bpp.util import rebuild_contenttypes
from bpp.views.browse import AutorView, AutorzyView, get_available_letters


class FakeUnauthenticatedUser:
    def is_authenticated(self):
        return False


@pytest.fixture
def setup_group(db):
    """Fixture tworzący grupę wprowadzania danych."""
    Group.objects.get_or_create(name="wprowadzanie danych")


def _rodzaj_wydzial():
    # Faza C (#438): rolę „wydziału" (strona w stylu strukturalnym) pełni
    # jednostka top-level z rodzajem o ``pokazuj_strukture_podjednostek=True``.
    # Dawniej ustawiał to węzeł-lustro (znajdz_lub_utworz_wezel_wydzialu).
    rodzaj, _ = RodzajJednostki.objects.get_or_create(
        nazwa="Wydział", defaults={"pokazuj_strukture_podjednostek": True}
    )
    if not rodzaj.pokazuj_strukture_podjednostek:
        rodzaj.pokazuj_strukture_podjednostek = True
        rodzaj.save()
    return rodzaj


@pytest.mark.django_db
def test_root_empty(setup_group, logged_in_client):
    res = logged_in_client.get("/")
    assert res.status_code == 200
    assert b"W systemie nie ma" in res.content


@pytest.mark.django_db
def test_root_with_uczelnia(setup_group, logged_in_client):
    any_uczelnia(nazwa="uczelnia 123", skrot="uu123")
    res = logged_in_client.get("/", follow=False)
    assert b"uczelnia 123" in res.content


@pytest.mark.django_db
def test_browse_wydzial(setup_group, logged_in_client):
    u = any_uczelnia(nazwa="uczelnia", skrot="uu")
    Jednostka.objects.create(nazwa="wydzial", uczelnia=u, parent=None)
    res = logged_in_client.get(reverse("bpp:browse_uczelnia", args=("uu",)))
    assert res.status_code == 200
    assert "Wybierz wydział" in res.content.decode()


@pytest.mark.django_db
def test_browse_wydzial_redirects_to_browse_jednostka(setup_group, logged_in_client):
    """Faza C (#438): legacy URL /wydzial/<slug>/ przekierowuje 301 na
    /jednostka/<slug>/ — „wydział" to jednostka top-level o tym samym slugu
    (mapowanie 1:1 zachowane od Fazy B)."""
    u = any_uczelnia(nazwa="uczelnia", skrot="uu")
    j = any_jednostka(nazwa="Wydział Nowego Typu", uczelnia=u, wydzial=None)

    res = logged_in_client.get(
        reverse("bpp:browse_wydzial", args=(j.slug,)), follow=False
    )
    assert res.status_code == 301
    assert res.url == reverse("bpp:browse_jednostka", args=(j.slug,))


@pytest.mark.django_db
def test_browse_wydzial_redirect_404_gdy_brak_jednostki(setup_group, logged_in_client):
    """Slug bez odpowiadającej Jednostki → 404 (nie 500), żeby martwe linki
    zewnętrzne/zakładki degradowały się czytelnie."""
    any_uczelnia(nazwa="uczelnia", skrot="uu")

    res = logged_in_client.get(
        reverse("bpp:browse_wydzial", args=("nie-ma-takiego-wydzialu",)),
        follow=False,
    )
    assert res.status_code == 404


@pytest.mark.django_db
def test_jednostka_styl_strukturalny_jedno_dziecko_redirects(
    setup_group, logged_in_client
):
    """Węzeł strukturalny (rodzaj "Wydział") z jedną podjednostką
    przekierowuje na jej stronę -- tak jak dawny WydzialView."""
    u = any_uczelnia(nazwa="uczelnia", skrot="uu")
    w = Jednostka.objects.create(
        nazwa="wydzial", uczelnia=u, parent=None, rodzaj=_rodzaj_wydzial()
    )
    j = Jednostka.objects.create(
        nazwa="jedyna jednostka",
        skrot="JJ",
        parent=w,
        uczelnia=u,
        aktualna=True,
        widoczna=True,
    )

    res = logged_in_client.get(
        reverse("bpp:browse_jednostka", args=(w.slug,)), follow=False
    )
    assert res.status_code == 302
    assert res.url == reverse("bpp:browse_jednostka", args=(j.slug,))


@pytest.mark.django_db
def test_jednostka_styl_strukturalny_wiele_dzieci_shows_page(
    setup_group, logged_in_client
):
    """Węzeł strukturalny z wieloma podjednostkami wyświetla stronę w
    stylu strukturalnym (dawna strona wydziału)."""
    u = any_uczelnia(nazwa="uczelnia", skrot="uu")
    w = Jednostka.objects.create(
        nazwa="wydzial", uczelnia=u, parent=None, rodzaj=_rodzaj_wydzial()
    )
    Jednostka.objects.create(
        nazwa="jednostka 1",
        skrot="J1",
        parent=w,
        uczelnia=u,
        aktualna=True,
        widoczna=True,
    )
    Jednostka.objects.create(
        nazwa="jednostka 2",
        skrot="J2",
        parent=w,
        uczelnia=u,
        aktualna=True,
        widoczna=True,
    )

    res = logged_in_client.get(
        reverse("bpp:browse_jednostka", args=(w.slug,)), follow=False
    )
    assert res.status_code == 200
    assert b"Jednostki aktualne" in res.content


@pytest.mark.django_db
def test_jednostka_styl_strukturalny_jedno_kolo_naukowe_redirects(
    setup_group, logged_in_client
):
    """Węzeł strukturalny z jednym kołem naukowym przekierowuje na stronę
    koła."""
    u = any_uczelnia(nazwa="uczelnia", skrot="uu")
    w = Jednostka.objects.create(
        nazwa="wydzial", uczelnia=u, parent=None, rodzaj=_rodzaj_wydzial()
    )
    j = Jednostka.objects.create(
        nazwa="koło naukowe",
        skrot="KN",
        parent=w,
        uczelnia=u,
        aktualna=True,
        widoczna=True,
        rodzaj=RodzajJednostki.objects.get_or_create(nazwa="Koło naukowe")[0],
    )

    res = logged_in_client.get(
        reverse("bpp:browse_jednostka", args=(w.slug,)), follow=False
    )
    assert res.status_code == 302
    assert res.url == reverse("bpp:browse_jednostka", args=(j.slug,))


@pytest.mark.django_db
def test_jednostka_styl_prac_dla_rodzaju_standard(setup_group, logged_in_client):
    """Węzeł rodzaju "Standard" (bez pokazuj_strukture_podjednostek)
    renderuje dotychczasowy styl prac -- nie strukturalny."""
    u = any_uczelnia(nazwa="uczelnia", skrot="uu")
    w = Jednostka.objects.create(nazwa="wydzial", skrot="WDZ", uczelnia=u, parent=None)
    j = Jednostka.objects.create(
        nazwa="jednostka standardowa",
        skrot="JSTD",
        parent=w,
        uczelnia=u,
        rodzaj=RodzajJednostki.objects.get_or_create(nazwa="Standard")[0],
    )

    res = logged_in_client.get(reverse("bpp:browse_jednostka", args=(j.slug,)))
    assert res.status_code == 200
    content = res.content.decode()
    assert "Wyszukaj publikacje" in content
    assert "Jednostki aktualne" not in content


@pytest.mark.django_db
def test_browse_jednostka(setup_group, logged_in_client):
    u = any_uczelnia(nazwa="uczelnia", skrot="uu")
    w = Jednostka.objects.create(nazwa="wydzial", skrot="WDZ", uczelnia=u, parent=None)
    j = Jednostka.objects.create(
        nazwa="jednostka", skrot="JEDN", parent=w, uczelnia=u
    )

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


@pytest.mark.django_db
def test_autorzy_view_empty_page_redirects(client, setup_group):
    """Test: AutorzyView redirects to page 1 when EmptyPage occurs."""
    # Create test data - need 100+ authors for 2+ pages (paginate_by=50)
    any_uczelnia(nazwa="Test University", skrot="TU")
    baker.make(Autor, nazwisko="Test", imiona="Autor", pokazuj=True, _quantity=100)

    # Try to access non-existent page (we have 2 pages, try page 10)
    url = reverse("bpp:browse_autorzy") + "?page=10"
    response = client.get(url, follow=False)

    # Should get redirect (302)
    assert response.status_code == 302
    # Check redirect URL
    assert "page=1" in response.url
    # Check warning message was added
    messages_list = list(response.wsgi_request._messages)
    assert len(messages_list) == 1
    assert "Podana strona nie istnieje" in str(messages_list[0])
    assert messages_list[0].level_tag == "warning"


@pytest.mark.django_db
def test_autorzy_view_empty_page_preserves_search(client, setup_group):
    """Test: Redirect preserves search parameter."""
    any_uczelnia(nazwa="Test University", skrot="TU")
    baker.make(Autor, nazwisko="Test", imiona="Autor", pokazuj=True, _quantity=100)

    url = reverse("bpp:browse_autorzy") + "?page=10&search=Test"
    response = client.get(url, follow=True)

    assert response.status_code == 200
    redirect_url = response.redirect_chain[0][0]
    assert "search=Test" in redirect_url
    assert "page=1" in redirect_url


@pytest.mark.django_db
def test_autorzy_view_empty_page_preserves_literka_in_path(client, setup_group):
    """Test: Redirect preserves literka in URL path."""
    any_uczelnia(nazwa="Test University", skrot="TU")
    # Create 100 authors starting with 'A'
    baker.make(Autor, nazwisko="Atest", imiona="Autor", pokazuj=True, _quantity=100)

    url = reverse("bpp:browse_autorzy_literka", kwargs={"literka": "A"}) + "?page=10"
    response = client.get(url, follow=True)

    assert response.status_code == 200
    redirect_url = response.redirect_chain[0][0]
    assert "/bpp/autorzy/A/" in redirect_url
    assert "page=1" in redirect_url


@pytest.mark.django_db
def test_autorzy_view_page_not_integer_redirects(client, setup_group):
    """Test: Non-integer page values redirect to page 1."""
    any_uczelnia(nazwa="Test University", skrot="TU")
    baker.make(Autor, nazwisko="Test", imiona="Autor", pokazuj=True, _quantity=100)

    url = reverse("bpp:browse_autorzy") + "?page=abc"
    response = client.get(url, follow=True)

    assert response.status_code == 200
    assert "page=1" in response.redirect_chain[0][0]
    # Check warning message
    messages_list = list(response.context["messages"])
    assert len(messages_list) == 1
    assert "Podana strona nie istnieje" in str(messages_list[0])


# =============================================================================
# get_available_letters: pojedyncze zapytanie zamiast N+1.
# Patrz ANALYSIS.md #4 (2026-05-02).
# =============================================================================


@pytest.mark.django_db
def test_get_available_letters_polish_diacritics_canonical():
    """Polskie znaki diakrytyczne mapują się na kanoniczną literkę."""
    any_uczelnia(nazwa="X", skrot="X")
    baker.make(Autor, nazwisko="Ąbrowski", pokazuj=True)
    baker.make(Autor, nazwisko="ćwiek", pokazuj=True)
    baker.make(Autor, nazwisko="Łyk", pokazuj=True)
    baker.make(Autor, nazwisko="Ñowak", pokazuj=True)  # nie z LITERKI

    letters = get_available_letters(Autor.objects.all(), "nazwisko")

    assert "A" in letters
    assert "C" in letters
    assert "L" in letters
    # Ñ nie jest w LITERKI ani PODWOJNE → pomijane
    assert "N" not in letters


@pytest.mark.django_db
def test_get_available_letters_runs_single_query(django_assert_num_queries):
    """Regresja: jedno zapytanie, niezależnie od liczby liter."""
    any_uczelnia(nazwa="X", skrot="X")
    baker.make(Autor, nazwisko="Adam", pokazuj=True)
    baker.make(Autor, nazwisko="Bartek", pokazuj=True)
    baker.make(Autor, nazwisko="Cezary", pokazuj=True)

    with django_assert_num_queries(1):
        letters = get_available_letters(Autor.objects.all(), "nazwisko")

    assert {"A", "B", "C"} <= letters


@pytest.mark.django_db
def test_get_available_letters_respects_queryset_filter():
    """Pre-filtry queryseta są zachowane (nie pokazujemy ukrytych autorów)."""
    any_uczelnia(nazwa="X", skrot="X")
    baker.make(Autor, nazwisko="Adam", pokazuj=True)
    baker.make(Autor, nazwisko="Bartek", pokazuj=False)

    letters = get_available_letters(Autor.objects.filter(pokazuj=True), "nazwisko")
    assert letters == {"A"}
