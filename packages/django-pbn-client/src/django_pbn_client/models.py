"""Abstract Django models for PBN objects."""

import warnings

from django.db import models
from django.utils.functional import cached_property

MAX_TEXT_FIELD_LENGTH = 350


class BasePBNModel(models.Model):
    """Base timestamps shared by locally persisted PBN objects."""

    created_on = models.DateTimeField(auto_now_add=True)
    last_updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BasePBNMongoDBModel(BasePBNModel):
    """Abstract representation of a versioned object returned by PBN."""

    mongoId = models.CharField(max_length=32, primary_key=True)
    status = models.CharField(max_length=32, db_index=True, default="")
    verificationLevel = models.CharField(
        max_length=32,
        db_index=True,
        default="",
    )
    verified = models.BooleanField(default=False, db_index=True)
    versions = models.JSONField(default=list)

    # Field names copied from the current version's ``object`` dictionary.
    pull_up_on_save = None

    class Meta:
        abstract = True

    def save(
        self,
        force_insert=False,
        force_update=False,
        using=None,
        update_fields=None,
    ):
        if self.pull_up_on_save:
            self._pull_up_on_save()
        return super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def _pull_up_on_save(self):
        for attr in self.pull_up_on_save:
            pull_up = getattr(self, f"pull_up_{attr}", None)
            if pull_up is not None:
                value = pull_up()
            else:
                value = self.value_or_none("object", attr)

            if value is not None:
                if isinstance(value, str) and len(value) >= MAX_TEXT_FIELD_LENGTH:
                    value = value[:MAX_TEXT_FIELD_LENGTH]
                setattr(self, attr, value)

    @cached_property
    def current_version(self):
        """Return the version marked as current, if one exists."""
        if self.versions:
            for element in self.versions:
                if element.get("current"):
                    return element
        return None

    def value(self, *path, return_none=False):
        """Read a nested value from the current version."""
        value = self.current_version
        if value is None:
            warnings.warn(
                f"Model {self.__class__} with id {self.mongoId} "
                "has NO current_version!",
                stacklevel=2,
            )
            if return_none:
                return None
            return "[brak current_version]"

        for element in path:
            if element in value:
                value = value[element]
            else:
                if return_none:
                    return None
                return f"[brak {element}]"
        return value

    def value_or_none(self, *path):
        """Read a nested value, returning ``None`` when it is absent."""
        return self.value(*path, return_none=True)

    def website(self):
        """Return the website stored in the current object version."""
        return self.value("object", "website")
