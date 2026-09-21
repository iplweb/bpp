"""Strażnik: żaden szablon nie woła ``obiekt.link_do_pbn`` / ``obiekt.link_do_pi``.

Obie metody biorą ``uczelnia`` — w multi-hosted (>1 uczelnia) bez niej zwracają
``None``, a Django renderuje to dosłownie jako ``href="None"``. Szablon nie umie
podać argumentu metodzie, więc ``{{ praca.link_do_pbn }}`` jest ZAWSZE błędem.
Ten bug naprawiano punktowo kilka razy (strona rekordu, strona autora, admin),
za każdym razem zostawiając inne szablony — stąd test na WSZYSTKIE naraz.

Poprawnie:

    {% load prace %}
    {% link_do_pbn praca as pbn_url %}
    {% if pbn_url %}<a href="{{ pbn_url }}">PBN</a>{% endif %}

    {% with pi_url=praca|link_do_pi:uczelnia %}...{% endwith %}
"""

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]

# ``.link_do_pbn`` / ``.link_do_pi`` jako atrybut w wyrażeniu szablonu; NIE
# łapie tagu ``{% link_do_pbn x as y %}`` ani filtra ``x|link_do_pi:uczelnia``
# (tam przed nazwą nie ma kropki).
WZORZEC = re.compile(r"\.(link_do_pbn|link_do_pi)\b(?!_)")


def _szablony():
    for sciezka in SRC.rglob("templates/**/*"):
        if sciezka.suffix in (".html", ".txt", ".xml") and sciezka.is_file():
            yield sciezka


def test_szablony_nie_wolaja_link_do_pbn_bez_uczelni():
    naruszenia = []
    for sciezka in _szablony():
        tekst = sciezka.read_text(encoding="utf-8", errors="replace")
        for nr, linia in enumerate(tekst.splitlines(), start=1):
            if WZORZEC.search(linia):
                naruszenia.append(f"{sciezka.relative_to(SRC)}:{nr}: {linia.strip()}")

    assert not naruszenia, (
        "Szablony wołają link_do_pbn/link_do_pi bez uczelni (w multi-hosted "
        'renderuje się href="None"). Użyj tagu {% link_do_pbn obj as url %} '
        "albo filtra obj|link_do_pi:uczelnia z biblioteki 'prace':\n"
        + "\n".join(naruszenia)
    )
