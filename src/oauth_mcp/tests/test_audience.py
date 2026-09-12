"""Walidator audience RFC 8707 zawężający po ORIGINIE, nie po prefiksie ścieżki.

Uzasadnienie wyboru (i pomiar, który go wymusił) siedzi w docstringu
``oauth_mcp.audience``. Tu pilnujemy KONTRAKTU: co ma przejść, a co nie.
"""

import pytest

from oauth_mcp.audience import waliduj_audience_po_originie

ZASOB = "https://bpp.example.test/mcp"


@pytest.mark.parametrize(
    "adres",
    [
        "https://bpp.example.test/mcp",
        "https://bpp.example.test/mcp/auth",
        # SEDNO poprawki: żądanie wewnętrzne serwera MCP do własnego /api/v1/.
        # Domyślny walidator DOT (prefiks ścieżki) odrzucał je 401-ką, przez co
        # zalogowana ścieżka /mcp/auth była martwa dla zgodnego klienta.
        "https://bpp.example.test/api/v1/autor/",
        # Port domyślny schematu jest normalizowany po obu stronach.
        "https://bpp.example.test:443/api/v1/rekord/",
    ],
)
def test_ten_sam_origin_przechodzi(adres):
    assert waliduj_audience_po_originie(adres, [ZASOB]) is True


@pytest.mark.parametrize(
    "adres",
    [
        # Inna uczelnia w instalacji wielouczelnianej — wspólna tabela tokenów,
        # więc BEZ tej kontroli token z hosta A działałby pod hostem B.
        "https://inna.example.test/api/v1/autor/",
        # Inny schemat to inny origin (RFC 6454) — nie schodzimy z https na http.
        "http://bpp.example.test/api/v1/autor/",
        # Inny port to inny origin.
        "https://bpp.example.test:8443/api/v1/autor/",
        # Authority confusion: prawdziwym hostem jest evil.example.
        "https://bpp.example.test@evil.example/api/v1/autor/",
        # Adres względny (bez originu) niczego nie dowodzi → fail closed.
        "/api/v1/autor/",
        "",
    ],
)
def test_obcy_albo_niepoprawny_origin_odrzucony(adres):
    assert waliduj_audience_po_originie(adres, [ZASOB]) is False


def test_schemat_musi_sie_zgadzac_nawet_przy_takim_samym_porcie():
    """Audyt PR #804, punkt 3: przypadek ``http://…/autor/`` powyżej
    (``test_obcy_albo_niepoprawny_origin_odrzucony``) różni się od ``ZASOB``
    RÓWNOCZEŚNIE schematem i portem domyślnym (80 vs 443) — walidator
    zmutowany tak, żeby porównywał TYLKO ``(host, port)`` (pomijając
    schemat), i tak by go odrzucił, bo porty się różnią. Różnica portu
    maskuje więc różnicę schematu i test nie dowodzi tego, co deklaruje.

    Tu port jest JAWNY i RÓWNY po obu stronach (443), więc jedyną różnicą
    zostaje schemat — dokładnie to, co ``waliduj_audience_po_originie`` ma
    sprawdzać poprzez porównanie krotki ``[:3]`` (schemat, host, port), nie
    samego ``[1:3]``."""
    audiences = ["https://bpp.example.test:443/mcp"]
    assert (
        waliduj_audience_po_originie(
            "http://bpp.example.test:443/api/v1/autor/", audiences
        )
        is False
    )


def test_ten_sam_origin_z_jawnym_portem_nadal_przechodzi():
    """Kontrola pozytywna do testu wyżej — jawny, równy port po obu stronach
    NIE ma sam z siebie nic odrzucać, gdy schemat i host też się zgadzają."""
    audiences = ["https://bpp.example.test:443/mcp"]
    assert (
        waliduj_audience_po_originie(
            "https://bpp.example.test:443/api/v1/autor/", audiences
        )
        is True
    )


def test_pusta_lista_audience_znaczy_bez_ograniczen():
    """Kontrakt DOT: token bez ``resource`` jest nieograniczony (kompatybilność
    wstecz z tokenami sprzed RFC 8707)."""
    assert waliduj_audience_po_originie("https://gdziekolwiek.test/x", []) is True


def test_smieciowy_wpis_nie_uniewaznia_pozostalych():
    """Pojedynczy niepoprawny wpis w ``resource`` ma być pominięty, nie ma
    przesądzać o całości — dokładnie jak w walidatorze DOT (``continue``)."""
    audiences = ["urn:cos:tam", ZASOB]
    assert (
        waliduj_audience_po_originie(
            "https://bpp.example.test/api/v1/autor/", audiences
        )
        is True
    )


def test_same_smieciowe_wpisy_odrzucone():
    wynik = waliduj_audience_po_originie("https://bpp.example.test/mcp", ["nie-uri"])
    assert wynik is False
