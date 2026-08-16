"""Repro: link "Otwórz w PBN" na stronie rekordu w trybie multi-homed.

Gdy w instalacji jest WIĘCEJ NIŻ JEDNA uczelnia, szablon strony rekordu
(``browse/praca_tabela_mono.html``) woła ``praca.link_do_pbn`` bez argumentu,
więc ``get_single_uczelnia_or_none()`` zwraca ``None``, metoda zwraca ``None``,
a Django renderuje to dosłownie jako napis ``None``:

    <button ... data-open-url="None" title="Otwórz w PBN">

Zamiast tego link ma wskazywać PBN uczelni z hosta requestu — analogicznie do
``link_do_pi`` (filtr z uczelnią z kontekstu) i do strony autora (FD#390).
"""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from model_bakery import baker

from bpp.models import Uczelnia, Wydawnictwo_Zwarte


@pytest.fixture
def dwie_uczelnie(db):
    """Multi-homed: dwie uczelnie → ``get_single_uczelnia_or_none() is None``."""
    uczelnia_a = baker.make(Uczelnia, pbn_api_root="https://pbn-a.example.com")
    uczelnia_a.site.domain = "uczelnia-a.example.com"
    uczelnia_a.site.save()

    baker.make(Uczelnia)  # druga → single == None (multi-homed)
    return uczelnia_a


@pytest.mark.django_db
def test_link_do_pbn_na_stronie_rekordu_uzywa_uczelni_z_hosta(
    client, settings, dwie_uczelnie
):
    settings.ALLOWED_HOSTS = ["*"]

    from pbn_api.models import Publication

    publication = baker.make(Publication)
    praca = baker.make(Wydawnictwo_Zwarte, pbn_uid=publication)

    url = reverse(
        "bpp:browse_praca",
        args=(
            ContentType.objects.get(app_label="bpp", model="wydawnictwo_zwarte").pk,
            praca.pk,
        ),
    )
    resp = client.get(url, HTTP_HOST="uczelnia-a.example.com", follow=True)
    assert resp.status_code == 200

    content = resp.content.decode("utf-8")

    oczekiwany = (
        f"https://pbn-a.example.com/core/#/publication/view/{publication.pk}/current"
    )
    assert oczekiwany in content, (
        "Link do PBN na stronie rekordu powinien używać pbn_api_root uczelni "
        "z hosta; zamiast tego degraduje do None (bug multi-homed)."
    )
    assert 'data-open-url="None"' not in content
    assert "data-open-url=None" not in content


@pytest.mark.django_db
def test_link_do_pbn_na_stronie_rekordu_single_install(client, settings):
    """Regresja: w instalacji z JEDNĄ uczelnią link nadal się renderuje."""
    settings.ALLOWED_HOSTS = ["*"]

    from pbn_api.models import Publication

    uczelnia = baker.make(Uczelnia, pbn_api_root="https://pbn.example.com")

    publication = baker.make(Publication)
    praca = baker.make(Wydawnictwo_Zwarte, pbn_uid=publication)

    url = reverse(
        "bpp:browse_praca",
        args=(
            ContentType.objects.get(app_label="bpp", model="wydawnictwo_zwarte").pk,
            praca.pk,
        ),
    )
    resp = client.get(url, HTTP_HOST=uczelnia.site.domain, follow=True)
    assert resp.status_code == 200

    content = resp.content.decode("utf-8")
    assert (
        f"https://pbn.example.com/core/#/publication/view/{publication.pk}/current"
        in content
    )
