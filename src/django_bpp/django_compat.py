"""Compatibility shims for old Django migrations.

These shims restore APIs that were removed in Django 5.0 but are still
referenced by migration files under src/*/migrations/ (which must stay
immutable per CLAUDE.md). Applied before the migration graph is built.
"""

import datetime

import django.utils.timezone
from django.db import models

# django.utils.timezone.utc was removed in Django 5.0. Used by
# src/rozbieznosci_if/migrations/0002_auto_20210323_0106.py.
if not hasattr(django.utils.timezone, "utc"):
    django.utils.timezone.utc = datetime.timezone.utc


# models.NullBooleanField was removed in Django 5.0. Used by many old
# migrations (bpp/0119, 0239, 0270, 0271; integrator2/0001;
# import_pracownikow/0003, 0004; ewaluacja2021/0003; pbn_api/0012, 0031).
# (Note: the historical `tee/0004` migration also used it, but the `tee`
# app has been extracted to the standalone `django-tee` package whose
# migrations were rewritten without NullBooleanField. The shim is no
# longer needed for `tee` but is still required by the apps listed
# above.) The replacement is BooleanField(null=True, default=None) —
# we return a BooleanField subclass that applies those kwargs so the
# migrations' frozen field definitions load unchanged.
if not hasattr(models, "NullBooleanField"):

    class NullBooleanField(models.BooleanField):
        def __init__(self, *args, **kwargs):
            kwargs["null"] = True
            kwargs.setdefault("blank", True)
            kwargs.setdefault("default", None)
            super().__init__(*args, **kwargs)

        def deconstruct(self):
            name, path, args, kwargs = super().deconstruct()
            # Normalise so `makemigrations` can't silently re-serialize
            # the historical migrations using the new (removed) class.
            path = "django.db.models.BooleanField"
            return name, path, args, kwargs

    models.NullBooleanField = NullBooleanField
