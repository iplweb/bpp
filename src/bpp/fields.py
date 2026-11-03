import logging
from decimal import Decimal, InvalidOperation

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django import forms
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import models

logger = logging.getLogger(__name__)

# Ta klasa na obecną chwilę nie zawiera nic, ale używamy jej, aby oznaczyć
# odpowiednio pola, gdzie chodzi o rok:
YearField = models.IntegerField


class CommaDecimalField(forms.DecimalField):
    """
    A DecimalField that accepts both comma and period as decimal separators.
    Converts comma to period for processing.
    """

    def to_python(self, value):
        if value in self.empty_values:
            return None

        if isinstance(value, str):
            value = value.replace(",", ".")

        try:
            return Decimal(str(value))
        except (ValueError, InvalidOperation):
            raise ValidationError(self.error_messages["invalid"]) from None


class DOIField(models.CharField):
    def __init__(self, *args, **kw):
        if "help_text" not in kw:
            kw["help_text"] = "Digital Object Identifier (DOI)"

        if "max_length" not in kw:
            kw["max_length"] = 2048

        super().__init__(*args, **kw)


def klucze_szyfrowania() -> list[str]:
    """Skonfigurowane klucze Fernet, w kolejności: najpierw klucz główny.

    ``FIELD_ENCRYPTION_KEY`` (env ``DJANGO_BPP_FIELD_ENCRYPTION_KEY``) może
    zawierać kilka kluczy rozdzielonych przecinkami — pierwszy szyfruje,
    pozostałe służą tylko do odczytu (rotacja). ``DSPACE_CREDENTIALS_KEY``
    jest dokładany na końcu jako klucz zgodności wstecznej.
    """
    wynik = []
    for nazwa in ("FIELD_ENCRYPTION_KEY", "DSPACE_CREDENTIALS_KEY"):
        surowe = getattr(settings, nazwa, "") or ""
        if isinstance(surowe, (list, tuple)):
            kandydaci = surowe
        else:
            kandydaci = str(surowe).split(",")
        for klucz in kandydaci:
            klucz = klucz.strip()
            if klucz and klucz not in wynik:
                wynik.append(klucz)
    return wynik


def multifernet() -> MultiFernet | None:
    """MultiFernet z aktualnych ustawień albo ``None``, gdy brak klucza.

    Błędny format klucza → ``ImproperlyConfigured`` (świadomie bez cichego
    przejścia na zapis jawny, gdy operator ustawił klucz, ale z błędem).
    """
    klucze = klucze_szyfrowania()
    if not klucze:
        return None
    try:
        return MultiFernet([Fernet(k.encode()) for k in klucze])
    except (ValueError, TypeError) as e:
        raise ImproperlyConfigured(
            "Klucz szyfrowania pól (DJANGO_BPP_FIELD_ENCRYPTION_KEY / "
            "DSPACE_CREDENTIALS_KEY) ma niepoprawny format — oczekiwano "
            "klucza Fernet (32 bajty, base64 URL-safe)."
        ) from e


#: Każdy szyfrogram Fernet zaczyna się od tego prefiksu (bajt wersji 0x80
#: + początek znacznika czasu, zakodowane base64).
PREFIKS_SZYFROGRAMU = "gAAAAA"


def wyglada_na_szyfrogram(wartosc) -> bool:
    return isinstance(wartosc, str) and wartosc.startswith(PREFIKS_SZYFROGRAMU)


class NieodszyfrowanaWartosc(str):
    """Pusta wartość zastępująca szyfrogram, którego nie da się odczytać.

    Dla kodu aplikacji zachowuje się jak ``""`` (pusty, fałszywy), ale
    pamięta oryginalny szyfrogram — ponowny zapis rekordu (np. formularz
    admina z innym polem zmienionym) zapisze z powrotem ten sam szyfrogram,
    zamiast nadpisać go pustą wartością. Po przywróceniu właściwego klucza
    wartość znów będzie czytelna.
    """

    def __new__(cls, szyfrogram):
        obj = super().__new__(cls, "")
        obj.szyfrogram = szyfrogram
        return obj

    def __reduce__(self):
        return (NieodszyfrowanaWartosc, (self.szyfrogram,))


def zaszyfruj(wartosc: str) -> str:
    """Szyfruje wartość, gdy jest klucz; bez klucza zwraca ją bez zmian."""
    mf = multifernet()
    if mf is None:
        logger.warning(
            "Brak klucza DJANGO_BPP_FIELD_ENCRYPTION_KEY — sekret integracji "
            "zapisano w bazie bez szyfrowania."
        )
        return wartosc
    return mf.encrypt(wartosc.encode()).decode()


def odszyfruj(wartosc: str) -> str:
    """Odszyfrowuje szyfrogram; wartość jawną (sprzed szyfrowania) zwraca
    wprost. Nieodszyfrowalny szyfrogram → :class:`NieodszyfrowanaWartosc`.
    """
    if not wyglada_na_szyfrogram(wartosc):
        return wartosc
    try:
        mf = multifernet()
        if mf is None:
            raise InvalidToken
        return mf.decrypt(wartosc.encode()).decode()
    except (InvalidToken, ImproperlyConfigured):
        logger.warning(
            "Nie udało się odszyfrować EncryptedTextField (brak/zły klucz "
            "DJANGO_BPP_FIELD_ENCRYPTION_KEY lub uszkodzony szyfrogram) — "
            "zwracam pustą wartość."
        )
        return NieodszyfrowanaWartosc(wartosc)


class EncryptedTextField(models.TextField):
    """TextField szyfrujący wartość (Fernet/MultiFernet) w drodze do bazy.

    W DB leży base64 szyfrogramu, w Pythonie zwraca plaintext.
    Pola NIE da się filtrować/sortować po wartości (każdy szyfrogram inny);
    działa jedynie porównanie z pustym napisem (``""`` nie jest szyfrowany).

    Bez skonfigurowanego klucza wartość jest zapisywana jawnie (z
    ostrzeżeniem), a przy odczycie wartości jawne są rozpoznawane i
    zwracane wprost — instalacje bez klucza działają dalej, a po dodaniu
    klucza ``manage.py zaszyfruj_sekrety`` szyfruje zapisane wartości.
    """

    def get_prep_value(self, value):
        if value is None or value == "":
            if isinstance(value, NieodszyfrowanaWartosc):
                return value.szyfrogram
            return value
        value = str(value)
        if wyglada_na_szyfrogram(value):
            # Już zaszyfrowane (np. surowa wartość przepisywana 1:1) —
            # nie szyfruj drugi raz.
            return value
        return zaszyfruj(value)

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        return odszyfruj(value)

    def to_python(self, value):
        # Wartość z serializacji (historia zmian, fixtures) przychodzi jako
        # szyfrogram — odszyfruj; wartości jawne przechodzą bez zmian.
        if isinstance(value, str) and wyglada_na_szyfrogram(value):
            return odszyfruj(value)
        return super().to_python(value)

    def value_to_string(self, obj):
        # Serializacja (django-reversion, dumpdata) zapisuje szyfrogram, a nie
        # wartość jawną — sekret nie trafia jawnym tekstem do historii zmian.
        return self.get_prep_value(self.value_from_object(obj))
