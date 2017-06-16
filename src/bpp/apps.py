# -*- encoding: utf-8 -*-

from django.conf import settings
from django.apps import AppConfig
import django

if django.VERSION < (1,10):
    from django.db.migrations import executor

class BppConfig(AppConfig):
    name = 'bpp'
    verbose_name = u'Biblioteka Publikacji Pracowników'

    def ready(self):
        if not settings.TESTING:
            from bpp.models import cache
            cache.enable()

        if django.VERSION < (1,10):
            from django_18_fast_migrations import migration_executor_patched
            migration_executor_patched.monkeypatch(executor)

        from django.db.models.signals import post_migrate
        from bpp.system import ustaw_robots_txt, odtworz_grupy
        post_migrate.connect(ustaw_robots_txt, sender=self)
        post_migrate.connect(odtworz_grupy, sender=self)
