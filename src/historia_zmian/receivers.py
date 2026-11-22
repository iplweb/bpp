"""Zapis źródła zmiany dla każdej rewizji (FD#587)."""

from django.dispatch import receiver
from reversion.signals import post_revision_commit

from bpp.zrodlo_zmian import biezace_zrodlo_zmian, wersje_zapisane_hurtowo

from .models import ZrodloZmiany


@receiver(post_revision_commit, dispatch_uid="historia_zmian.zrodlo_rewizji")
def zapisz_zrodlo_rewizji(sender, revision, versions, **kwargs):
    ZrodloZmiany.objects.create(rewizja=revision, **biezace_zrodlo_zmian())


@receiver(wersje_zapisane_hurtowo, dispatch_uid="historia_zmian.zrodlo_hurtowe")
def zapisz_zrodlo_rewizji_hurtowo(sender, rewizje, **kwargs):
    zrodlo = biezace_zrodlo_zmian()
    ZrodloZmiany.objects.bulk_create(
        [ZrodloZmiany(rewizja=rewizja, **zrodlo) for rewizja in rewizje]
    )
