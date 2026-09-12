"""Testy jednostkowe ``_dozwolone_hosty()`` (spec §6.1, recenzja Tasku 7).

Funkcja tłumaczy ``ALLOWED_HOSTS`` Django na allowlistę hostów, którą
rozumie ``TransportSecuritySettings`` SDK MCP — semantyka OBU list jest
inna (SDK dopasowuje dokładnie albo wzorcem ``host:*``; Django rozumie
``*`` i wiodącą ``.domenę``), więc błąd tutaj otwiera albo zamyka DNS
rebinding protection na całej ``/mcp``.

**Zakres odpowiedzialności — świadomie wąski.** Ta lista NIE jest kontrolą
wielotenantową i nie ma nią być: nie da się jej policzyć z bazy, bo biegnie
przy imporcie ``django_bpp.asgi``. Tożsamość uczelni rozstrzyga per żądanie
``mcp_server.uczelnia`` (testy: ``test_bramka_uczelni.py``) i to tam jest
fail-closed. Ostatni test w tym pliku pilnuje, żeby ten podział nie został
przez pomyłkę „naprawiony” tutaj — bo naprawa tutaj byłaby pozorna.
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


def test_hosty_infrastrukturalne_przechodza_ta_warstwe(settings):
    """Dokumentacja podziału odpowiedzialności, nie akceptacja dziury.

    Produkcyjne ``ALLOWED_HOSTS`` zawiera ``127.0.0.1``, ``appserver``
    i ``appserver:8000`` (``settings/production.py`` — potrzebne m.in. sondzie
    Dockera). Ta funkcja je przepuszcza i tak ma zostać: ochrona przed DNS
    rebindingiem to nie to samo, co rozstrzyganie uczelni.

    Żądanie z takim hostem jest odrzucane 421-ką dopiero PER ŻĄDANIE, przez
    ``mcp_server.uczelnia`` — bo dopiero tam wolno zapytać bazę, czy host ma
    swój ``Site``. Gdyby ktoś kiedyś zawęził tę listę „dla bezpieczeństwa”,
    dostałby zawężenie liczone z konfiguracji, a nie z danych — czyli poczucie
    bezpieczeństwa bez samego bezpieczeństwa.
    """
    settings.ALLOWED_HOSTS = ["bpp.przyklad.test", "appserver", "127.0.0.1"]
    hosty = _dozwolone_hosty()
    assert "appserver" in hosty
    assert "127.0.0.1" in hosty
