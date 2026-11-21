"""Freshdesk #456 — adres „Dostępna w sieci pod adresem" w nowej karcie.

Na stronie zgłoszenia publikacji w adminie link do pracy ma otwierać się
w nowej karcie (``target="_blank"``), żeby operator nie tracił oglądanego
zgłoszenia.
"""

import re

import pytest
from django.urls import reverse
from model_bakery import baker

from zglos_publikacje.models import Zgloszenie_Publikacji

ADRES = "https://example.com/papers/456"


def _change_html(admin_client, zgloszenie):
    response = admin_client.get(
        reverse(
            "admin:zglos_publikacje_zgloszenie_publikacji_change",
            args=[zgloszenie.pk],
        )
    )
    assert response.status_code == 200
    return response.content.decode()


@pytest.mark.django_db
def test_repro_fd456_strona_www_otwiera_sie_w_nowej_karcie(admin_client):
    zgloszenie = baker.make(
        Zgloszenie_Publikacji,
        tytul_oryginalny="Praca ze stroną WWW",
        strona_www=ADRES,
    )

    html = _change_html(admin_client, zgloszenie)

    assert "Dostępna w sieci pod adresem" in html
    linki = re.findall(rf'<a href="{re.escape(ADRES)}"[^>]*>', html)
    assert linki, "Brak linku do adresu pracy na stronie zgłoszenia"
    for link in linki:
        assert 'target="_blank"' in link
        assert 'rel="noopener noreferrer"' in link


@pytest.mark.django_db
def test_repro_fd456_brak_adresu_bez_linku(admin_client):
    zgloszenie = baker.make(
        Zgloszenie_Publikacji,
        tytul_oryginalny="Praca bez adresu",
        strona_www="",
    )

    html = _change_html(admin_client, zgloszenie)

    assert "Dostępna w sieci pod adresem" in html
    assert 'target="_blank" rel="noopener noreferrer"' not in html
