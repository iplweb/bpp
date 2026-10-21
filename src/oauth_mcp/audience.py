"""Walidator audience (RFC 8707) dopasowany do tego, czym BPP naprawdę jest.

Kontekst — dlaczego domyślny walidator DOT tu nie działa
========================================================

Klient MCP zgodny ze specyfikacją autoryzacji (2025-06-18) **MUSI** wysłać
parametr ``resource`` (RFC 8707) w żądaniu autoryzacji i w żądaniu o token,
z kanonicznym adresem serwera MCP — u nas ``https://<host>/mcp``. Wartość NIE
pochodzi z naszego dokumentu PRM, tylko z adresu, pod który klient się łączy,
więc **usunięcie pola ``resource`` z PRM niczego by nie zmieniło**: token i tak
przyszedłby zawężony (zweryfikowane w kodzie ``oauthlib``: ``Request.__init__``
wciąga KAŻDY parametr query/body do ``_params``, więc DOT zapisuje ``resource``
w ``Grant`` i dalej w ``AccessToken``).

Domyślny walidator DOT (``validate_resource_as_url_prefix``) porównuje adres
żądania z audience PREFIKSEM ŚCIEŻKI. Tymczasem serwer MCP obsługuje wywołanie
narzędzia, wołając WŁASNE ``/api/v1/`` w procesie (``mcp_server.klient``) —
z tym samym bearerem. Adres tego żądania to ``https://<host>/api/v1/...``,
który nie zaczyna się od ``https://<host>/mcp``, więc DOT odrzucał go 401-ką.

Zmierzone na pełnym stosie (``mcp_server/tests/test_audience.py``): token
z ``resource=["http://<host>/mcp"]`` przechodził naszą bramkę ``/mcp``, po czym
KAŻDE wywołanie narzędzia kończyło się ``BppError: Błąd HTTP 401`` z
``/api/v1/``. Czyli: dla klienta zgodnego ze specyfikacją cała ścieżka
zalogowana była martwa, a jednocześnie audience nie było przez nas sprawdzane
nigdzie — deklarowaliśmy je w PRM i nie egzekwowaliśmy.

Co robimy zamiast tego
======================

Egzekwujemy audience na **poziomie originu**, a nie prefiksu ścieżki:

* ``/mcp`` i ``/api/v1/`` to JEDEN Resource Server — ta sama instancja BPP, ten
  sam zbiór danych, ten sam scope ``read``. Narzędzie MCP z definicji czyta
  ``/api/v1/``, więc token dopuszczony do ``/mcp`` z natury rzeczy sięga po te
  same dane. Granulacja per-ścieżka wewnątrz jednego originu nie chroni tu
  niczego, a łamie propagację tożsamości do żądania wewnętrznego.
* Tym, przed czym RFC 8707 realnie chroni, jest użycie tokenu u INNEGO Resource
  Servera — a w instalacji wielouczelnianej BPP „inny serwer" to inny host.
  Origin egzekwujemy więc nadal, i to jest zysk: token wydany pod hostem
  uczelni A zostaje odrzucony pod hostem uczelni B (wcześniej — przy domyślnym
  walidatorze — również, ale za cenę odrzucania go także pod hostem A).

Ograniczenie, którego ten walidator NIE usuwa: token wydany BEZ ``resource``
(np. założony ręcznie w adminie albo przez klienta, który RFC 8707 nie
implementuje) jest z definicji nieograniczony — ``AccessToken.allows_audience``
zwraca dla pustej listy ``True``, zanim jakikolwiek walidator zostanie
zawołany. Takiego tokenu nie da się związać z hostem bez zmiany semantyki DOT
dla całego projektu; jest to odnotowane w otwartych kwestiach specyfikacji.
"""

from __future__ import annotations

from oauth2_provider.oauth2_validators import _parse_and_validate_uri


def waliduj_audience_po_originie(request_uri: str, audiences: list[str]) -> bool:
    """Czy ``request_uri`` leży w tym samym originie, co któreś z ``audiences``?

    Podpis i kontrakt jak w ``oauth2_provider.oauth2_validators
    .validate_resource_as_url_prefix`` (to jest podmiana ustawienia
    ``RESOURCE_SERVER_TOKEN_RESOURCE_VALIDATOR``): pusta lista audience znaczy
    „bez ograniczeń", niepoprawny adres żądania znaczy odmowa.

    Parsowanie oddajemy funkcji DOT ``_parse_and_validate_uri`` — mimo
    podkreślenia w nazwie — zamiast pisać własne. To ona odrzuca adresy
    z ``userinfo`` (``https://host@evil.example/``) i z fragmentem, oraz
    normalizuje domyślny port schematu (``https://h`` == ``https://h:443``).
    Własna implementacja tych niuansów byłaby dokładnie tym miejscem, w którym
    powstają obejścia typu „authority confusion".
    """
    if not audiences:
        return True

    czesci_zadania = _parse_and_validate_uri(request_uri)
    if czesci_zadania is None:
        return False
    origin_zadania = czesci_zadania[:3]  # (schemat, host, port)

    for audience in audiences:
        czesci_audience = _parse_and_validate_uri(audience)
        if czesci_audience is None:
            # Pojedynczy śmieciowy wpis nie może przesądzać o całości —
            # dokładnie tak samo robi walidator DOT (``continue``).
            continue
        if czesci_audience[:3] == origin_zadania:
            return True

    return False
