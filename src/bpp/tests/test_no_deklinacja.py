import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # korzeń repo
# ten plik trzyma wzorce jako literały — wykluczamy go, by nie łapał sam siebie
SELF = "src/bpp/tests/test_no_deklinacja.py"


def _grep(pattern, pathspec):
    res = subprocess.run(
        ["git", "grep", "-n", pattern, "--", pathspec, f":(exclude){SELF}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return res.stdout.strip()


def test_brak_starych_tagow_rzeczownik():
    assert _grep(r"{% rzeczownik_", "*.html") == ""


def test_brak_load_deklinacja():
    assert _grep(r"{% load deklinacja", "*.html") == ""


def test_brak_definicji_deklinacji_w_py():
    # wzorce w formie definicji, by nie łapać zwykłych referencji
    assert _grep("def znajdz_rzeczownik", "*.py") == ""
    assert _grep("def lazy_rzeczownik_title", "*.py") == ""
    assert _grep("^deklinacja = ", "*.py") == ""
