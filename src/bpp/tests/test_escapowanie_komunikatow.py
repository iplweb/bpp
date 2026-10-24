"""Komunikaty ``django.contrib.messages`` są escapowane przy renderowaniu,
chyba że są jawnie oznaczone jako bezpieczny HTML (``format_html``)."""

import pytest
from django.contrib.messages import constants
from django.contrib.messages.storage.base import Message
from django.contrib.messages.storage.cookie import CookieStorage
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.urls import reverse
from django.utils.html import escapejs, format_html

ZWYKLY = "Komunikat <b>x</b>"
ESCAPOWANY = "Komunikat &lt;b&gt;x&lt;/b&gt;"


def _ustaw_komunikat(client, tekst):
    """Komunikat przechodzi przez serializację cookie storage, tak jak
    między żądaniami (redirect po POST)."""
    storage = CookieStorage(RequestFactory().get("/"))
    client.cookies[storage.cookie_name] = storage._encode(
        [Message(constants.INFO, tekst)]
    )


@pytest.mark.django_db
def test_admin_komunikat_zwykly_string_escapowany(admin_client, uczelnia):
    _ustaw_komunikat(admin_client, ZWYKLY)
    res = admin_client.get(reverse("admin:index"))
    html = res.content.decode()
    assert ESCAPOWANY in html
    assert ZWYKLY not in html


@pytest.mark.django_db
def test_admin_komunikat_format_html_renderuje_html(admin_client, uczelnia):
    _ustaw_komunikat(
        admin_client,
        format_html('Zobacz <a href="{}">{}</a>', "/foo/", "<i>y</i>"),
    )
    res = admin_client.get(reverse("admin:index"))
    html = res.content.decode()
    assert 'Zobacz <a href="/foo/">&lt;i&gt;y&lt;/i&gt;</a>' in html


@pytest.mark.django_db
def test_front_komunikat_zwykly_string_escapowany(client, uczelnia):
    _ustaw_komunikat(client, ZWYKLY)
    res = client.get("/")
    html = res.content.decode()
    # Szablon Mustache nie wstawia surowego ``text``.
    assert "{{{ text }}}" not in html
    # Do szablonu trafia wersja zescapowana po stronie serwera.
    assert "html: '" + escapejs(ESCAPOWANY) + "'" in html
    assert "html: '" + escapejs(ZWYKLY) + "'" not in html


@pytest.mark.django_db
def test_front_komunikat_format_html_renderuje_html(client, uczelnia):
    tekst = format_html('Zobacz <a href="{}">tu</a>', "/foo/")
    _ustaw_komunikat(client, tekst)
    res = client.get("/")
    html = res.content.decode()
    assert "html: '" + escapejs(tekst) + "'" in html


def test_importer_step_done_komunikaty_escapowane():
    html = render_to_string(
        "importer_publikacji/partials/step_done.html",
        {
            "messages": [
                Message(constants.INFO, ZWYKLY),
                Message(constants.INFO, format_html("<em>{}</em>", "ok")),
            ],
            "error": "blad",
        },
    )
    assert ESCAPOWANY in html
    assert ZWYKLY not in html
    assert "<em>ok</em>" in html
