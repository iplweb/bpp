# Create your models here.
from django.db import models

from long_running.models import Operation


class TestOperation(Operation):
    # long_running.tests.test_models
    pass


class TestObjectThatDoesNotExistManager(models.Manager):
    # long_running.tests.test_tasks
    def get(self, *args, **kw):
        # Those objects never exist
        raise TestObjectThatDoesNotExist.DoesNotExist


class TestObjectThatDoesNotExist(models.Model):
    objects = TestObjectThatDoesNotExistManager()
