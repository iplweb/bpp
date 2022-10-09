import json
import re

import pytest
from bs4 import BeautifulSoup

from django.contrib.contenttypes.models import ContentType

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

from model_bakery import baker
from multiseek.logic import EQUAL, EQUAL_FEMALE, EQUAL_NONE
from multiseek.views import MULTISEEK_SESSION_KEY

from miniblog.models import Article

from bpp.models import Rekord, Wydawnictwo_Zwarte
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


@pytest.mark.django_db
def test_browse_praca_wydawnictwa_powiazane(wydawnictwo_zwarte, client, denorms):
    # Testuj, czy rozdziały pokazują się w wydawnictwach powiązanych
    baker.make(
        Wydawnictwo_Zwarte,
        wydawnictwo_nadrzedne=wydawnictwo_zwarte,
        tytul_oryginalny="Roz 1",
        strony="asdoifj 55-34 oaijsdfo",
    )
    baker.make(
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


@pytest.mark.django_db
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
