from datetime import timedelta

import pytest

from fixtures import *  # noqa


@pytest.fixture(scope="session")
def today():
    from django.utils import timezone

    return timezone.now().date()


@pytest.fixture(scope="session")
def yesterday(today):
    return today - timedelta(days=1)
