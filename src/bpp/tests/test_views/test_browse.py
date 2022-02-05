import json
import re
from datetime import date

import pytest
from bs4 import BeautifulSoup

from django.contrib.contenttypes.models import ContentType

from bpp.tests import normalize_html

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

from model_mommy import mommy
from multiseek.logic import EQUAL, EQUAL_FEMALE, EQUAL_NONE
from multiseek.views import MULTISEEK_SESSION_KEY

from fixtures import NORMAL_DJANGO_USER_LOGIN, NORMAL_DJANGO_USER_PASSWORD
from miniblog.models import Article

from bpp.models import (
    Autor_Jednostka,
    Funkcja_Autora,
    Jednostka,
    OpcjaWyswietlaniaField,
    Praca_Doktorska,
    Rekord,
    Typ_Odpowiedzialnosci,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)
from bpp.models.autor import Autor
from bpp.views.browse import BuildSearch, PracaViewBySlug


def test_buildSearch(settings):
    dct = {
        "zrodlo": [
            1,
        ],
        "typ": [
            1,
        ],
        "rok": [
            2013,
        ],
        "jednostka": [
            1,
        ],
        "autor": [
            1,
        ],
    }

    class mydct(dict):
        def getlist(self, value):
            return self.get(value)

    class request:
        POST = mydct(dct)
        META = {}
        session = {}

        def build_absolute_uri(self, *args, **kw):
            return "/absolute/uri"

    settings.LANGUAGE_CODE = "en"
    tbs = BuildSearch()
    tbs.request = request()
    tbs.post(request)

    expected = {
        "form_data": [
            None,
            {
                "field": "\u0179r\xf3d\u0142o",
                "operator": str(EQUAL_NONE),
                "prev_op": None,
                "value": 1,
            },
            {
                "field": "Nazwisko i imi\u0119",
                "operator": str(EQUAL_NONE),
                "prev_op": "and",
                "value": 1,
            },
            {
                "field": "Typ rekordu",
                "operator": str(EQUAL),
                "prev_op": "and",
                "value": 1,
            },
            {
                "field": "Jednostka",
                "operator": str(EQUAL_FEMALE),
                "prev_op": "and",
                "value": 1,
            },
            {"field": "Rok", "operator": str(EQUAL), "prev_op": "and", "value": 2013},
        ]
    }

    assert json.loads(request.session[MULTISEEK_SESSION_KEY]) == expected


pattern = re.compile("Strona WWW")


def nastepna_komorka_po_strona_www(dokument):
    soup = BeautifulSoup(dokument, "html.parser")
    return soup.find("th", text=pattern).parent.find("td").text.strip()


@pytest.mark.django_db
def test_darmowy_platny_dostep_www_wyswietlanie(client, wydawnictwo_ciagle, denorms):
    wydawnictwo_ciagle.www = ""
    wydawnictwo_ciagle.public_www = ""
    wydawnictwo_ciagle.save()

    res = client.get(
        reverse(
            "bpp:browse_praca",
            args=(
                ContentType.objects.get(app_label="bpp", model="wydawnictwo_ciagle").pk,
                wydawnictwo_ciagle.pk,
            ),
        ),
        follow=True,
    )
    val = nastepna_komorka_po_strona_www(res.content)
    assert val == "Brak danych"

    wydawnictwo_ciagle.www = "platny"
    wydawnictwo_ciagle.public_www = ""
    wydawnictwo_ciagle.save()

    res = client.get(
        reverse(
            "bpp:browse_praca",
            args=(
                ContentType.objects.get(app_label="bpp", model="wydawnictwo_ciagle").pk,
                wydawnictwo_ciagle.pk,
            ),
        ),
        follow=True,
    )
    val = nastepna_komorka_po_strona_www(res.content)
    assert val == "platny"

    wydawnictwo_ciagle.www = ""
    wydawnictwo_ciagle.public_www = "darmowy"
    wydawnictwo_ciagle.save()
    res = client.get(
        reverse(
            "bpp:browse_praca",
            args=(
                ContentType.objects.get(app_label="bpp", model="wydawnictwo_ciagle").pk,
                wydawnictwo_ciagle.pk,
            ),
        ),
        follow=True,
    )
    val = nastepna_komorka_po_strona_www(res.content)
    assert val == "darmowy"

    wydawnictwo_ciagle.www = "jezeli sa oba ma byc darmowy"
    wydawnictwo_ciagle.public_www = "darmowy"
    wydawnictwo_ciagle.save()
    res = client.get(
        reverse(
            "bpp:browse_praca",
            args=(
                ContentType.objects.get(app_label="bpp", model="wydawnictwo_ciagle").pk,
                wydawnictwo_ciagle.pk,
            ),
        ),
        follow=True,
    )
    val = nastepna_komorka_po_strona_www(res.content)
    assert val == "darmowy"


@pytest.mark.django_db
def test_artykuly(uczelnia, client):
    res = client.get(reverse("bpp:browse_uczelnia", args=(uczelnia.slug,)))
    assert res.status_code == 200

    TYTUL = "Tytul testowego artykulu"

    a = Article.objects.create(
        title=TYTUL, article_body="456", status=Article.STATUS.draft, slug="1"
    )

    res = client.get(reverse("bpp:browse_uczelnia", args=(uczelnia.slug,)))
    assert TYTUL.encode("utf-8") not in res.content

    a.status = Article.STATUS.published
    a.save()

    res = client.get(reverse("bpp:browse_uczelnia", args=(uczelnia.slug,)))
    assert TYTUL.encode("utf-8") in res.content


@pytest.mark.django_db
def test_artykul_ze_skrotem(uczelnia, client):
    a = Article.objects.create(
        title="123",
        article_body="456\n<!-- tutaj -->\nTego ma nie byc",
        status=Article.STATUS.published,
        slug="1",
    )

    res = client.get(reverse("bpp:browse_uczelnia", args=(uczelnia.slug,)))
    assert b"Tego ma nie byc" not in res.content
    assert "więcej" in res.rendered_content

    res = client.get(reverse("bpp:browse_artykul", args=(uczelnia.slug, a.slug)))
    assert b"Tego ma nie byc" in res.content


@pytest.mark.django_db
def test_jednostka_nie_wyswietlaj_autorow_gdy_wielu(client, jednostka):
    for n in range(102):
        jednostka.dodaj_autora(mommy.make(Autor))

    res = client.get(reverse("bpp:browse_jednostka", args=(jednostka.slug,)))
    assert "... napisane przez" not in res.rendered_content


@pytest.fixture
def test_browse_autor():
    Typ_Odpowiedzialnosci.objects.get_or_create(nazwa="autor", skrot="aut.")

    autor = mommy.make(Autor)
    jednostka = mommy.make(Jednostka, skupia_pracownikow=True)
    wc = mommy.make(Wydawnictwo_Ciagle, liczba_cytowan=200)
    wc.dodaj_autora(autor, jednostka, zapisany_jako="Jan K")

    j2 = mommy.make(Jednostka, skupia_pracownikow=False)
    wc2 = mommy.make(Wydawnictwo_Ciagle, liczba_cytowan=300)
    wc2.dodaj_autora(autor, j2, zapisany_jako="Jan K2", afiliuje=False)

    return autor


def test_browse_autor_dwa_doktoraty(typy_odpowiedzialnosci, autor_jan_kowalski, client):
    tytuly_prac = ["Praca 1", "Praca 2"]
    for praca in tytuly_prac:
        mommy.make(Praca_Doktorska, tytul_oryginalny=praca, autor=autor_jan_kowalski)

    res = client.get(
        reverse(
            "bpp:browse_autor",
            kwargs=dict(
                slug=autor_jan_kowalski.slug,
            ),
        )
    )

    for praca in tytuly_prac:
        assert praca in res.content.decode("utf-8")


@pytest.mark.django_db
def test_browse_autor_podstrona_liczba_cytowan_nigdy(
    client, uczelnia, test_browse_autor
):
    uczelnia.pokazuj_liczbe_cytowan_na_stronie_autora = (
        OpcjaWyswietlaniaField.POKAZUJ_NIGDY
    )
    uczelnia.save()

    res = client.get(reverse("bpp:browse_autor", args=(test_browse_autor.slug,)))
    assert "Liczba cytowań" not in res.rendered_content


@pytest.mark.django_db
def test_browse_autor_podstrona_liczba_cytowan_zawsze(
    client, uczelnia, test_browse_autor
):
    uczelnia.pokazuj_liczbe_cytowan_na_stronie_autora = (
        OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE
    )
    uczelnia.save()

    res = client.get(reverse("bpp:browse_autor", args=(test_browse_autor.slug,)))

    content = normalize_html(res.rendered_content)
    assert "Liczba cytowań" in content
    assert "Liczba cytowań: </strong>500" in content
    assert "Liczba cytowań z jednostek afiliowanych: </strong>200" in content


@pytest.mark.django_db
def test_browse_autor_podstrona_liczba_cytowan_zalogowani(
    client, uczelnia, test_browse_autor, normal_django_user
):
    uczelnia.pokazuj_liczbe_cytowan_na_stronie_autora = (
        OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM
    )
    uczelnia.save()

    res = client.get(reverse("bpp:browse_autor", args=(test_browse_autor.slug,)))
    assert "Liczba cytowań" not in res.rendered_content

    client.login(
        username=NORMAL_DJANGO_USER_LOGIN, password=NORMAL_DJANGO_USER_PASSWORD
    )
    res = client.get(reverse("bpp:browse_autor", args=(test_browse_autor.slug,)))
    assert "Liczba cytowań" in res.rendered_content


@pytest.mark.django_db
def test_browse_snip_visible(client, uczelnia, wydawnictwo_ciagle):
    wydawnictwo_ciagle.punktacja_snip = 50
    wydawnictwo_ciagle.save()

    uczelnia.pokazuj_punktacja_snip = True
    uczelnia.save()

    res = client.get(
        reverse(
            "bpp:browse_praca",
            args=(
                ContentType.objects.get(app_label="bpp", model="wydawnictwo_ciagle").pk,
                wydawnictwo_ciagle.pk,
            ),
        ),
        follow=True,
    )

    assert b"SNIP" in res.content


@pytest.mark.django_db
def test_browse_snip_invisible(client, uczelnia, wydawnictwo_ciagle):
    wydawnictwo_ciagle.punktacja_snip = 50
    wydawnictwo_ciagle.save()

    uczelnia.pokazuj_punktacja_snip = False
    uczelnia.save()

    res = client.get(
        reverse(
            "bpp:browse_praca",
            args=(
                ContentType.objects.get(app_label="bpp", model="wydawnictwo_ciagle").pk,
                wydawnictwo_ciagle.pk,
            ),
        ),
        follow=True,
    )

    assert b"SNIP" not in res.content


@pytest.mark.django_Db
def test_browse_praca_wydawnictwa_powiazane(wydawnictwo_zwarte, client, denorms):
    # Testuj, czy rozdziały pokazują się w wydawnictwach powiązanych
    mommy.make(
        Wydawnictwo_Zwarte,
        wydawnictwo_nadrzedne=wydawnictwo_zwarte,
        tytul_oryginalny="Roz 1",
        strony="asdoifj 55-34 oaijsdfo",
    )
    mommy.make(
        Wydawnictwo_Zwarte,
        wydawnictwo_nadrzedne=wydawnictwo_zwarte,
        tytul_oryginalny="Roz 2",
        strony="IXIXI 22-50",
    )

    denorms.flush()

    wydawnictwo_zwarte.refresh_from_db()

    url = reverse("bpp:browse_praca_by_slug", args=(wydawnictwo_zwarte.slug,))
    res = client.get(url)

    assert b"Rekordy powi" in res.content
    x1 = res.content.find(b"Roz 1")
    x2 = res.content.find(b"Roz 2")

    # Sortujemy po polu "strony", jeden ma byc pozniej, drugi wczesniej:
    assert x2 < x1


@pytest.mark.django_db
def test_praca_tabela_no_pmc_id(wydawnictwo_zwarte, client):
    wydawnictwo_zwarte.pmc_id = None
    wydawnictwo_zwarte.save()

    res = client.get(
        reverse(
            "bpp:browse_praca",
            args=(
                ContentType.objects.get_for_model(wydawnictwo_zwarte).pk,
                wydawnictwo_zwarte.pk,
            ),
        )
    )

    assert b"https://www.ncbi.nlm.nih.gov/pmc/" not in res.content


@pytest.mark.django_db
def test_praca_tabela_pmc_id(wydawnictwo_zwarte, client):
    wydawnictwo_zwarte.pmc_id = "123"
    wydawnictwo_zwarte.save()

    res = client.get(
        reverse(
            "bpp:browse_praca",
            args=(
                ContentType.objects.get_for_model(wydawnictwo_zwarte).pk,
                wydawnictwo_zwarte.pk,
            ),
        ),
        follow=True,
    )

    assert b"https://www.ncbi.nlm.nih.gov/pmc/" in res.content


def test_PracaView_ukrywanie_statusy_anonim(
    client, uczelnia, przed_korekta, wydawnictwo_zwarte_przed_korekta
):
    url = reverse(
        "bpp:browse_praca",
        args=(
            ContentType.objects.get_for_model(wydawnictwo_zwarte_przed_korekta).pk,
            wydawnictwo_zwarte_przed_korekta.pk,
        ),
    )

    res = client.get(url, follow=True)
    assert res.status_code == 200

    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)

    res = client.get(url, follow=True)
    assert res.status_code == 403


def test_PracaView_ukrywanie_statusy_admin(
    admin_client, uczelnia, przed_korekta, wydawnictwo_zwarte_przed_korekta
):
    url = reverse(
        "bpp:browse_praca",
        args=(
            ContentType.objects.get_for_model(wydawnictwo_zwarte_przed_korekta).pk,
            wydawnictwo_zwarte_przed_korekta.pk,
        ),
    )

    res = admin_client.get(url, follow=True)
    assert res.status_code == 200

    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)

    res = admin_client.get(url, follow=True)
    assert res.status_code == 200


@pytest.mark.django_db
def test_AutorView_funkcja_za_nazwiskiem(app):
    autor = mommy.make(Autor, nazwisko="Foo", imiona="Bar")
    jednostka = mommy.make(Jednostka, nazwa="Jednostka")
    funkcja = Funkcja_Autora.objects.create(
        nazwa="profesor uczelni", skrot="prof. ucz."
    )
    aj = Autor_Jednostka.objects.create(
        autor=autor, jednostka=jednostka, funkcja=funkcja
    )

    url = reverse("bpp:browse_autor", args=(autor.slug,))

    page = app.get(url)
    assert page.status_code == 200
    res = normalize_html(str(page.content, "utf-8"))
    assert res.find("<h1>Foo Bar </h1>") >= 0

    aj.rozpoczal_prace = date(2020, 1, 1)
    aj.save()

    page = app.get(url)
    res = normalize_html(str(page.content, "utf-8"))
    assert res.find("<h1>Foo Bar </h1>") >= 0

    funkcja.pokazuj_za_nazwiskiem = True
    funkcja.save()

    page = app.get(url)
    res = normalize_html(str(page.content, "utf-8"))
    assert res.find("<h1>Foo Bar, profesor uczelni </h1>") >= 0


def test_PracaViewBySlug_get_object(wydawnictwo_zwarte, denorms):
    denorms.rebuildall("Wydawnictwo_Zwarte")
    wydawnictwo_zwarte.refresh_from_db()
    r = Rekord.objects.get_for_model(wydawnictwo_zwarte)
    o = PracaViewBySlug(kwargs=dict(slug=wydawnictwo_zwarte.slug)).get_object()
    assert o == r

    o = PracaViewBySlug(
        kwargs=dict(
            slug=f"stary-slug-"
            f"{ContentType.objects.get_for_model(wydawnictwo_zwarte).pk}-{wydawnictwo_zwarte.pk}"
        )
    ).get_object()
    assert o == r


def test_PracaViewMixin_redirect(wydawnictwo_zwarte, rf, admin_user, denorms):
    denorms.rebuildall("Wydawnictwo_Zwarte")
    req = rf.get("/")
    req.user = admin_user
    res = PracaViewBySlug(
        kwargs=dict(
            slug=f"zlys-lug-{ContentType.objects.get_for_model(wydawnictwo_zwarte).pk}-{wydawnictwo_zwarte.pk}"
        )
    ).get(req)
    assert res.status_code == 302
    assert res.url.find("/bpp/rekord/Wydawnictwo-Zwarte") == 0


def test_autor_ukrywanie_nazwisk(autor_jan_nowak, client, admin_client):
    NAZWISKO = "NazwiskoAutora"
    autor_jan_nowak.poprzednie_nazwiska = NAZWISKO
    assert NAZWISKO in str(autor_jan_nowak)

    autor_jan_nowak.pokazuj_poprzednie_nazwiska = False
    autor_jan_nowak.save()

    assert NAZWISKO not in str(autor_jan_nowak)

    url = reverse("bpp:browse_autor", args=(autor_jan_nowak.slug,))

    page = admin_client.get(url)
    assert NAZWISKO in normalize_html(page.rendered_content)

    page = client.get(url)
    assert NAZWISKO not in normalize_html(page.rendered_content)


def test_browse_jednostka_nadrzedna(jednostka, jednostka_podrzedna, client):
    url = reverse("bpp:browse_jednostka", args=(jednostka.slug,))
    page = client.get(url)
    assert "Jest nadrzędną jednostką dla" in normalize_html(page.rendered_content)

    url = reverse("bpp:browse_jednostka", args=(jednostka_podrzedna.slug,))
    page = client.get(url)
    assert "Wchodzi w skład" in normalize_html(page.rendered_content)


def test_browse_jednostka_sortowanie(jednostka, jednostka_podrzedna, uczelnia, client):

    jednostka.nazwa = "Z jednostka"
    jednostka.save()

    jednostka_podrzedna.nazwa = "A jednostka"
    jednostka_podrzedna.save()

    uczelnia.sortuj_jednostki_alfabetycznie = True
    uczelnia.save()

    url = reverse("bpp:browse_jednostki")
    page = client.get(url)
    idx1 = page.rendered_content.find("A jednostka")
    idx2 = page.rendered_content.find("Z jednostka")

    assert idx1 < idx2

    uczelnia.sortuj_jednostki_alfabetycznie = False
    uczelnia.save()
    page = client.get(url)

    idx1 = page.rendered_content.find("A jednostka")
    idx2 = page.rendered_content.find("Z jednostka")
    assert idx1 > idx2


def test_browse_jednostka_nadrzedna_tekst(jednostka_podrzedna, jednostka, client):
    url = reverse("bpp:browse_jednostka", args=(jednostka.slug,))
    res = client.get(url)
    assert "Jest nadrzędną jednostką dla" in normalize_html(res.rendered_content)

    url = reverse("bpp:browse_jednostka", args=(jednostka_podrzedna.slug,))
    res = client.get(url)
    assert "Jest nadrzędną jednostką dla" not in normalize_html(res.rendered_content)
