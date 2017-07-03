# -*- encoding: utf-8 -*-
"""
Profile użytkowników serwisu BPP
"""

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import AbstractUser, UserManager

from bpp.models import ModelZAdnotacjami


class BppUserManager(UserManager):
    model = 'bpp.BppUser'
    pass


class BppUser(AbstractUser, ModelZAdnotacjami):
    active_charmap_tab = models.IntegerField(default=0)

    per_page = models.IntegerField(
        'Ilość wyświetlanych rekordów na stronie',
        default=20)

    multiseek_format = models.CharField(
        'Ostatnio wybrany format wyświetlania w Multiseeku',
        max_length=200, null=True, blank=True)

    multiseek_order_1 = models.CharField(
        'Ostatnio wybrane pole sortowania w Multiseeku',
        max_length=200, null=True, blank=True
    )

    class Meta:
        app_label = 'bpp'
        verbose_name = 'użytkownik'
        verbose_name_plural = 'użytkownicy'

    objects = BppUserManager()
