"""
Modele abstrakcyjne związane z adresami WWW.
"""

from django.db import models
from django.urls.base import reverse

from bpp import const


class ModelZWWW(models.Model):
    """Model zawierający adres strony WWW"""

    www = models.URLField(
        const.WWW_FIELD_LABEL,
        max_length=1024,
        blank=True,
        default="",
    )
    dostep_dnia = models.DateField(
        "Dostęp dnia (płatny dostęp)",
        blank=True,
        null=True,
        help_text="""Data dostępu do strony WWW.""",
    )

    public_www = models.URLField(
        const.PUBLIC_WWW_FIELD_LABEL,
        max_length=2048,
        blank=True,
        default="",
    )
    public_dostep_dnia = models.DateField(
        "Dostęp dnia (wolny dostęp)",
        blank=True,
        null=True,
        help_text="""Data wolnego dostępu do strony WWW.""",
    )

    class Meta:
        abstract = True


class ModelZAbsolutnymUrl:
    def get_absolute_url(self):
        from django.contrib.contenttypes.models import ContentType

        if hasattr(self, "slug") and self.slug:
            return reverse("bpp:browse_praca_by_slug", args=(self.slug,))

        return reverse(
            "bpp:browse_praca",
            args=(ContentType.objects.get_for_model(self).pk, self.pk),
        )
