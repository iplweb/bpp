import pytest
from model_bakery import baker

from test_bpp.models import TestOperation, TestReport


@pytest.fixture
def operation(admin_user):
    return TestOperation.objects.create(owner=admin_user)


@pytest.fixture
def report(db):
    return baker.make(TestReport)
