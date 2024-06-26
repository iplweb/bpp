from pathlib import Path

import pytest
from model_bakery import baker

from fixtures.conftest import (
    NORMAL_DJANGO_USER_LOGIN,
    NORMAL_DJANGO_USER_PASSWORD,
    _webtest_login,
)
from import_dyscyplin.models import Import_Dyscyplin

from django.contrib.auth.models import Group

from bpp.const import GR_WPROWADZANIE_DANYCH


@pytest.fixture
def wprowadzanie_danych_user(normal_django_user):
    grp = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)[0]
    normal_django_user.groups.add(grp)
    return normal_django_user


@pytest.fixture
def wd_app(webtest_app, wprowadzanie_danych_user):
    return _webtest_login(
        webtest_app, NORMAL_DJANGO_USER_LOGIN, NORMAL_DJANGO_USER_PASSWORD
    )


@pytest.fixture
def parent_path():
    return Path(__file__).parent


@pytest.fixture
def test1_xlsx(parent_path):
    return str(parent_path / "test1.xlsx")


@pytest.fixture
def default_xlsx(parent_path):
    return str(
        parent_path / ".." / "static" / "import_dyscyplin" / "xlsx" / "default.xlsx"
    )


@pytest.fixture
def test2_bad_header_xlsx(parent_path):
    return str(parent_path / "test2_bad_header.xlsx")


@pytest.fixture
def test3_multiple_sheets_xlsx(parent_path):
    return str(parent_path / "test3_multiple_sheets.xlsx")


@pytest.fixture
def test4_kasowanie_xlsx(parent_path):
    return str(parent_path / "test4_kasowanie.xlsx")


@pytest.fixture
def test5_kasowanie_subdyscypliny(parent_path):
    return str(parent_path / "test5_kasowanie_subdyscypliny.xlsx")


@pytest.fixture
def conftest_py(parent_path):
    return str(parent_path / "conftest.py")


@pytest.fixture
def import_dyscyplin(db, rok):
    return baker.make(Import_Dyscyplin, rok=rok)
