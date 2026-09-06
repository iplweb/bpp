"""Testy jednostkowe ``_dozwolone_hosty()`` (spec §6.1, recenzja Tasku 7).

Funkcja tłumaczy ``ALLOWED_HOSTS`` Django na allowlistę hostów, którą
rozumie ``TransportSecuritySettings`` SDK MCP — semantyka OBU list jest
inna (SDK dopasowuje dokładnie albo wzorcem ``host:*``; Django rozumie
``*`` i wiodącą ``.domenę``), więc błąd tutaj otwiera albo zamyka DNS
rebinding protection na całej ``/mcp``.
"""

from mcp_server.aplikacja import _dozwolone_hosty


def test_gwiazdka_wylacza_sprawdzanie(settings):
    """SDK nie ma odpowiednika ``*`` — jedyny bezpieczny przekład to pusta
    lista, która w ``build_application`` wyłącza
    ``enable_dns_rebinding_protection`` (patrz wywołanie w ``aplikacja.py``)."""
    settings.ALLOWED_HOSTS = ["*"]
    assert _dozwolone_hosty() == []


def test_gwiazdka_wygrywa_niezaleznie_od_pozycji(settings):
    """``*`` gdziekolwiek na liście wyłącza sprawdzanie w całości — funkcja
    zwraca od razu, nawet gdy przed nim zdążyła dodać inne wpisy."""
    settings.ALLOWED_HOSTS = ["bpp.realny.test", "*"]
    assert _dozwolone_hosty() == []


def test_zwykly_host_dokladny_i_z_gwiazdka_portu(settings):
    """Zwykły wpis daje DWA warianty: dokładny (bez portu) i ``host:*``
    (z dowolnym portem) — SDK nie ma osobnej semantyki „dowolny port"."""
    settings.ALLOWED_HOSTS = ["bpp.przyklad.test"]
    hosty = _dozwolone_hosty()
    assert hosty == ["bpp.przyklad.test", "bpp.przyklad.test:*"]


def test_wiele_hostow_daje_wpisy_dla_kazdego(settings):
    settings.ALLOWED_HOSTS = ["bpp.a.test", "bpp.b.test"]
    hosty = _dozwolone_hosty()
    assert hosty == [
        "bpp.a.test",
        "bpp.a.test:*",
        "bpp.b.test",
        "bpp.b.test:*",
    ]


def test_wiodaca_kropka_django_bez_wiodacej_kropki_w_wyniku(settings):
    """Django-owe ``.domena`` (dopasowuje domenę i WSZYSTKIE subdomeny) SDK
    nie rozumie wprost — funkcja ucina kropkę, więc subdomeny same nie
    przejdą (SDK dopasowuje dokładnie), ale przynajmniej goła domena
    działa, zamiast nie dopasować NICZEGO (kropka na początku nie pasowałaby
    do żadnego realnego nagłówka ``Host``)."""
    settings.ALLOWED_HOSTS = [".przyklad.test"]
    hosty = _dozwolone_hosty()
    assert hosty == ["przyklad.test", "przyklad.test:*"]
    assert not any(h.startswith(".") for h in hosty)
