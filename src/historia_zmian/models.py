"""Źródło zmiany zapisane przy każdej rewizji django-reversion (FD#587).

Rewizja reversion niesie użytkownika, datę i komentarz; tu dochodzi, SKĄD
przyszła zmiana (moduł redagowania, strona, import/narzędzie, API/MCP,
system) i — dla API/MCP — którą aplikacją OAuth. Pozwala przefiltrować np.
„wszystko, co zmienił agent X”. Historia jest trzymana bez limitu czasu.

Aplikacja OAuth jest zapisana jako ``client_id`` + nazwa (bez klucza
obcego): wpis historii przeżyje usunięcie aplikacji, a ``bpp`` nie zależy
od ``oauth2_provider``.
"""

from django.conf import settings
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


class ArchiwalnyPlik(models.Model):
    """Plik, który stracił odwołanie w bazie (FD#587, „wieczne pliki”).

    Pliki rekordów (repozytorium publikacji, zgłoszenia i ich załączniki)
    NIGDY nie są kasowane z dysku. Gdy wiersz z plikiem znika z bazy
    (trwałe usunięcie, także kaskadą z rekordu nadrzędnego) albo plik
    w polu zostaje podmieniony lub wyczyszczony, tu zostaje wpis: gdzie
    leży plik, jak się nazywał, do czego należał, kto i kiedy. Plik da się
    z archiwum pobrać.

    Wpis NIE przechowuje kopii — ``plik`` wskazuje ten sam plik na dysku
    (kopiowanie ani przenoszenie nie są potrzebne, bo nic go nie kasuje;
    przenoszenie zepsułoby przywracanie wersji, które pamiętają ścieżkę).
    """

    class Powody(models.TextChoices):
        USUNIETO_WIERSZ = "usunieto", "usunięto trwale z bazy"
        PODMIENIONO = "podmieniono", "podmieniono na inny plik"
        WYCZYSZCZONO = "wyczyszczono", "usunięto z pola"

    plik = models.FileField("plik", max_length=765)
    oryginalna_nazwa_pliku = models.CharField(
        "oryginalna nazwa pliku", max_length=512, blank=True, default=""
    )
    powod = models.CharField(
        "co się stało", max_length=16, choices=Powody.choices, db_index=True
    )
    rodzaj = models.CharField(
        "rodzaj", max_length=100, help_text="Model, do którego należał plik."
    )
    model_zrodlowy = models.CharField(
        "model źródłowy", max_length=100, db_index=True, editable=False
    )
    id_zrodlowe = models.CharField(
        "ID wiersza źródłowego", max_length=64, db_index=True, editable=False
    )
    opis = models.TextField(
        "należał do", blank=True, default="", help_text="Opis rekordu z chwili zmiany."
    )
    kto = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="kto",
    )
    kiedy = models.DateTimeField("kiedy", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "plik w archiwum"
        verbose_name_plural = "archiwum plików"
        ordering = ("-kiedy",)

    def __str__(self):
        return self.oryginalna_nazwa_pliku or self.plik.name.rsplit("/", 1)[-1]
