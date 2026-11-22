"""Źródło zmiany zapisane przy każdej rewizji django-reversion (FD#587).

Rewizja reversion niesie użytkownika, datę i komentarz; tu dochodzi, SKĄD
przyszła zmiana (moduł redagowania, strona, import/narzędzie, API/MCP,
system) i — dla API/MCP — którą aplikacją OAuth. Pozwala przefiltrować np.
„wszystko, co zmienił agent X”. Historia jest trzymana bez limitu czasu.

Aplikacja OAuth jest zapisana jako ``client_id`` + nazwa (bez klucza
obcego): wpis historii przeżyje usunięcie aplikacji, a ``bpp`` nie zależy
od ``oauth2_provider``.
"""

from django.db import models
from reversion.models import Revision

from bpp.zrodlo_zmian import ZRODLA_ZMIAN, ZRODLO_SYSTEM


class ZrodloZmiany(models.Model):
    rewizja = models.OneToOneField(
        Revision,
        on_delete=models.CASCADE,
        related_name="zrodlo_zmiany",
        verbose_name="rewizja",
    )
    zrodlo = models.CharField(
        "źródło zmiany",
        max_length=16,
        choices=ZRODLA_ZMIAN,
        default=ZRODLO_SYSTEM,
        db_index=True,
    )
    aplikacja_client_id = models.CharField(
        "aplikacja OAuth (client_id)", max_length=100, blank=True, db_index=True
    )
    aplikacja_nazwa = models.CharField(
        "aplikacja OAuth (nazwa)", max_length=255, blank=True
    )

    class Meta:
        verbose_name = "źródło zmiany"
        verbose_name_plural = "historia zmian (rewizje)"

    def __str__(self):
        opis = self.get_zrodlo_display()
        if self.aplikacja_nazwa:
            opis = f"{opis}: {self.aplikacja_nazwa}"
        return opis
