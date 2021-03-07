from pathlib import Path

import pytest


@pytest.fixture
def parent_path():
    return Path(__file__).parent


@pytest.fixture
def test1_xlsx(parent_path):
    return str(parent_path / "test1.xlsx")


@pytest.fixture
def default_xlsx(parent_path):
    return str(parent_path / "default.xlsx")


@pytest.fixture
def test2_bad_header_xlsx(parent_path):
    return str(parent_path / "test2_bad_header.xlsx")
