"""Nagłówek Content-Security-Policy (bez zewnętrznych zależności).

Domyślnie polityka jest wysyłana jako ``Content-Security-Policy-Report-Only``
— przeglądarka zgłasza naruszenia (konsola, opcjonalnie ``report-uri``), ale
niczego nie blokuje. Przejście na tryb wymuszający opisuje
``docs/administrator/zaawansowane.md``.

Ustawienia (czytane przy każdym żądaniu, z env przez ``settings/base.py``):

- ``BPP_CSP_ENABLED`` — czy w ogóle wysyłać nagłówek,
- ``BPP_CSP_REPORT_ONLY`` — ``True``: Report-Only, ``False``: wymuszanie,
- ``BPP_CSP_POLICY`` — własna polityka (pusta = :data:`DOMYSLNA_POLITYKA`),
- ``BPP_CSP_REPORT_URI`` — opcjonalny adres zbierania raportów.
"""

from django.conf import settings

#: Umiarkowana polityka startowa. Szablony ładują skrypty/style z własnego
#: originu; z zewnątrz tylko: Google Analytics (opcjonalny), widget
#: dostępności UserWay, widget wsparcia Freshworks/Freshdesk i front-endowy
#: Rollbar (wysyłka raportów). Szablony mają dużo skryptów i styli inline,
#: a htmx/plotly korzystają z ewaluacji kodu — stąd na razie
#: ``'unsafe-inline'`` i ``'unsafe-eval'``.
DOMYSLNA_POLITYKA = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
        "https://www.googletagmanager.com https://*.userway.org "
        "https://*.freshworks.com https://*.freshdesk.com",
        "style-src 'self' 'unsafe-inline' https://*.userway.org "
        "https://*.freshworks.com https://*.freshdesk.com",
        "img-src 'self' data: blob: https:",
        "font-src 'self' data: https://*.userway.org https://*.freshworks.com",
        "connect-src 'self' https://api.rollbar.com "
        "https://*.google-analytics.com https://*.analytics.google.com "
        "https://www.googletagmanager.com https://*.userway.org "
        "https://*.freshworks.com https://*.freshdesk.com",
        "frame-src 'self' https://*.userway.org https://*.freshworks.com "
        "https://*.freshdesk.com",
        "worker-src 'self' blob:",
        "frame-ancestors 'self'",
        "object-src 'none'",
        "base-uri 'self'",
    ]
)

NAGLOWEK_WYMUSZAJACY = "Content-Security-Policy"
NAGLOWEK_REPORT_ONLY = "Content-Security-Policy-Report-Only"


def zbuduj_polityke():
    polityka = getattr(settings, "BPP_CSP_POLICY", "") or DOMYSLNA_POLITYKA
    report_uri = getattr(settings, "BPP_CSP_REPORT_URI", "")
    if report_uri:
        polityka = f"{polityka}; report-uri {report_uri}"
    return polityka


class ContentSecurityPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not getattr(settings, "BPP_CSP_ENABLED", False):
            return response
        if getattr(settings, "BPP_CSP_REPORT_ONLY", True):
            naglowek = NAGLOWEK_REPORT_ONLY
        else:
            naglowek = NAGLOWEK_WYMUSZAJACY
        # Widok może ustawić własną politykę — nie nadpisujemy jej.
        if NAGLOWEK_WYMUSZAJACY in response or NAGLOWEK_REPORT_ONLY in response:
            return response
        response[naglowek] = zbuduj_polityke()
        return response
