# Create your models here.
from django.db import models

from long_running.models import Operation


class TestOperation(Operation):
    __test__ = False  # pytest: nie kolekcjonuj jako testu

    # long_running.tests.test_models


class TestObjectThatDoesNotExistManager(models.Manager):
    # long_running.tests.test_tasks
    def get(self, *args, **kw):
        # Those objects never exist
        raise TestObjectThatDoesNotExist.DoesNotExist


class TestObjectThatDoesNotExist(models.Model):
    __test__ = False  # pytest: nie kolekcjonuj jako testu

    objects = TestObjectThatDoesNotExistManager()
