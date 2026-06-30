"""Testy metadanych SEO na stronie opisu publikacji.

Tagi cytowań (Highwire/Google Scholar, Dublin Core, PRISM) MUSZĄ trafić do
sekcji <head> dokumentu — parsery Google Scholar i menedżery bibliografii
czytają wyłącznie head, ignorując <meta> w body. Dodatkowo strona opisu
powinna mieć link kanoniczny, opis (meta description) i tagi Open Graph.
"""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Jednostka
from bpp.models.cache import Rekord
from bpp.models.system import Charakter_Formalny, Typ_Odpowiedzialnosci
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor
from bpp.tests.util import any_ciagle
from bpp.util import rebuild_contenttypes


@pytest.fixture
def rekord_publikacji(db, transactional_db):
    rebuild_contenttypes()

    aut, _ = Typ_Odpowiedzialnosci.objects.get_or_create(
        skrot="aut.", defaults={"nazwa": "autor"}
    )
    ch, _ = Charakter_Formalny.objects.get_or_create(
        skrot="AC",
        defaults={"nazwa": "Artykuł w czasopiśmie", "nazwa_w_primo": "Artykuł"},
    )

    c = any_ciagle(
        tytul_oryginalny="Badanie wpływu czegoś na coś",
        charakter_formalny=ch,
        doi="10.1234/przykladowy.doi",
        rok=2024,
    )
    a = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    j = baker.make(Jednostka)
    Wydawnictwo_Ciagle_Autor.objects.create(
        rekord=c, autor=a, jednostka=j, typ_odpowiedzialnosci=aut
    )

    Rekord.objects.full_refresh()
    return Rekord.objects.get(tytul_oryginalny="Badanie wpływu czegoś na coś")


def _head(response):
    """Zwróć fragment <head> odpowiedzi (wszystko przed <body)."""
    html = response.content.decode("utf-8")
    return html.split("<body", 1)[0]


@pytest.mark.django_db(transaction=True)
def test_citation_tags_w_head(client, rekord_publikacji):
    """Tagi citation_* Google Scholar muszą być w <head>, nie w <body>."""
    res = client.get(rekord_publikacji.get_absolute_url(), follow=True)
    assert res.status_code == 200
    head = _head(res)
    assert 'name="citation_title"' in head
    assert 'name="citation_author"' in head
    assert 'name="citation_doi"' in head


@pytest.mark.django_db(transaction=True)
def test_dublin_core_w_head(client, rekord_publikacji):
    res = client.get(rekord_publikacji.get_absolute_url(), follow=True)
    head = _head(res)
    assert 'name="DC.title"' in head


@pytest.mark.django_db(transaction=True)
def test_json_ld_obecny(client, rekord_publikacji):
    res = client.get(rekord_publikacji.get_absolute_url(), follow=True)
    html = res.content.decode("utf-8")
    assert 'application/ld+json' in html
    assert '"@type": "ScholarlyArticle"' in html


@pytest.mark.django_db(transaction=True)
def test_link_kanoniczny(client, rekord_publikacji):
    res = client.get(rekord_publikacji.get_absolute_url(), follow=True)
    head = _head(res)
    assert 'rel="canonical"' in head


@pytest.mark.django_db(transaction=True)
def test_meta_description(client, rekord_publikacji):
    res = client.get(rekord_publikacji.get_absolute_url(), follow=True)
    head = _head(res)
    assert 'name="description"' in head


@pytest.mark.django_db(transaction=True)
def test_open_graph(client, rekord_publikacji):
    res = client.get(rekord_publikacji.get_absolute_url(), follow=True)
    head = _head(res)
    assert 'property="og:title"' in head
    assert 'property="og:type"' in head


@pytest.mark.django_db
def test_robots_txt_wskazuje_sitemap(client):
    """robots.txt musi ogłaszać host-zależny adres sitemapy."""
    res = client.get(reverse("robots_txt"))
    assert res.status_code == 200
    body = res.content.decode("utf-8")
    assert "Sitemap:" in body
    assert "/sitemap.xml" in body
    # Lista Disallow ze statycznego pliku nadal obecna.
    assert "Disallow:" in body
