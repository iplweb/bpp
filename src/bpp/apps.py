# -*- encoding: utf-8 -*-

from django.conf import settings
from django.apps import AppConfig
import django

class BppConfig(AppConfig):
    name = 'bpp'
    verbose_name = 'Biblioteka Publikacji Pracowników'

    def ready(self):
        if not settings.TESTING:
            from bpp.models import cache
            cache.enable()

        from django.db.models.signals import post_migrate
        from bpp.system import ustaw_robots_txt, odtworz_grupy
        post_migrate.connect(ustaw_robots_txt, sender=self)
        post_migrate.connect(odtworz_grupy, sender=self)