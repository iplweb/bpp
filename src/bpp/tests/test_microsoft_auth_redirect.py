"""Testy bezpieczeństwa MicrosoftAuthRedirectView (uwaga reviewera #2).

Podpisanie ``next`` dowodzi jedynie integralności wartości, NIE tego, że cel
jest bezpieczny. Bez walidacji hosta ``?next=https://evil.example/`` przechodzi
przez podpis i po zalogowaniu użytkownik jest przekierowywany na obcą domenę
(open redirect / phishing z zaufanej domeny BPP).
"""

from bpp.views.microsoft_auth_redirect import _safe_next


def test_safe_next_odrzuca_zewnetrzny_host(rf):
    request = rf.get("/microsoft-auth-redirect/")
    assert _safe_next(request, "https://evil.example/") is None


def test_safe_next_odrzuca_protocol_relative(rf):
    # //evil.example → protocol-relative; host = evil.example, nie nasz.
    request = rf.get("/microsoft-auth-redirect/")
    assert _safe_next(request, "//evil.example/phish") is None


def test_safe_next_akceptuje_wzgledny(rf):
    request = rf.get("/microsoft-auth-redirect/")
    assert _safe_next(request, "/o/authorize/?foo=bar") == "/o/authorize/?foo=bar"


def test_safe_next_akceptuje_wlasny_host(rf):
    request = rf.get("/microsoft-auth-redirect/", HTTP_HOST="testserver")
    assert _safe_next(request, "https://testserver/panel/") == "https://testserver/panel/"


def test_safe_next_pusty_zwraca_none(rf):
    request = rf.get("/microsoft-auth-redirect/")
    assert _safe_next(request, None) is None
    assert _safe_next(request, "") is None
