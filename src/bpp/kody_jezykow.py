"""Kody języków ISO 639-1 dla polskich nazw języków (FD#513).

Służy do jednorazowego uzupełnienia pola „Kod języka wg BCP 47” w słowniku
języków (migracja ``0533``) — po tym kodzie BPP dopasowuje język pracy
pobieranej z CrossRef. Klucze: nazwa języka małymi literami, bez dopisku
„język”. Tylko nazwy jednoznaczne.
"""

import re

KOD_WG_NAZWY = {
    "angielski": "en",
    "polski": "pl",
    "niemiecki": "de",
    "francuski": "fr",
    "hiszpański": "es",
    "włoski": "it",
    "rosyjski": "ru",
    "ukraiński": "uk",
    "białoruski": "be",
    "czeski": "cs",
    "słowacki": "sk",
    "słoweński": "sl",
    "chorwacki": "hr",
    "serbski": "sr",
    "bośniacki": "bs",
    "macedoński": "mk",
    "bułgarski": "bg",
    "litewski": "lt",
    "łotewski": "lv",
    "estoński": "et",
    "węgierski": "hu",
    "rumuński": "ro",
    "portugalski": "pt",
    "kataloński": "ca",
    "niderlandzki": "nl",
    "holenderski": "nl",
    "duński": "da",
    "szwedzki": "sv",
    "norweski": "no",
    "fiński": "fi",
    "islandzki": "is",
    "grecki": "el",
    "nowogrecki": "el",
    "turecki": "tr",
    "łaciński": "la",
    "łacina": "la",
    "hebrajski": "he",
    "arabski": "ar",
    "perski": "fa",
    "chiński": "zh",
    "japoński": "ja",
    "koreański": "ko",
    "wietnamski": "vi",
    "hindi": "hi",
    "esperanto": "eo",
    "albański": "sq",
    "gruziński": "ka",
    "ormiański": "hy",
    "kazachski": "kk",
    "irlandzki": "ga",
    "walijski": "cy",
    "baskijski": "eu",
    "galicyjski": "gl",
    "maltański": "mt",
    "afrikaans": "af",
    "indonezyjski": "id",
    "malajski": "ms",
    "tajski": "th",
    "mongolski": "mn",
    "azerski": "az",
    "uzbecki": "uz",
    "jidysz": "yi",
}

# Kod języka w rozumieniu CrossRef: podstawowy podtag (2–3 małe litery),
# opcjonalnie z dalszymi podtagami BCP 47 (np. „en-GB”, „zh-Hant”).
WZORZEC_KODU = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")


def kod_dla_nazwy(nazwa):
    """Kod ISO 639-1 dla polskiej nazwy języka albo ``None``.

    Toleruje wielkość liter, białe znaki i dopisek „język” („Język
    angielski”, „angielski język”)."""
    if not nazwa:
        return None
    slowa = [s for s in str(nazwa).strip().lower().split() if s != "język"]
    return KOD_WG_NAZWY.get(" ".join(slowa))


def podtag_podstawowy(kod):
    """„en-GB” → „en”; pusty/niepoprawny → ``""``."""
    return str(kod or "").split("-")[0].strip().lower()
