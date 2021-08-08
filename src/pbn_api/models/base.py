import warnings

from django.db import models

from django.contrib.postgres.fields import JSONField

from django.utils.functional import cached_property


class BasePBNModel(models.Model):
    created_on = models.DateTimeField(auto_now_add=True)
    last_updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


MAX_TEXT_FIELD_LENGTH = 512


class BasePBNMongoDBModel(BasePBNModel):
    mongoId = models.CharField(max_length=32, primary_key=True)
    status = models.CharField(max_length=32, db_index=True)
    verificationLevel = models.CharField(max_length=32)
    verified = models.BooleanField(default=False)
    versions = JSONField()

    # Nazwy pól wyciaganych "na wierzch" do pól obiektu
    # ze słownika JSONa (pole 'values')
    pull_up_on_save = None

    def _pull_up_on_save(self):
        for attr in self.pull_up_on_save:
            v = self.value_or_none("object", attr)
            if v is not None:
                # Tylko błędne rekordy (takie, które zawieraja pola dlugosci kilkudziesieciu kilobajtow)
                # zawieraja bardzo dlugie wpisy. Np jeden rekord w polu 'nazwisko' ma 10 kb nazwisk,
                # po przecinku. Oczywiscie, ze sa bledne. PostgreSQL jednakze ma limit na wielkosc
                # wiersza indeksu. I tego limitu bedziemy teraz przestrzegali:
                if len(v) >= MAX_TEXT_FIELD_LENGTH:
                    v = v[:MAX_TEXT_FIELD_LENGTH]
            setattr(self, attr, v)

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        if self.pull_up_on_save:
            self._pull_up_on_save()
        return super(BasePBNMongoDBModel, self).save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    @cached_property
    def current_version(self):
        if self.versions:
            for elem in self.versions:
                if elem["current"]:
                    return elem

    def value(self, *path, return_none=False):
        v = self.current_version
        if v is None:
            warnings.warn(
                f"Model {self.__class__} with id {self.mongoId} has NO current_version!"
            )
            if return_none:
                return
            return "[brak current_version]"

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
