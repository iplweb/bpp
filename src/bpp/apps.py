# -*- encoding: utf-8 -*-

from django.apps import AppConfig


class BppConfig(AppConfig):
    name = "bpp"
    verbose_name = "Biblioteka Publikacji Pracowników"

    def ready(self):
        from django.db.models.signals import post_migrate

        from bpp.system import odtworz_grupy, ustaw_robots_txt

        post_migrate.connect(ustaw_robots_txt, sender=self)
        post_migrate.connect(odtworz_grupy, sender=self)
