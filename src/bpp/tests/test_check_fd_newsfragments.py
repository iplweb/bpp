"""bin/check-fd-newsfragments.py: każdy FD# z tytułu PR-a ma newsfragment."""

import importlib.util
from pathlib import Path

import pytest

_SCIEZKA = Path(__file__).resolve().parents[3] / "bin" / "check-fd-newsfragments.py"
if not _SCIEZKA.exists():
    # The CI test-runner image ships src/ only, without bin/; the script itself
    # runs on every PR in the "Newsfragments" workflow.
    pytest.skip("bin/ not available in this environment", allow_module_level=True)
_spec = importlib.util.spec_from_file_location("check_fd_newsfragments", _SCIEZKA)
modul = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(modul)

NF = "src/bpp/newsfragments"


@pytest.mark.parametrize(
    ("tytul", "oczekiwane"),
    [
        ("Fix FD#456, FD#481, FD#460: drobne", ["456", "481", "460"]),
        ("Record history (FD#441, FD#600)", ["441", "600"]),
        ("fd 12 i FD#12 jeszcze raz", ["12"]),
        ("Bump ruff", []),
    ],
)
def test_numery_fd(tytul, oczekiwane):
    assert modul.numery_fd(tytul) == oczekiwane


def test_wszystkie_fragmenty_sa():
    sciezki = [f"{NF}/fd456.bugfix.rst", f"{NF}/fd481.feature.md", "src/x.py"]
    assert modul.brakujace("FD#456 FD#481", sciezki) == []


def test_brakujacy_fragment():
    assert modul.brakujace("FD#456 FD#481", [f"{NF}/fd456.bugfix.rst"]) == ["481"]


@pytest.mark.parametrize(
    "sciezka",
    [
        f"{NF}/fd4560.bugfix.rst",  # inny numer
        f"{NF}/fd456.txt",  # zła nazwa
        f"{NF}/fd456.nieznany.rst",  # nieznany typ
        "changes/newsfragments/fd456.bugfix.rst",  # zły katalog
    ],
)
def test_nieuznawane_fragmenty(sciezka):
    assert modul.brakujace("FD#456", [sciezka]) == ["456"]


def test_slug_po_numerze_dozwolony():
    assert modul.brakujace("FD#456", [f"{NF}/fd456-link.bugfix.rst"]) == []


def test_main(tmp_path, capsys):
    plik = tmp_path / "zmiany.txt"
    plik.write_text(f"{NF}/fd1.bugfix.rst\n")
    assert modul.main(["x", "FD#1", str(plik)]) == 0
    assert modul.main(["x", "FD#1 FD#2", str(plik)]) == 1
    assert "FD#2" in capsys.readouterr().out
