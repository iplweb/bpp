"""Strażnik: adresy do PBN składamy z ``Uczelnia.pbn_api_root``, nie z literału.

W instalacji multi-hosted każda uczelnia ma własny ``pbn_api_root`` (produkcja,
środowisko testowe PBN, instancja demo). Link sklejony z wpisanego na sztywno
``https://pbn.nauka.gov.pl`` prowadzi wtedy do CUDZEGO systemu — i robi to po
cichu, bo adres wygląda poprawnie. Kanoniczne wzorce siedzą w ``bpp.const``
(``LINK_PBN_DO_AUTORA``, ``LINK_PBN_DO_ZRODLA``, ``LINK_PBN_DO_PUBLIKACJI``,
``LINK_PBN_DO_WYDAWCY``) i przyjmują ``pbn_api_root`` jako parametr.

Ten błąd wracał kilka razy w różnych modułach (eksporty XLSX deduplikatorów,
kolejka eksportu, JavaScript importera), dlatego test pilnuje całego drzewa
źródeł naraz. Komentarze i docstringi są pomijane — opis starego, błędnego
adresu w komentarzu jest pożądany, bo tłumaczy, czego nie powtarzać.

Lista ``DOZWOLONE`` to miejsca, w których literał jest poprawny, każde z
powodem. Dopisanie czegoś do niej jest decyzją do uzasadnienia w code review,
nie sposobem na uciszenie testu.
"""

import ast
from pathlib import Path

import pytest

HOST = "pbn.nauka.gov.pl"
SRC = Path(__file__).resolve().parents[2]

# ścieżka → powód, dla którego literał jest tu na miejscu
DOZWOLONE = {
    "bpp_setup_wizard/forms.py": "wybór środowiska PBN w kreatorze (wartość do zapisania w Uczelnia.pbn_api_root)",
    "bpp_setup_wizard/templates/bpp_setup_wizard/uczelnia_setup.html": "link do centrum pomocy PBN (instrukcja uzyskania API)",
    "bpp/management/commands/debug_setup_initial_data.py": "domyślna wartość parametru komendy debugowej",
    "cerif_export/cerif/orgunit.py": "URI schematu identyfikatorów CERIF (stała nazwa, nie link do klikania)",
    "cerif_export/cerif/wspolne.py": "URI schematu identyfikatorów CERIF (stała nazwa, nie link do klikania)",
    "pbn_export_queue/views/constants.py": "adres pomocy PBN i link do dokumentacji API w szablonie zgłoszenia",
    "importer_publikacji/providers/pbn.py": "tekst podpowiedzi „wklej URL z pbn.nauka.gov.pl”",
    "pbn_import/templatetags/pbn_import_tags.py": "świadomy fallback na publiczny root, gdy uczelni nie da się ustalić",
}


def _dozwolone(sciezka):
    return str(sciezka.relative_to(SRC)) in DOZWOLONE


def _pliki(wzorzec):
    for sciezka in SRC.rglob(wzorzec):
        tekst = str(sciezka)
        if "/tests/" in tekst or "/cassettes/" in tekst or "/node_modules/" in tekst:
            continue
        if sciezka.name.startswith("test_"):
            continue
        yield sciezka


def test_kod_python_nie_sklada_adresu_pbn_z_literalu():
    """Literał w kodzie (poza komentarzem i docstringiem) = błąd."""
    naruszenia = []
    for sciezka in _pliki("*.py"):
        if _dozwolone(sciezka):
            continue
        tekst = sciezka.read_text(encoding="utf-8", errors="replace")
        if HOST not in tekst:
            continue
        drzewo = ast.parse(tekst, filename=str(sciezka))
        # Docstringi (pierwszy Expr w module/klasie/funkcji) pomijamy —
        # tam opis starego adresu jest dokumentacją, nie linkiem.
        docstringi = set()
        for wezel in ast.walk(drzewo):
            if isinstance(
                wezel,
                (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                cialo = getattr(wezel, "body", [])
                if (
                    cialo
                    and isinstance(cialo[0], ast.Expr)
                    and isinstance(cialo[0].value, ast.Constant)
                    and isinstance(cialo[0].value.value, str)
                ):
                    docstringi.add(id(cialo[0].value))
        for wezel in ast.walk(drzewo):
            if (
                isinstance(wezel, ast.Constant)
                and isinstance(wezel.value, str)
                and HOST in wezel.value
                and id(wezel) not in docstringi
            ):
                naruszenia.append(
                    f"{sciezka.relative_to(SRC)}:{wezel.lineno}: {wezel.value[:90]}"
                )

    assert not naruszenia, (
        "Adres PBN wpisany na sztywno w kodzie. Złóż link z "
        "Uczelnia.pbn_api_root (wzorce w bpp.const), a gdy uczelni nie da się "
        "ustalić — nie linkuj:\n" + "\n".join(naruszenia)
    )


@pytest.mark.parametrize("wzorzec", ["templates/**/*.html", "static/**/*.js"])
def test_szablony_i_javascript_nie_skladaja_adresu_pbn_z_literalu(wzorzec):
    naruszenia = []
    for sciezka in _pliki(wzorzec):
        if _dozwolone(sciezka):
            continue
        for nr, linia in enumerate(
            sciezka.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
        ):
            if HOST in linia:
                naruszenia.append(f"{sciezka.relative_to(SRC)}:{nr}: {linia.strip()}")

    assert not naruszenia, (
        "Adres PBN wpisany na sztywno w szablonie/JS. Adres ma przyjść z "
        "backendu (zna pbn_api_root uczelni z requestu):\n" + "\n".join(naruszenia)
    )
