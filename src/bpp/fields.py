import logging
from decimal import Decimal, InvalidOperation

from cryptography.fernet import Fernet, InvalidToken
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


def _fernet() -> Fernet:
    key = getattr(settings, "DSPACE_CREDENTIALS_KEY", "")
    if not key:
        raise ImproperlyConfigured(
            "DSPACE_CREDENTIALS_KEY nie jest ustawiony — nie mogę "
            "szyfrować/odszyfrować pól EncryptedTextField."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


class EncryptedTextField(models.TextField):
    """TextField szyfrujący wartość (Fernet) w drodze do bazy.

    W DB leży base64 szyfrogramu, w Pythonie zwraca plaintext.
    Pola NIE da się filtrować/sortować po wartości (każdy szyfrogram inny).
    """

    def get_prep_value(self, value):
        if value is None or value == "":
            return value
        return _fernet().encrypt(str(value).encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        try:
            return _fernet().decrypt(value.encode()).decode()
        except (InvalidToken, ImproperlyConfigured):
            logger.warning(
                "Nie udało się odszyfrować EncryptedTextField "
                "(zły/brak DSPACE_CREDENTIALS_KEY lub uszkodzony szyfrogram) "
                "— zwracam pustą wartość."
            )
            return ""
