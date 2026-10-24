"""Playwright: komunikaty ``django.contrib.messages`` na froncie (szablon
Mustache ``#messageTemplate``) — zwykły tekst escapowany, ``format_html``
renderowany jako HTML."""

import pytest
from django.contrib.messages import constants
from django.contrib.messages.storage.base import Message
from django.contrib.messages.storage.cookie import CookieStorage
from django.test import RequestFactory
from django.utils.html import format_html
from model_bakery import baker
from playwright.sync_api import Page, expect

from bpp.models import Uczelnia


def _cookie(*teksty):
    storage = CookieStorage(RequestFactory().get("/"))
    return storage.cookie_name, storage._encode(
        [Message(constants.INFO, t) for t in teksty]
    )


@pytest.mark.django_db(transaction=True)
def test_komunikaty_front_escapowanie(channels_live_server, page: Page):
    baker.make(Uczelnia)

    name, value = _cookie(
        "Zwykly <b>x</b>",
        format_html('Bezpieczny <a href="{}">link</a>', "/foo/"),
    )
    page.context.add_cookies(
        [{"name": name, "value": value, "url": channels_live_server.url}]
    )
    page.goto(channels_live_server.url + "/")

    placeholder = page.locator("#messagesPlaceholder")
    expect(placeholder).to_contain_text("Zwykly <b>x</b>")
    expect(placeholder).to_contain_text("Bezpieczny link")
    assert placeholder.locator("b").count() == 0
    assert placeholder.locator('a[href="/foo/"]').count() == 1
