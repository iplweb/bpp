"""Wspólna konfiguracja axe-core dla bramki dostępności (WCAG faza 3).

Jedno miejsce z tagami i wstrzykiwaniem, żeby dało się je zmienić raz,
a nie w trzech testach — i żeby przegląd kodu widział każdą zmianę
konfiguracji bramki w jednym pliku.

`axe.min.js` bierzemy ze statyków, nie z `node_modules`: obraz CI
`test-runner` nie zawiera zależności Node, więc ścieżka przez
`node_modules` działa lokalnie i pada na CI. Plik kopiuje tam zadanie
`shell:copyAxe` z `Gruntfile.js`.
"""

import json
from pathlib import Path

SCIEZKA_AXE = (
    Path(__file__).resolve().parents[1] / "bpp" / "static" / "axe" / "axe.min.js"
)

# Zakres audytu: WCAG 2.2, poziomy A i AA. `wcag22a` zostaje celowo, mimo
# że dziś nie niesie regul — jako zabezpieczenie na wypadek dodania ich
# w przyszlych wersjach axe (ustalenie ze specyfikacji 2026-08-05).
TAGI = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22a", "wcag22aa"]


def skanuj(page):
    """Wstrzykuje axe i zwraca surowy wynik `axe.run()`."""
    if not SCIEZKA_AXE.exists():
        raise AssertionError(
            f"Brak {SCIEZKA_AXE}. Uruchom `make assets` — plik kopiuje "
            "zadanie shell:copyAxe z Gruntfile.js."
        )
    page.add_script_tag(path=str(SCIEZKA_AXE))
    return page.evaluate(
        "async () => await axe.run(document, {runOnly: {type: 'tag', "
        "values: " + json.dumps(TAGI) + "}})"
    )


def opisz_naruszenia(wynik):
    """Czytelny raport: reguła, waga, selektor i fragment HTML-a.

    Diagnoza ma nie wymagać powtarzania pomiaru — komunikat z CI musi
    wystarczyć, żeby wiedzieć, co poprawić.
    """
    linie = []
    for v in wynik["violations"]:
        linie.append(f"\n{v['id']} [{v['impact']}] — {len(v['nodes'])} elem.")
        for n in v["nodes"]:
            selektor = n["target"][0] if n["target"] else "?"
            html = " ".join(n["html"].split())[:120]
            linie.append(f"  sel:  {selektor}")
            linie.append(f"  html: {html}")
    return "\n".join(linie)


def opisz_niejednoznaczne(wynik):
    """Raport `incomplete` — reguł, których axe nie umiał rozstrzygnąć.

    Nie blokują bramki, ale muszą być widoczne: naruszenie potrafi
    zmigrować z `violations` do `incomplete` (np. po zmianie tła na
    półprzezroczyste) i cicho zniknąć z pola widzenia.
    """
    if not wynik.get("incomplete"):
        return "incomplete: brak"
    czesci = [f"{v['id']}({len(v['nodes'])})" for v in wynik["incomplete"]]
    return "incomplete: " + ", ".join(czesci)
