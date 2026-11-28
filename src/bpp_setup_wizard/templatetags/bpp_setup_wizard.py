"""Pasek postępu kreatora pierwszego uruchomienia („Krok N z M").

Lista kroków zależy od ścieżki:

* ``demo`` — konto administratora → dane demonstracyjne → generowanie,
* ``wlasna`` (domyślna, także przed odpowiedzią o dane demo) — konto
  administratora → dane demonstracyjne → dane uczelni → integracja z PBN,
* ``bez_demo`` — w bazie jest już uczelnia (np. dane demo wygenerowane
  z konsoli przez ``bpp-ctl``), więc kreator pyta tylko o to, czego brakuje.
"""

from __future__ import annotations

from django import template

register = template.Library()

ETYKIETY = {
    "admin": "Konto administratora",
    "dane_demo": "Dane demonstracyjne",
    "generowanie": "Generowanie danych",
    "uczelnia": "Dane uczelni",
    "pbn": "Integracja z PBN",
}

SCIEZKI = {
    "demo": ["admin", "dane_demo", "generowanie"],
    "wlasna": ["admin", "dane_demo", "uczelnia", "pbn"],
}


def wykryj_sciezke() -> str | list[str]:
    from bpp.models import Uczelnia
    from bpp_setup_wizard.dane_demo import ostatnie_generowanie
    from bpp_setup_wizard.models import KreatorDanychDemo

    operacja = ostatnie_generowanie()
    if operacja is not None and (operacja.w_toku or operacja.finished_successfully):
        return "demo"
    if KreatorDanychDemo.objects.filter(
        pk=1, odpowiedz=KreatorDanychDemo.ODPOWIEDZ_NIE
    ).exists():
        return "wlasna"
    if operacja is None and Uczelnia.objects.exists():
        # Uczelnia powstała poza kreatorem — pytania o dane demo nie będzie.
        kroki = ["admin"]
        if Uczelnia.objects.filter(kreator_czeka_na_pbn=True).exists():
            kroki += ["uczelnia", "pbn"]
        return kroki
    return "wlasna"


@register.inclusion_tag("bpp_setup_wizard/_postep.html")
def postep_kreatora(aktualny: str, sciezka: str | None = None):
    """``{% postep_kreatora "uczelnia" %}`` — ``sciezka`` wymusza wariant
    (np. ``"demo"`` na ekranie wyboru motywu, zanim decyzja trafi do bazy)."""
    kroki = SCIEZKI[sciezka] if sciezka else wykryj_sciezke()
    if isinstance(kroki, str):
        kroki = SCIEZKI[kroki]
    if aktualny not in kroki:
        kroki = [*kroki, aktualny]
    numer = kroki.index(aktualny) + 1
    return {
        "numer": numer,
        "liczba_krokow": len(kroki),
        "kroki": [
            {
                "etykieta": ETYKIETY[k],
                "aktualny": i + 1 == numer,
                "zrobiony": i + 1 < numer,
            }
            for i, k in enumerate(kroki)
        ],
    }
