"""Walidatory siły haseł BPP (NIST SP 800-63B: lista słabych haseł).

Bez reguł złożoności (cyfry, znaki specjalne) — zamiast tego odrzucamy
hasła łatwe do odgadnięcia: powtórzenia, sekwencje, słowa związane
z serwisem i hasła znane z wycieków (Have I Been Pwned).
"""

import hashlib
import logging
import unicodedata

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import OperationalError, ProgrammingError

logger = logging.getLogger(__name__)

# Ciągi, których kolejne znaki tworzą „prostą sekwencję”: cyfry, alfabet
# i rzędy klawiatury QWERTY (także sklejone, np. „qwertyuiopasdf”).
SEKWENCJE = (
    "0123456789",
    "abcdefghijklmnopqrstuvwxyz",
    "1234567890",
    "qwertyuiopasdfghjklzxcvbnm",
)

# Słowa kontekstowe zawsze odrzucane (nazwa serwisu).
STALE_SLOWA_KONTEKSTOWE = ("bpp", "bibliografia")

MIN_DLUGOSC_SLOWA_KONTEKSTOWEGO = 3

PWNED_API_URL = "https://api.pwnedpasswords.com/range/{prefix}"
PWNED_TIMEOUT = 3


def normalizuj(tekst):
    """Małe litery, bez polskich znaków diakrytycznych (ą→a, ł→l itd.)."""
    tekst = tekst.lower().replace("ł", "l")
    tekst = unicodedata.normalize("NFKD", tekst)
    return "".join(z for z in tekst if not unicodedata.combining(z))


def _jest_sekwencja(haslo):
    haslo = haslo.lower()
    for sekwencja in SEKWENCJE:
        # Powielona sekwencja łapie też ciągi „zawijane”, np. 123456789012345.
        powielona = sekwencja * (len(haslo) // len(sekwencja) + 2)
        if haslo in powielona or haslo in powielona[::-1]:
            return True
    return False


class SimplePatternPasswordValidator:
    """Odrzuca hasła z powtórzeń jednego znaku, o zbyt małej liczbie
    różnych znaków albo będące prostą sekwencją znaków."""

    def __init__(self, min_unique_chars=5):
        self.min_unique_chars = min_unique_chars

    def validate(self, password, user=None):
        unikalne = len(set(password.lower()))
        if len(password) > 1 and unikalne == 1:
            raise ValidationError(
                "Hasło nie może składać się z jednego powtarzanego znaku.",
                code="password_repeated_character",
            )
        if unikalne < self.min_unique_chars:
            raise ValidationError(
                "Hasło musi zawierać co najmniej %(min_unique_chars)d różnych znaków.",
                code="password_too_few_unique_characters",
                params={"min_unique_chars": self.min_unique_chars},
            )
        if _jest_sekwencja(password):
            raise ValidationError(
                "Hasło nie może być prostą sekwencją znaków "
                "(np. 12345…, abcde…, qwerty…).",
                code="password_simple_sequence",
            )

    def get_help_text(self):
        return (
            f"Hasło musi zawierać co najmniej {self.min_unique_chars} różnych "
            "znaków i nie może być powtórzeniem jednego znaku ani prostą "
            "sekwencją (np. 12345…, abcde…, qwerty…)."
        )


def _slowa_z_tekstu(tekst):
    return normalizuj(tekst).replace(".", " ").replace("-", " ").split()


def _slowa_z_bazy():
    from django.contrib.sites.models import Site

    from bpp.models import Uczelnia

    slowa = []
    try:
        for nazwa, skrot in Uczelnia.objects.values_list("nazwa", "skrot"):
            slowa.extend(_slowa_z_tekstu(nazwa or ""))
            slowa.append(normalizuj(skrot or ""))
        for domena in Site.objects.values_list("domain", flat=True):
            # Bez domeny najwyższego poziomu (.pl), portu i „www”.
            etykiety = normalizuj(domena or "").split(":")[0].split(".")
            slowa.extend(e for e in etykiety[:-1] if e != "www")
    except (ProgrammingError, OperationalError):
        # Kreator pierwszego uruchomienia albo trwające migracje: tabel może
        # jeszcze nie być. Wtedy sprawdzamy tylko słowa stałe i z konfiguracji.
        logger.info("Słowa kontekstowe haseł: tabele niedostępne, pomijam.")
    return slowa


def slowa_kontekstowe():
    slowa = list(STALE_SLOWA_KONTEKSTOWE)
    slowa.extend(
        normalizuj(s) for s in getattr(settings, "BPP_HASLA_SLOWA_KONTEKSTOWE", [])
    )
    slowa.extend(_slowa_z_bazy())
    return {
        s.strip() for s in slowa if len(s.strip()) >= MIN_DLUGOSC_SLOWA_KONTEKSTOWEGO
    }


class ContextWordsPasswordValidator:
    """Odrzuca hasła zawierające słowa związane z serwisem: „bpp”,
    „bibliografia”, nazwę i skrót uczelni, domenę serwisu oraz słowa
    z ``DJANGO_BPP_PASSWORD_CONTEXT_WORDS``."""

    def validate(self, password, user=None):
        haslo = normalizuj(password)
        if any(slowo in haslo for slowo in slowa_kontekstowe()):
            raise ValidationError(
                "Hasło nie może zawierać słów związanych z serwisem "
                "(nazwa systemu, nazwa lub skrót uczelni, adres strony).",
                code="password_context_word",
            )

    def get_help_text(self):
        return (
            "Hasło nie może zawierać słów związanych z serwisem, np. nazwy "
            "systemu, nazwy lub skrótu uczelni, adresu strony."
        )


class PwnedPasswordValidator:
    """Odrzuca hasła znane z wycieków (Have I Been Pwned, k-anonimowość).

    Do API trafia wyłącznie 5-znakowy prefiks skrótu SHA-1; sufiks
    porównujemy lokalnie. Awaria API nie blokuje zmiany hasła (fail-open).
    Wyłącznik: ``DJANGO_BPP_PASSWORD_CHECK_PWNED``.
    """

    def validate(self, password, user=None):
        if not getattr(settings, "BPP_HASLA_SPRAWDZAJ_WYCIEKI", True):
            return
        # SHA-1 to wymóg protokołu HIBP (range API), a nie sposób
        # przechowywania hasła — stąd usedforsecurity=False.
        skrot = (
            hashlib.sha1(password.encode("utf-8"), usedforsecurity=False)
            .hexdigest()
            .upper()
        )
        prefix, sufiks = skrot[:5], skrot[5:]
        try:
            odpowiedz = requests.get(
                PWNED_API_URL.format(prefix=prefix),
                headers={
                    "Add-Padding": "true",
                    "User-Agent": "BPP-password-validator",
                },
                timeout=PWNED_TIMEOUT,
            )
        except requests.RequestException as e:
            logger.warning(
                "Nie udało się sprawdzić hasła w Have I Been Pwned (%s) "
                "— pomijam sprawdzenie.",
                type(e).__name__,
            )
            return
        if odpowiedz.status_code != 200:
            logger.warning(
                "Have I Been Pwned zwróciło status %s — pomijam sprawdzenie.",
                odpowiedz.status_code,
            )
            return
        for linia in odpowiedz.text.splitlines():
            kandydat, _, licznik = linia.strip().partition(":")
            if kandydat.upper() != sufiks:
                continue
            try:
                ile = int(licznik)
            except ValueError:
                ile = 0  # nieczytelny licznik — traktuj jak brak trafienia
            if ile > 0:
                raise ValidationError(
                    "To hasło pojawiło się w znanych wyciekach danych "
                    "i nie może zostać użyte. Wybierz inne.",
                    code="password_pwned",
                )

    def get_help_text(self):
        return "Hasło nie może pochodzić ze znanych wycieków danych."
