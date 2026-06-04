"""Testy ekstrakcji IP klienta zza nginx (X-Forwarded-For) dla django-axes.

Topologia deploymentu (bpp-deploy): nginx jest brzegiem (terminuje TLS, publikuje
80/443), a appserver:8000 / authserver:8001 NIE są wystawione na hosta — ruch
wchodzi wyłącznie przez nginx. nginx ustawia:

    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

gdzie ``$proxy_add_x_forwarded_for`` = ``<XFF przysłany przez klienta>, <remote_addr>``.
Dlatego PRAWDZIWE IP klienta to ZAWSZE OSTATNI (najbardziej prawy) wpis nagłówka —
ten, który dokleił nginx z ``$remote_addr`` (realny TCP-peer). Lewe wpisy są
sterowane przez klienta i można je sfałszować, więc nie wolno im ufać.

Bez ekstrakcji axes używałby ``REMOTE_ADDR`` = IP nginxa → komponent ``ip_address``
w lockoucie zapadłby się do jednej wartości dla wszystkich klientów.
"""

from django.test import RequestFactory

from django_bpp.client_ip import get_client_ip


def _req(xff=None, remote_addr="172.18.0.5"):
    rf = RequestFactory()
    extra = {"REMOTE_ADDR": remote_addr}
    if xff is not None:
        extra["HTTP_X_FORWARDED_FOR"] = xff
    return rf.get("/", **extra)


def test_returns_rightmost_xff_entry_ignoring_spoofed_left():
    # Klient próbuje podszyć się pod 9.9.9.9; nginx dokleja realne 203.0.113.7.
    req = _req(xff="9.9.9.9, 203.0.113.7", remote_addr="172.18.0.5")
    assert get_client_ip(req) == "203.0.113.7"


def test_single_xff_value():
    req = _req(xff="203.0.113.7", remote_addr="172.18.0.5")
    assert get_client_ip(req) == "203.0.113.7"


def test_falls_back_to_remote_addr_without_xff():
    req = _req(xff=None, remote_addr="198.51.100.4")
    assert get_client_ip(req) == "198.51.100.4"


def test_ignores_trailing_empty_and_whitespace_tokens():
    # Klient kończy swój XFF przecinkiem/spacjami; liczy się ostatni NIEPUSTY wpis
    # (i tak doklejony przez nginx jako $remote_addr).
    req = _req(xff="9.9.9.9 ,  , 203.0.113.7 ", remote_addr="172.18.0.5")
    assert get_client_ip(req) == "203.0.113.7"


def test_empty_xff_falls_back_to_remote_addr():
    req = _req(xff="   ", remote_addr="198.51.100.4")
    assert get_client_ip(req) == "198.51.100.4"
