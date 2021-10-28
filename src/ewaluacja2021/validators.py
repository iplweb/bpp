import openpyxl
from django.core.exceptions import ValidationError
from django.db import models
from openpyxl.utils.exceptions import InvalidFileException

from ewaluacja2021.util import find_header_row


def validate_xlsx(obj: models.FileField):
    try:
        return openpyxl.load_workbook(obj)
    except InvalidFileException as e:
        raise ValidationError(f"Nieobsługiwany rodzaj pliku ({e}) ")
    except BaseException as e:
        raise ValidationError(f"Błąd przy próbie otwarcia pliku ({e})")


class xlsx_header_validator:
    """Upewnia się, że plik XLS ma zadany nagłówek.

    Dodatkowo, ten validator zapewnia również walidację typu pliku XLSX, ponieważ korzysta
    z funkcji ``validate_xls``"""

    def __init__(self, columns, max_header_row=100):
        """
        @param columns: kolumny w takiej kolejności, jaka powinna być w pliku XLS,
        może to być jedynie ich część (nie wszystkie), ale muszą być od początku;
        wielkość liter nie ma znaczenia, polskie litery mogą być usuwane.

        @param max_header_row: szukaj wiersza nagłówka maksymalnie do ``max_header_row``
        wierszy
        """
        self.cols = columns
        self.max_header_row = max_header_row

    def deconstruct(self):
        return (
            "ewaluacja2021.validators.xlsx_header_validator",
            (),
            {"columns": self.cols, "max_header_row": self.max_header_row},
        )

    def __eq__(self, other):
        return other.cols == self.cols and other.max_header_row == self.max_header_row

    def __call__(self, obj: models.FileField):
        wb = validate_xlsx(obj)
        header_row = find_header_row(
            wb.worksheets[0], header_row=self.cols, max_header_row=self.max_header_row
        )

        if header_row is not None:
            return True

        quoted_cols = [f'"{x}"' for x in self.cols]
        raise ValidationError(
            f"Nie znaleziono wiersza nagłówka wśród pierwszych {self.max_header_row} wierszy pierwszego arkusza "
            f"skoroszytu. Oczekiwany wiersz nagłówka powinien zaczynać się od pierwszej kolumny (kolumna 'A') "
            f"i zawierać następujące kolumny, w takiej kolejności, tak zatytułowane, bez przerw pomiędzy: "
            f"{', '.join(quoted_cols)}. "
        )
