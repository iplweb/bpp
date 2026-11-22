"""Porady wyświetlane w pasku „Porady BPP” na stronie głównej.

Każda porada opisuje funkcję, która naprawdę jest w BPP, i linkuje do
opublikowanej dokumentacji (otwieranej w nowym oknie). Ścieżki muszą
wskazywać na istniejące strony w ``docs/`` — pilnuje tego test
``bpp/tests/test_pasek_porad.py``.

Zmiana treści porad zmienia ``wersja_porad()``, więc pasek pojawi się
ponownie także u osób, które wcześniej go zamknęły.
"""

import hashlib
from dataclasses import dataclass
from functools import cache

#: Adres opublikowanej dokumentacji (``site_url`` z ``mkdocs.yml``).
DOKUMENTACJA_URL = "https://iplweb.github.io/bpp/"


@dataclass(frozen=True)
class Porada:
    tekst: str
    #: Ścieżka strony w dokumentacji, względem ``DOKUMENTACJA_URL``
    #: (adres strony mkdocs, np. ``uzytkownik/tabela-krzyzowa/``),
    #: opcjonalnie z kotwicą.
    dokumentacja: str
    link_tekst: str = "Jak to działa?"

    @property
    def url(self):
        return DOKUMENTACJA_URL + self.dokumentacja


PORADY = (
    Porada(
        "Klawisz „/” otwiera szybkie wyszukiwanie — wystarczy fragment "
        "tytułu, nazwisko, DOI albo ISBN.",
        "uzytkownik/przegladanie-i-wyszukiwanie/",
    ),
    Porada(
        "W menu „szukaj → precyzyjnie” zbudujesz zapytanie z wielu warunków "
        "naraz, np. artykuły autora z lat 2020–2024.",
        "uzytkownik/wyszukiwanie-precyzyjne/",
    ),
    Porada(
        "Gotowe przepisy na częste zapytania — prace z Impact Factor, "
        "w otwartym dostępie, wspólne prace dwóch autorów — znajdziesz "
        "w przykładach wyszukiwania precyzyjnego.",
        "uzytkownik/wyszukiwanie-precyzyjne-przyklady/",
        "Zobacz przykłady",
    ),
    Porada(
        "Tabela krzyżowa zamienia wynik wyszukiwania w zestawienie "
        "(np. jednostki × rodzaje prac) — także do pobrania jako XLSX lub CSV.",
        "uzytkownik/tabela-krzyzowa/",
    ),
    Porada(
        "Zapytanie, które powtarzasz co miesiąc, można zapisać pod nazwą "
        "i wczytywać jednym kliknięciem.",
        "uzytkownik/wyszukiwanie-precyzyjne-zapisane/",
    ),
    Porada(
        "Na stronie autora pobierzesz wszystkie jego prace w formacie BibTeX "
        "lub RIS (Zotero, Mendeley, EndNote) albo w Excelu z punktacją.",
        "uzytkownik/przegladanie-i-wyszukiwanie/"
        "#eksport-publikacji-autora-bibtex-i-ris",
    ),
    Porada(
        "Listę swoich prac z wybranych lat — np. do sprawozdania — pobierzesz "
        "jako plik Word albo Excel.",
        "uzytkownik/pobieranie-listy-publikacji/",
    ),
    Porada(
        "Punkty MNiSW, punkty dla autora (PkDAut) i sloty sprawdzisz na "
        "stronie autora i na stronie każdej pracy.",
        "uzytkownik/punkty-i-sloty/",
    ),
    Porada(
        "Przycisk „Zobacz sieć powiązań” na stronie autora pokazuje, z kim "
        "autor publikuje i jak często.",
        "uzytkownik/powiazania-autorow/",
    ),
    Porada(
        "Po zalogowaniu możesz sam uzupełnić swoją stronę autora: zdjęcie, "
        "biogram, linki do profili i wyróżnione publikacje.",
        "uzytkownik/moj-profil-autora/",
    ),
    Porada(
        "Najnowsze publikacje autora lub jednostki wyświetlisz na dowolnej "
        "stronie WWW — wystarczy wkleić jedną linię kodu z generatora.",
        "uzytkownik/widget-publikacji/",
    ),
    Porada(
        "Brakuje Twojej pracy w bazie? Zgłoś ją przyciskiem „Zgłoś "
        "publikację” — wystarczy tytuł, rok i link albo plik.",
        "uzytkownik/zgloszenie-publikacji/",
    ),
    Porada(
        "Bibliografię możesz podłączyć do asystenta AI (np. Claude, ChatGPT) "
        "i pytać o publikacje zwykłym językiem — instrukcja jest pod adresem "
        "/mcp/ tej strony.",
        "uzytkownik/asystent-ai/",
    ),
    Porada(
        "Dla redaktorów: oświadczenia autorów wydrukujesz pojedynczo ze strony "
        "pracy albo wiele naraz (PDF, DOCX, XLSX) i wyślesz do PBN.",
        "redaktor/oswiadczenia/",
    ),
)


@cache
def wersja_porad():
    """Krótki skrót treści porad — klucz zapamiętanego zamknięcia paska."""
    skrot = hashlib.sha256()
    for porada in PORADY:
        skrot.update(f"{porada.tekst}\n{porada.dokumentacja}\n".encode())
    return skrot.hexdigest()[:12]
