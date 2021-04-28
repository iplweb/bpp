# -*- encoding: utf-8 -*-
"""
Profile użytkowników serwisu BPP
"""

from django.db import models

from django.contrib.auth.models import AbstractUser, UserManager

from django.utils.functional import cached_property

from bpp.models import ModelZAdnotacjami


class BppUserManager(UserManager):
    model = "bpp.BppUser"


class BppUser(AbstractUser, ModelZAdnotacjami):
    active_charmap_tab = models.IntegerField(default=0)

    per_page = models.IntegerField(
        "Ilość wyświetlanych rekordów na stronie", default=20
    )

    multiseek_format = models.CharField(
        "Ostatnio wybrany format wyświetlania w Multiseeku",
        max_length=200,
        null=True,
        blank=True,
    )

    multiseek_order_1 = models.CharField(
        "Ostatnio wybrane pole sortowania w Multiseeku",
        max_length=200,
        null=True,
        blank=True,
    )

    pbn_token = models.CharField(max_length=128, null=True, blank=True)

    class Meta:
        app_label = "bpp"
        verbose_name = "użytkownik"
        verbose_name_plural = "użytkownicy"

    objects = BppUserManager()

    @cached_property
    def cached_groups(self):
        return self.groups.all()
