from .base import BasePBNMongoDBModel


class Conference(BasePBNMongoDBModel):
    class Meta:
        verbose_name = "Konferencja w PBN API"
        verbose_name_plural = "Konferencje w PBN API"

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
