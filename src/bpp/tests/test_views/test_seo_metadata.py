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
def test_json_ld_poprawny_json_przy_groznych_znakach(client, db, transactional_db):
    """JSON-LD musi być poprawnym JSON-em nawet gdy dane mają " < & </script>.

    Regresja: autoescaping zamieniał cudzysłowy z `jsonify` na `&quot;`, a
    HTML5 nie dekoduje encji w <script> — JSON-LD był niepoprawny i Google
    go odrzucał. Filtr `jsonify` zwraca teraz mark_safe + escapuje <, >, &.
    """
    import json
    import re

    rebuild_contenttypes()
    aut, _ = Typ_Odpowiedzialnosci.objects.get_or_create(
        skrot="aut.", defaults={"nazwa": "autor"}
    )
    ch, _ = Charakter_Formalny.objects.get_or_create(
        skrot="AC",
        defaults={"nazwa": "Artykuł", "nazwa_w_primo": "Artykuł"},
    )
    c = any_ciagle(
        tytul_oryginalny='Tytuł z " cudzysłowem & <b>znacznikiem</b>',
        charakter_formalny=ch,
        rok=2024,
    )
    a = baker.make(Autor, nazwisko='O"Brien & <Co>', imiona="Jan")
    j = baker.make(Jednostka)
    Wydawnictwo_Ciagle_Autor.objects.create(
        rekord=c, autor=a, jednostka=j, typ_odpowiedzialnosci=aut
    )
    Rekord.objects.full_refresh()
    rekord = Rekord.objects.first()

    html = client.get(rekord.get_absolute_url(), follow=True).content.decode("utf-8")
    payload = re.search(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S
    ).group(1)

    parsed = json.loads(payload)  # rzuci, jeśli JSON-LD jest niepoprawny
    assert parsed["author"][0]["name"] == 'Jan O"Brien & <Co>'
    # Brak dosłownego "<" w payloadzie => nie da się wyłamać przez </script>.
    assert "<" not in payload


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


@pytest.mark.django_db
def test_robots_txt_sitemap_zalezna_od_hosta(client, settings):
    """Sitemap musi wskazywać host requestu, a odpowiedź mieć Vary: Host.

    Bez Vary: Host owijający cache_page zaserwowałby pierwszemu hostowi
    cache współdzielony z innymi domenami multi-hosted.
    """
    settings.ALLOWED_HOSTS = ["bpp.uczelnia-a.pl", "bpp.uczelnia-b.pl"]

    res_a = client.get(reverse("robots_txt"), HTTP_HOST="bpp.uczelnia-a.pl")
    res_b = client.get(reverse("robots_txt"), HTTP_HOST="bpp.uczelnia-b.pl")

    assert "Sitemap: http://bpp.uczelnia-a.pl/sitemap.xml" in res_a.content.decode()
    assert "Sitemap: http://bpp.uczelnia-b.pl/sitemap.xml" in res_b.content.decode()
    assert "Host" in res_a.get("Vary", "")
