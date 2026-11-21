"""FD#391 (część opcjonalna) — kafel „Wydziały” zamiast „Jednostki”.

Na stronie głównej uczelni kafel „Jednostki” w sekcji „Przeglądaj bazę
publikacji” był wpisany na sztywno. Uczelnia z wydziałami (UAFM) chce
zamiast niego kafla „Wydziały”, prowadzącego do indeksu wydziałów —
jednostek najwyższego poziomu (``parent=None``) TEJ uczelni.

Opcja ``Uczelnia.kafel_wydzialy_zamiast_jednostek`` (domyślnie wyłączona):
* wyłączona — kafel „Jednostki” jak dotąd (``/bpp/jednostki/``),
* włączona — kafel z nazwą wydziału w l.mn. (lemat ``WYDZIAL``) i linkiem
  do ``/bpp/wydzialy/``.
"""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Jednostka, Rzeczownik, Uczelnia
from bpp.views.browse import get_uczelnia_context_data

KAFEL_JEDNOSTKI = '<h4 class="uczelnia__tile-title">Jednostki</h4>'
KAFEL_JEDNOSTKI_LINK = '<a href="/bpp/jednostki/" class="browse-tile">'


def _kafel(tytul):
    return f'<h4 class="uczelnia__tile-title">{tytul}</h4>'


def _strona_glowna(client, uczelnia, **kw):
    get_uczelnia_context_data.invalidate()
    url = reverse("bpp:browse_uczelnia", args=(uczelnia.slug,))
    res = client.get(url, **kw)
    assert res.status_code == 200
    return res.content.decode("utf-8")


@pytest.mark.django_db
def test_fd391_domyslnie_kafel_jednostki(client, uczelnia):
    """Guard: bez włączonej opcji strona główna wygląda jak dotąd."""
    assert uczelnia.kafel_wydzialy_zamiast_jednostek is False

    content = _strona_glowna(client, uczelnia)

    assert KAFEL_JEDNOSTKI in content
    assert KAFEL_JEDNOSTKI_LINK in content
    assert reverse("bpp:browse_wydzialy") not in content


@pytest.mark.django_db
def test_fd391_opcja_wlaczona_kafel_wydzialy(client, uczelnia):
    uczelnia.kafel_wydzialy_zamiast_jednostek = True
    uczelnia.save()

    content = _strona_glowna(client, uczelnia)

    assert _kafel("Wydziały") in content
    assert "Przeglądaj wg wydziału" in content
    assert f'href="{reverse("bpp:browse_wydzialy")}"' in content
    assert KAFEL_JEDNOSTKI not in content
    assert KAFEL_JEDNOSTKI_LINK not in content


@pytest.mark.django_db
def test_fd391_kafel_uzywa_nazewnictwa_uczelni(client, uczelnia):
    """Nazwa kafla bierze się z nazewnictwa (Rzeczownik ``WYDZIAL``)."""
    Rzeczownik.objects.update_or_create(uid="WYDZIAL", defaults={"m": "instytut"})
    uczelnia.kafel_wydzialy_zamiast_jednostek = True
    uczelnia.save()

    content = _strona_glowna(client, uczelnia)

    assert _kafel("Instytuty") in content
    assert "Przeglądaj wg instytutu" in content


@pytest.mark.django_db
def test_fd391_indeks_wydzialow_tylko_jednostki_najwyzszego_poziomu(
    client, uczelnia
):
    wydzial = baker.make(
        Jednostka, uczelnia=uczelnia, parent=None, nazwa="Wydział Testowy"
    )
    baker.make(
        Jednostka, uczelnia=uczelnia, parent=wydzial, nazwa="Katedra Podrzędna"
    )
    baker.make(
        Jednostka,
        uczelnia=uczelnia,
        parent=None,
        widoczna=False,
        nazwa="Wydział Ukryty",
    )

    res = client.get(reverse("bpp:browse_wydzialy"))
    assert res.status_code == 200
    content = res.content.decode("utf-8")

    assert "Wydział Testowy" in content
    assert "Katedra Podrzędna" not in content
    assert "Wydział Ukryty" not in content
    assert "Indeks wydziałów" in content


@pytest.mark.django_db
def test_fd391_indeks_wydzialow_literka(client, uczelnia):
    baker.make(Jednostka, uczelnia=uczelnia, parent=None, nazwa="Wydział Alfa")
    baker.make(Jednostka, uczelnia=uczelnia, parent=None, nazwa="Kolegium Beta")

    res = client.get(reverse("bpp:browse_wydzialy_literka", args=("W",)))
    assert res.status_code == 200
    content = res.content.decode("utf-8")

    assert "Wydział Alfa" in content
    assert "Kolegium Beta" not in content
    # Okruszek i przyciski prowadzą do indeksu wydziałów, nie jednostek.
    assert f'href="{reverse("bpp:browse_wydzialy")}"' in content


@pytest.mark.django_db
def test_fd391_indeks_jednostek_bez_zmian(client, uczelnia):
    """Guard: indeks jednostek nadal pokazuje także jednostki podrzędne."""
    wydzial = baker.make(
        Jednostka, uczelnia=uczelnia, parent=None, nazwa="Wydział Testowy"
    )
    baker.make(
        Jednostka, uczelnia=uczelnia, parent=wydzial, nazwa="Katedra Podrzędna"
    )

    res = client.get(reverse("bpp:browse_jednostki"))
    content = res.content.decode("utf-8")

    assert "Wydział Testowy" in content
    assert "Katedra Podrzędna" in content
    assert "Indeks jednostek" in content
    assert f'href="{reverse("bpp:browse_wydzialy")}"' not in content


@pytest.mark.django_db
def test_fd391_multi_hosted(client, settings):
    """Multi-hosted: kafel zależy od opcji uczelni z hosta, a indeks
    wydziałów pokazuje wyłącznie wydziały tej uczelni."""
    settings.ALLOWED_HOSTS = ["*"]

    uczelnia_a = baker.make(Uczelnia, kafel_wydzialy_zamiast_jednostek=True)
    uczelnia_a.site.domain = "uczelnia-a.example.com"
    uczelnia_a.site.save()
    uczelnia_b = baker.make(Uczelnia, kafel_wydzialy_zamiast_jednostek=False)
    uczelnia_b.site.domain = "uczelnia-b.example.com"
    uczelnia_b.site.save()

    baker.make(Jednostka, uczelnia=uczelnia_a, parent=None, nazwa="Wydział A")
    baker.make(Jednostka, uczelnia=uczelnia_b, parent=None, nazwa="Wydział B")

    host_a = {"HTTP_HOST": "uczelnia-a.example.com"}
    host_b = {"HTTP_HOST": "uczelnia-b.example.com"}

    content_a = _strona_glowna(client, uczelnia_a, **host_a)
    assert _kafel("Wydziały") in content_a
    assert KAFEL_JEDNOSTKI not in content_a

    content_b = _strona_glowna(client, uczelnia_b, **host_b)
    assert KAFEL_JEDNOSTKI in content_b
    assert _kafel("Wydziały") not in content_b

    res = client.get(reverse("bpp:browse_wydzialy"), **host_a)
    content = res.content.decode("utf-8")
    assert "Wydział A" in content
    assert "Wydział B" not in content
