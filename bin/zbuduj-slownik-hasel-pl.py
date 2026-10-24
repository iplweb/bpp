"""Zbuduj polski słownik dla walidatora haseł zxcvbn.

Najczęstsze polskie słowa z wordfreq (wg częstości) → indeks marisa-trie
``słowo → pozycja`` w ``src/django_bpp/data/slownik_hasel_pl.marisa``.
Dla słów z polskimi znakami dodawany jest też wariant bez nich
(„żółw” → „zolw”) z tą samą pozycją — tak hasła wpisuje się najczęściej.

wordfreq NIE jest zależnością BPP — skrypt uruchamiamy jednorazowo:

    uv run --no-project --with wordfreq==3.1.1 --with marisa-trie \\
        python bin/zbuduj-slownik-hasel-pl.py

Dane wordfreq są na licencji CC-BY-SA 4.0 — patrz
``src/django_bpp/data/SLOWNIK_HASEL_PL_LICENCJA.txt``.
"""

import argparse
import unicodedata
from pathlib import Path

import marisa_trie
from wordfreq import top_n_list

DOMYSLNA_LICZBA_SLOW = 50_000
MIN_DLUGOSC = 3
WYJSCIE = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "django_bpp"
    / "data"
    / "slownik_hasel_pl.marisa"
)


def bez_polskich_znakow(slowo):
    # Ta sama normalizacja co django_bpp.password_validation.normalizuj.
    slowo = slowo.replace("ł", "l")
    slowo = unicodedata.normalize("NFKD", slowo)
    return "".join(z for z in slowo if not unicodedata.combining(z))


def zbuduj(liczba_slow):
    pozycje = {}
    pozycja = 0
    # Zapas, bo część słów odpada na filtrze (cyfry, za krótkie).
    for slowo in top_n_list("pl", liczba_slow * 2, wordlist="large"):
        if len(slowo) < MIN_DLUGOSC or not slowo.isalpha():
            continue
        pozycja += 1
        for wariant in (slowo, bez_polskich_znakow(slowo)):
            pozycje.setdefault(wariant, pozycja)
        if pozycja >= liczba_slow:
            break
    return marisa_trie.RecordTrie("<I", ((s, (p,)) for s, p in pozycje.items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--liczba-slow", type=int, default=DOMYSLNA_LICZBA_SLOW)
    parser.add_argument("--wyjscie", type=Path, default=WYJSCIE)
    args = parser.parse_args()

    trie = zbuduj(args.liczba_slow)
    args.wyjscie.parent.mkdir(parents=True, exist_ok=True)
    trie.save(str(args.wyjscie))
    print(
        f"Zapisano {len(trie)} haseł ({args.liczba_slow} słów + warianty bez "
        f"polskich znaków) do {args.wyjscie} "
        f"({args.wyjscie.stat().st_size // 1024} KB)"
    )


if __name__ == "__main__":
    main()
