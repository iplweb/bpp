import pytest
from django.core.exceptions import ValidationError

from ewaluacja2021 import const
from ewaluacja2021.tests.utils import curdir
from ewaluacja2021.validators import validate_xlsx, xlsx_header_validator


def test_validate_xlsx_bad():
    class FakeFile:
        name = __name__

    with pytest.raises(ValidationError):
        validate_xlsx(FakeFile)

    FakeFile.name = "unexistent"

    with pytest.raises(ValidationError):
        validate_xlsx(FakeFile)


def test_validate_xlsx_good():
    class FakeFile:
        name = curdir("default.xlsx")

    validate_xlsx(FakeFile)


def test_xlsx_header_validator_bad():
    class FakeFile:
        name = curdir("test_file_header_bad.xlsx")

    validator = xlsx_header_validator(const.IMPORT_MAKSYMALNYCH_SLOTOW_COLUMNS)

    with pytest.raises(ValidationError):
        validator(FakeFile)

    FakeFile.name = "unexistent"

    with pytest.raises(ValidationError):
        validator(FakeFile)


def test_xlsx_header_validator_good():
    class FakeFile:
        name = curdir("default.xlsx")

    validator = xlsx_header_validator(const.IMPORT_MAKSYMALNYCH_SLOTOW_COLUMNS)
    validator(FakeFile)
