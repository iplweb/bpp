# Create your models here.
from django.db import models

from django.contrib.postgres.fields import JSONField


class BasePBNModel(models.Model):
    created_on = models.DateTimeField(auto_now_add=True)
    last_updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Language(BasePBNModel):
    code = models.CharField(max_length=5, primary_key=True)
    language = JSONField()


class Country(BasePBNModel):
    code = models.CharField(max_length=5, primary_key=True)
    description = models.CharField(max_length=200)


class BasePBNMongoDBModel(BasePBNModel):
    mongoId = models.CharField(max_length=32, primary_key=True)
    status = models.CharField(max_length=32, db_index=True)
    verificationLevel = models.CharField(max_length=32)
    verified = models.BooleanField(default=False)
    versions = JSONField()

    def current_version(self):
        for elem in self.versions:
            if elem["current"]:
                return elem

    class Meta:
        abstract = True


class Institution(BasePBNMongoDBModel):
    pass


class Conference(BasePBNMongoDBModel):
    pass


class Journal(BasePBNMongoDBModel):
    pass


class Publisher(BasePBNMongoDBModel):
    pass


class Sciencist(BasePBNMongoDBModel):
    pass


class Publication(BasePBNMongoDBModel):
    pass
