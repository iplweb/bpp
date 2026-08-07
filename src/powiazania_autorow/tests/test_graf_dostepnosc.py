"""Dostępność grafu powiązań: nawigacja wskaźnikiem (2.5.7) i klawiaturą (2.1.1).

Graf stoi na Cytoscape.js i do tej pory dawał się przesuwać wyłącznie
przeciąganiem. Kryterium 2.5.7 wymaga alternatywy realizowanej pojedynczym
wskaźnikiem — stąd przyciski. Sam kontener zyskuje `tabindex`, żeby te same
funkcje dało się wywołać z klawiatury (2.1.1).
"""

from pathlib import Path

SZABLON = (
    Path(__file__).resolve().parents[1]
    / "templates"
    / "powiazania_autorow"
    / "graf.html"
)

PRZYCISKI = [
    "graf-nav-gora",
    "graf-nav-dol",
    "graf-nav-lewo",
    "graf-nav-prawo",
    "graf-nav-zoom-in",
    "graf-nav-zoom-out",
    "graf-nav-dopasuj",
]


def _tresc():
    return SZABLON.read_text(encoding="utf-8")


def test_wszystkie_przyciski_nawigacji_obecne():
    tresc = _tresc()
    for identyfikator in PRZYCISKI:
        assert f'id="{identyfikator}"' in tresc, f"brak przycisku {identyfikator}"


def test_kazdy_przycisk_ma_aria_label():
    # Sam glif strzałki nic nie mówi czytnikowi ekranu.
    tresc = _tresc()
    fragmenty = tresc.split("<button")
    nawigacyjne = [f for f in fragmenty if "graf-nav-" in f]

    assert len(nawigacyjne) == len(PRZYCISKI)
    for fragment in nawigacyjne:
        assert "aria-label=" in fragment


def test_przyciski_sa_typu_button():
    # Bez type="button" przycisk wewnątrz formularza wysyła go.
    tresc = _tresc()
    for fragment in tresc.split("<button")[1:]:
        if "graf-nav-" in fragment:
            assert 'type="button"' in fragment


def test_glify_ukryte_przed_czytnikiem():
    # Treść dla czytnika jest w aria-label; glif to dekoracja.
    tresc = _tresc()
    for fragment in tresc.split("<button")[1:]:
        if "graf-nav-" in fragment:
            assert 'aria-hidden="true"' in fragment
