# Create your models here.
from django.db import models

from django.contrib.postgres.fields import JSONField

from django.utils.functional import cached_property


class BasePBNModel(models.Model):
    created_on = models.DateTimeField(auto_now_add=True)
    last_updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Language(BasePBNModel):
    code = models.CharField(max_length=5, primary_key=True)
    language = JSONField()

    def __str__(self):
        return self.language.get("pl") or self.language.get("en") or self.code


class Country(BasePBNModel):
    code = models.CharField(max_length=5, primary_key=True)
    description = models.CharField(max_length=200)


class BasePBNMongoDBModel(BasePBNModel):
    mongoId = models.CharField(max_length=32, primary_key=True)
    status = models.CharField(max_length=32, db_index=True)
    verificationLevel = models.CharField(max_length=32)
    verified = models.BooleanField(default=False)
    versions = JSONField()

    @cached_property
    def current_version(self):
        if self.versions:
            for elem in self.versions:
                if elem["current"]:
                    return elem

    def value(self, *path, return_none=False):
        v = self.current_version
        for elem in path:
            if elem in v:
                v = v[elem]
            else:
                if return_none:
                    return None
                return f"[brak {elem}]"
        return v

    def value_or_none(self, *path):
        return self.value(*path, return_none=True)

    def website(self):
        return self.value("object", "website")

    class Meta:
        abstract = True


class Institution(BasePBNMongoDBModel):
    def name(self):
        return self.value("object", "name")

    def addressCity(self):
        return self.value("object", "addressCity")

    def addressStreet(self):
        return self.value("object", "addressStreet")

    def addressStreetNumber(self):
        return self.value("object", "addressStreetNumber")

    def addressPostalCode(self):
        return self.value("object", "addressPostalCode")

    def polonUid(self):
        return self.value("object", "polonUid")

    def __str__(self):
        v = self.current_version

        if v:
            v = v["object"]
            return (
                f"{self.name()}, "
                f"{self.addressCity()}, "
                f"{self.addressStreet()} {self.addressStreetNumber()} "
                f"(ID: {self.mongoId}, "
                f"PolonUid: {self.polonUid()}) "
            )

        return f"Instytucja PBN, ID={self.mongoId}, status={self.status}"


class Conference(BasePBNMongoDBModel):
    def fullName(self):
        return self.value("object", "fullName")

    def startDate(self):
        return self.value("object", "startDate")

    def endDate(self):
        return self.value("object", "endDate")

    def city(self):
        return self.value("object", "city")

    def country(self):
        return self.value("object", "country")

    def __str__(self):
        return f"{self.fullName()}, {self.startDate()}, {self.city()}"


class Journal(BasePBNMongoDBModel):
    def title(self):
        return self.value("object", "title")

    def websiteLink(self):
        return self.value("object", "websiteLink")

    def issn(self):
        return self.value("object", "issn")

    def eissn(self):
        return self.value("object", "eissn")

    def __str__(self):
        return f"{self.title()}, ISSN: {self.issn()}, EISSN: {self.eissn()}"


class Publisher(BasePBNMongoDBModel):
    def publisherName(self):
        return self.value("object", "publisherName")

    def mniswId(self):
        return self.value("object", "mniswId")

    def __str__(self):
        return f"{self.publisherName()}"


class Scientist(BasePBNMongoDBModel):
    def lastName(self):
        return self.value("object", "lastName")

    def name(self):
        return self.value("object", "name")

    def currentEmploymentsInstitutionDisplayName(self):
        return self.value("object", "currentEmployments", "institutionDisplayName")

    def pbnId(self):
        return self.value("object", "legacyIdentifiers")

    def tytul(self):
        return self.value("object", "qualifications")

    def orcid(self):
        return self.value("object", "orcid")

    def polonUid(self):
        return self.value("object", "polonUid")

    def __str__(self):
        return f"{self.lastName()} {self.name()}, {self.tytul()} (ID: {self.pk})"


class Publication(BasePBNMongoDBModel):
    def title(self):
        return self.value("object", "title")

    def type(self):
        return self.value("object", "type")

    def volume(self):
        return self.value("object", "volume")

    def year(self):
        return self.value("object", "year")

    def publicUri(self):
        return self.value("object", "publicUri")

    def doi(self):
        return self.value("object", "doi")

    def __str__(self):
        return f"{self.title()}, {self.year()}, {self.doi()}"
