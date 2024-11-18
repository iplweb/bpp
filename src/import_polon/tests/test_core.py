from pathlib import Path

import pytest
from model_bakery import baker

from import_polon.core import analyze_excel_file_import_polon
from import_polon.models import ImportPlikuPolon


@pytest.fixture
def fn_test_import_polon():
    return Path(__file__).parent / "test_import_polon.xlsx"


@pytest.mark.django_db
def test_analyze_excel_file_import_polon(fn_test_import_polon):
    ipp = baker.make(ImportPlikuPolon)
    analyze_excel_file_import_polon(fn_test_import_polon, ipp)
