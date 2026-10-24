"""Kafle identyfikatorów na podstronie autora.

- klik w kafel kopiuje wartość (przycisk ``data-kopiuj``), klik w link
  przenosi na stronę docelową;
- PBN: jeden kafel „Profil w PBN” zamiast „PBN UID” + „Naukowiec z POL-on”
  (prowadziły do tej samej strony), bez surowego UID w treści;
- stary numeryczny PBN ID (legacy) nie jest pokazywany.
"""

import pytest
from model_bakery import baker

from bpp.models import Autor

pytestmark = pytest.mark.django_db


def _tresc(client, autor):
    return client.get(autor.get_absolute_url()).content.decode()


def test_orcid_link_i_kopiowanie(client):
    autor = baker.make(Autor, orcid="0000-0002-0153-4624")
    tresc = _tresc(client, autor)
    assert 'href="https://orcid.org/0000-0002-0153-4624"' in tresc
    assert 'data-kopiuj="0000-0002-0153-4624"' in tresc


def test_bpp_id_do_skopiowania(client):
    autor = baker.make(Autor)
    assert f'data-kopiuj="{autor.pk}"' in _tresc(client, autor)


def test_jeden_kafel_pbn_bez_surowego_uid(client, uczelnia):
    from pbn_api.models import OsobaZInstytucji, Scientist

    # link do PBN składany z pbn_api_root uczelni
    uczelnia.pbn_api_root = "https://pbn.example.com"
    uczelnia.save()

    scientist = baker.make(Scientist)
    autor = baker.make(Autor, pbn_uid=scientist)
    baker.make(OsobaZInstytucji, personId=scientist)

    tresc = _tresc(client, autor)
    assert "Profil w PBN" in tresc
    assert "PBN UID" not in tresc
    assert "Naukowiec z POL-on" in tresc  # plakietka POL-on (title)
    assert tresc.count("Profil w PBN") == 1
    # UID wyłącznie w adresie linku, nie jako widoczny tekst
    assert f">{scientist.pk}<" not in tresc


def test_legacy_pbn_id_niewidoczny(client):
    autor = baker.make(Autor, pbn_id=123456)
    tresc = _tresc(client, autor)
    assert "PBN ID" not in tresc
    assert "123456" not in tresc


def test_system_kadrowy_ukryty_dla_anonima(client):
    autor = baker.make(Autor, system_kadrowy_id=987654)
    tresc = _tresc(client, autor)
    assert "System kadrowy" not in tresc
    assert "987654" not in tresc


def test_system_kadrowy_widoczny_dla_zalogowanego(client, normal_django_user):
    autor = baker.make(Autor, system_kadrowy_id=987654)
    client.force_login(normal_django_user)
    tresc = _tresc(client, autor)
    assert "System kadrowy" in tresc
    assert 'data-kopiuj="987654"' in tresc
