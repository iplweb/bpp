from decimal import Decimal, InvalidOperation

from django import forms
from django.core.exceptions import ValidationError
from django.db import models

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
            raise ValidationError(self.error_messages["invalid"])


class DOIField(models.CharField):
    def __init__(self, *args, **kw):
        if "help_text" not in kw:
            kw["help_text"] = "Digital Object Identifier (DOI)"

        if "max_length" not in kw:
            kw["max_length"] = 2048

        super().__init__(*args, **kw)
