from pathlib import Path

import pytest

TESTDATA = Path(__file__).parent / "testdata"


@pytest.fixture
def jcr_xlsx_path():
    return str(TESTDATA / "jcr_fd388.xlsx")


@pytest.fixture
def jcr_csv_path():
    return str(TESTDATA / "jcr_fd388.csv")
