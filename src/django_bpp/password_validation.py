"""Walidatory siły haseł BPP (NIST SP 800-63B: lista słabych haseł).

Bez reguł złożoności (cyfry, znaki specjalne) — zamiast tego odrzucamy
hasła łatwe do odgadnięcia: powtórzenia, sekwencje, słowa związane
z serwisem i hasła znane z wycieków (Have I Been Pwned).
"""

import hashlib
import logging
import re
import threading
import unicodedata

import requests
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import OperationalError, ProgrammingError
from zxcvbn import zxcvbn

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


def _jest_powtorzeniem(haslo):
    """Czy hasło to kopie krótszego fragmentu, np. „robak1robak1robak”.

    Ostatnia kopia może być urwana; fragment mieści się w haśle co najmniej
    dwa razy. zxcvbn wykrywa tylko pełne kopie — urwaną końcówkę wycenia jak
    losowe znaki, przez co takie hasło dostaje u niego najwyższą ocenę.
    """
    # Najmniejszy okres z funkcji prefiksowej KMP (n - pi[n-1]) — liniowo,
    # bo Django nie ogranicza długości hasła, a pętla po wszystkich okresach
    # byłaby kwadratowa (DoS przez hasło rzędu megabajtów).
    haslo = haslo.lower()
    n = len(haslo)
    if n < 2:
        return False
    pi = [0] * n
    for i in range(1, n):
        k = pi[i - 1]
        while k and haslo[i] != haslo[k]:
            k = pi[k - 1]
        if haslo[i] == haslo[k]:
            k += 1
        pi[i] = k
    return n - pi[-1] <= n // 2


class SimplePatternPasswordValidator:
    """Odrzuca hasła z powtórzeń jednego znaku lub krótszego fragmentu,
    o zbyt małej liczbie różnych znaków albo będące prostą sekwencją."""

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
        if _jest_powtorzeniem(password):
            raise ValidationError(
                "Hasło nie może być powtórzeniem krótszego fragmentu "
                "(np. robak1robak1robak…).",
                code="password_repeated_pattern",
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
            "znaków i nie może być powtórzeniem jednego znaku ani krótszego "
            "fragmentu, ani prostą sekwencją (np. 12345…, abcde…, qwerty…)."
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


# zxcvbn rzuca ValueError dla dłuższych haseł; oceniamy prefiks — jego siła
# nigdy nie przekracza siły całego hasła, więc nie przepuścimy słabszego.
ZXCVBN_MAKS_DLUGOSC = 72

# zxcvbn wpisuje ``user_inputs`` do globalnego słownika modułu, a potem
# z niego czyta — równoległe wywołania (wątki ASGI/WSGI) widziałyby słowa
# innego żądania. Stąd blokada wokół całego wywołania.
_ZXCVBN_BLOKADA = threading.Lock()

# Polskie podpowiedzi wg typu wzorca znalezionego przez zxcvbn (nazwy
# wzorców to stabilne API; angielskie komunikaty zxcvbn pomijamy).
_POWODY_SLOWNIKOWE = {
    "passwords": "popularne hasła",
    "user_inputs": "słowa związane z kontem lub serwisem",
}
_POWODY_WZORCOW = {
    "repeat": "powtórzenia",
    "sequence": "sekwencje znaków (abc, 123)",
    "spatial": "sąsiednie klawisze",
    "date": "daty",
}


def _slowa_uzytkownika(user):
    if user is None:
        return []
    teksty = [
        getattr(user, pole, "") or ""
        for pole in ("username", "first_name", "last_name", "email")
    ]
    slowa = []
    for tekst in teksty:
        for slowo in re.split(r"[\s@._+-]+", tekst):
            if len(slowo) >= MIN_DLUGOSC_SLOWA_KONTEKSTOWEGO:
                slowa.extend({slowo.lower(), normalizuj(slowo)})
    return slowa


def _powody(sekwencja):
    powody = []
    for dopasowanie in sekwencja:
        wzorzec = dopasowanie["pattern"]
        if wzorzec == "dictionary":
            powod = _POWODY_SLOWNIKOWE.get(
                dopasowanie["dictionary_name"], "pospolite słowa lub imiona"
            )
        elif wzorzec == "regex" and dopasowanie.get("regex_name") == "recent_year":
            powod = "lata"
        else:
            powod = _POWODY_WZORCOW.get(wzorzec)
        if powod and powod not in powody:
            powody.append(powod)
    return powody


class ZxcvbnPasswordValidator:
    """Odrzuca hasła łatwe do odgadnięcia wg oceny zxcvbn (0–4), liczonej
    lokalnie: popularne hasła i słowa, powtórzenia, sekwencje, klawiatura,
    daty — także w przeróbkach (wspak, „P@ssw0rd”). Jako własne słowa
    dostaje słowa kontekstowe serwisu i dane konta użytkownika.
    Próg: ``DJANGO_BPP_PASSWORD_MIN_ZXCVBN_SCORE`` (0 wyłącza).
    """

    def __init__(self, min_score=None):
        self._min_score = min_score

    @property
    def min_score(self):
        if self._min_score is not None:
            return self._min_score
        return getattr(settings, "BPP_HASLA_MIN_SILA_ZXCVBN", 3)

    def validate(self, password, user=None):
        if not self.min_score:
            return
        slowa = [*slowa_kontekstowe(), *_slowa_uzytkownika(user)]
        with _ZXCVBN_BLOKADA:
            wynik = zxcvbn(password[:ZXCVBN_MAKS_DLUGOSC], user_inputs=slowa)
        if wynik["score"] >= self.min_score:
            return
        powody = _powody(wynik["sequence"])
        raise ValidationError(
            "Hasło jest zbyt łatwe do odgadnięcia%(powody)s. Dodaj kilka "
            "nieprzewidywalnych słów albo wybierz zupełnie inne hasło.",
            code="password_too_guessable",
            params={"powody": f" (zawiera: {', '.join(powody)})" if powody else ""},
        )

    def get_help_text(self):
        return (
            "Hasło nie może być łatwe do odgadnięcia — np. złożone z popularnych "
            "haseł, powtórzeń, sekwencji, sąsiednich klawiszy czy dat."
        )
