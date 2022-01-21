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

    validate_xlsx(curdir("test_file.xlsx", __file__))


def test_xlsx_header_validator_bad():

    validator = xlsx_header_validator(const.IMPORT_MAKSYMALNYCH_SLOTOW_COLUMNS)

    with pytest.raises(ValidationError):
        validator(curdir("test_file_header_bad.xlsx", __file__))

    with pytest.raises(ValidationError):
        validator("unexsitent")


def test_xlsx_header_validator_good():

    validator = xlsx_header_validator(const.IMPORT_MAKSYMALNYCH_SLOTOW_COLUMNS)
    validator(curdir("test_file.xlsx", __file__))
