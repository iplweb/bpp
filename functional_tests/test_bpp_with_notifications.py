# -*- encoding: utf-8 -*-

from django.core.management import call_command

from conftest import NORMAL_DJANGO_USER_LOGIN


def test_bpp_notifications(preauth_browser):
    """Sprawdz, czy notyfikacje dochodza.
    Wymaga uruchomionego staging-server.
    """
    s = "test notyfikacji 123 456"
    assert preauth_browser.is_text_not_present(s)
    call_command('send_notification', NORMAL_DJANGO_USER_LOGIN, s)
    assert preauth_browser.is_text_present(s)


def test_preauth_browser(preauth_browser, live_server):
    """Sprawdz, czy pre-autoryzowany browser zwyklego uzytkownika
    funkcjonuje poprawnie."""
    preauth_browser.visit(live_server + '/admin/')
    assert preauth_browser.is_text_present(u"Login")


def test_preauth_browser_admin(preauth_browser_admin, live_server):
    """Sprawdz, czy pre-autoryzowany browser admina funkcjonuje poprawnie"""
    preauth_browser_admin.visit(live_server + '/admin/')
    assert preauth_browser_admin.is_text_present(u"Administracja stron")
