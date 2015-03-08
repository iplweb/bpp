# -*- encoding: utf-8 -*-

from django.conf import settings
from django.apps import AppConfig

class BppConfig(AppConfig):
    name = 'bpp'
    verbose_name = 'Biblioteka Publikacji Pracowników'

    def ready(self):
        if not settings.TESTING:
            from bpp.models import cache
            cache.enable()

