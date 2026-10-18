"""Rozpoznawanie identyfikatorów publikacji wpisanych w pole „Link lub DOI".

Na wzór „różdżki" Zotero: użytkownik może wkleić DOI w dowolnej postaci
(``10.xxxx/…``, ``doi:10.xxxx/…``, ``doi.org/…``, ``http://dx.doi.org/…``),
a także PMID, PMCID lub identyfikator arXiv — zamieniamy to na kanoniczny
adres URL, bo tego oczekuje PBN i dalsza część systemu (FD#480).

Wykrywanie i normalizację robi biblioteka ``idutils`` (InvenioRDM/Zenodo).
Bierzemy z niej tylko schematy jednoznaczne: goła liczba (``idutils`` uzna ją
za PMID) czy goły numer w stylu ``2101.00001`` (arXiv) mogą być czymkolwiek,
więc dla PMID i arXiv wymagamy jawnego prefiksu.
"""

import re

import idutils

# Znaki, które przy kopiowaniu z cytowania lub zdania „doklejają się" na końcu
# DOI, a do niego nie należą.
_OGONY = ".,;"

_PMID_RE = re.compile(r"^pmid\s*:?\s*(\d+)$", re.IGNORECASE)
_PMCID_RE = re.compile(r"^(?:pmcid\s*:?\s*)?(pmc\d+)$", re.IGNORECASE)
_ARXIV_RE = re.compile(r"^arxiv\s*:\s*(\S+)$", re.IGNORECASE)


def normalizuj_identyfikator(wartosc: str) -> str:
    """Zamień rozpoznany identyfikator na kanoniczny URL.

    Wartość, której nie da się jednoznacznie rozpoznać, zwracamy bez zmian —
    walidację adresu URL robi dalej pole formularza.

    >>> normalizuj_identyfikator("doi:10.1234/abc")
    'https://doi.org/10.1234/abc'
    >>> normalizuj_identyfikator("https://example.com/x")
    'https://example.com/x'
    """
    s = wartosc.strip()
    if not s:
        return wartosc

    if "doi" in idutils.detect_identifier_schemes(s):
        doi = idutils.normalize_doi(s).rstrip(_OGONY)
        return idutils.to_url(doi, "doi", url_scheme="https")

    if m := _PMID_RE.match(s):
        return idutils.to_url(m.group(1), "pmid", url_scheme="https")

    if m := _PMCID_RE.match(s):
        pmcid = m.group(1).upper()
        return idutils.to_url(pmcid, "pmcid", url_scheme="https")

    if (m := _ARXIV_RE.match(s)) and idutils.is_arxiv(m.group(1)):
        return f"https://arxiv.org/abs/{m.group(1)}"

    return wartosc
