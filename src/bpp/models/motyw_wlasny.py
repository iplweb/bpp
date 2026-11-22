"""Motyw zapisany przez konfigurator wyglądu („Zastosuj”).

CSS kompiluje przeglądarka administratora (tym samym SCSS-em co build, patrz
``motyw-konfig.js``), serwer go tylko przechowuje i serwuje pod
``bpp:motyw_wlasny_css``. Osobna tabela, a nie pola w ``Uczelnia``: uczelnia
jest ładowana przy każdym żądaniu, a CSS ma ~300 KB.
"""

import hashlib

from django.core.cache import cache
from django.db import models

# Wartość ``Uczelnia.theme_name`` oznaczająca motyw z konfiguratora.
MOTYW_WLASNY = "app-wlasny"


def _klucz_cache(uczelnia_id):
    return f"bpp:motyw_wlasny:skrot:{uczelnia_id}"


def _klucz_cache_trybu(uczelnia_id):
    return f"bpp:motyw_wlasny:tryb:{uczelnia_id}"


class MotywWlasny(models.Model):
    uczelnia = models.OneToOneField(
        "bpp.Uczelnia", on_delete=models.CASCADE, related_name="motyw_wlasny"
    )
    konfig = models.JSONField("Ustawienia zastosowanego motywu", null=True, blank=True)
    css = models.TextField("Skompilowany CSS", blank=True)
    # Zapisany, ale jeszcze niezastosowany motyw — np. gdy kompilator był
    # niedostępny albo motyw przygotował ktoś bez prawa „Zastosuj”.
    # „Zastosuj” go czyści; konfigurator wczytuje go na start.
    konfig_roboczy = models.JSONField(
        "Zapisane, niezastosowane ustawienia", null=True, blank=True
    )
    roboczy_zapisal = models.ForeignKey(
        "bpp.BppUser",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    roboczy_zapisano = models.DateTimeField(null=True, blank=True)
    skrot = models.CharField("Skrót CSS (wersja w adresie pliku)", max_length=64)
    # CSS powstał z SCSS-a tej wersji BPP. Po aktualizacji BPP nowe style
    # (nowe strony, komponenty) trafią do motywu dopiero po ponownym
    # „Zastosuj” w konfiguratorze — konfigurator o tym przypomina.
    wersja_bpp = models.CharField("Wersja BPP", max_length=50, blank=True)
    zmieniono = models.DateTimeField(auto_now=True)
    zmienil = models.ForeignKey(
        "bpp.BppUser", null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        verbose_name = "motyw z konfiguratora wyglądu"
        verbose_name_plural = "motywy z konfiguratora wyglądu"

    def __str__(self):
        return f"Motyw z konfiguratora wyglądu ({self.uczelnia})"

    def save(self, *args, **kwargs):
        # Sam motyw roboczy (bez zastosowanego CSS) nie ma pliku do serwowania.
        self.skrot = (
            hashlib.sha256(self.css.encode("utf-8")).hexdigest() if self.css else ""
        )
        # update_or_create zapisuje tylko pola z `defaults` (update_fields) —
        # skrót musi pójść razem z CSS-em, inaczej adres pliku się nie zmieni.
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and "css" in update_fields:
            kwargs["update_fields"] = set(update_fields) | {"skrot"}
        super().save(*args, **kwargs)
        cache.delete(_klucz_cache(self.uczelnia_id))
        cache.delete(_klucz_cache_trybu(self.uczelnia_id))

    @classmethod
    def skrot_dla(cls, uczelnia_id):
        """Skrót CSS-a uczelni (do adresu pliku) albo None — z cache."""
        klucz = _klucz_cache(uczelnia_id)
        skrot = cache.get(klucz)
        if skrot is None:
            skrot = (
                cls.objects.filter(uczelnia_id=uczelnia_id)
                .values_list("skrot", flat=True)
                .first()
            ) or ""
            cache.set(klucz, skrot, 3600)
        return skrot or None

    @classmethod
    def tryb_kolorow_dla(cls, uczelnia_id):
        """`tryb_kolorow` zastosowanego motywu („automatyczny”, „jasny”,
        „ciemny”) albo None — z cache. To tryb domyślny motywu; drugą wersję
        odwiedzający włącza pigułką ☀ | ☾ na pasku menu."""
        klucz = _klucz_cache_trybu(uczelnia_id)
        tryb = cache.get(klucz)
        if tryb is None:
            konfig = (
                cls.objects.filter(uczelnia_id=uczelnia_id)
                .exclude(css="")
                .values_list("konfig", flat=True)
                .first()
            )
            tryb = (konfig or {}).get("tryb_kolorow") or ""
            cache.set(klucz, tryb, 3600)
        return tryb or None


# Ile ostatnich zastosowanych wersji trzymamy na uczelnię (konfig z obrazkami
# ma do ~1 MB, więc bez historii w nieskończoność).
HISTORIA_MOTYWU_LIMIT = 10


class MotywWersja(models.Model):
    """Historia „Zastosuj” — do cofnięcia zmiany w konfiguratorze."""

    uczelnia = models.ForeignKey(
        "bpp.Uczelnia", on_delete=models.CASCADE, related_name="wersje_motywu"
    )
    konfig = models.JSONField("Ustawienia")
    # Motyw uczelni PRZED tym „Zastosuj” — pozwala wrócić do motywu sprzed
    # konfiguratora (np. app-green) bez kompilacji.
    motyw_przed = models.CharField(max_length=50, blank=True)
    zastosowano = models.DateTimeField(auto_now_add=True)
    zastosowal = models.ForeignKey(
        "bpp.BppUser", null=True, blank=True, on_delete=models.SET_NULL
    )
    wersja_bpp = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ("-zastosowano", "-pk")
        verbose_name = "wersja motywu z konfiguratora"
        verbose_name_plural = "wersje motywu z konfiguratora"

    def __str__(self):
        return f"Motyw {self.uczelnia} z {self.zastosowano:%Y-%m-%d %H:%M}"

    @classmethod
    def zapisz(cls, uczelnia, konfig, motyw_przed, uzytkownik, wersja_bpp):
        cls.objects.create(
            uczelnia=uczelnia,
            konfig=konfig,
            motyw_przed=motyw_przed or "",
            zastosowal=uzytkownik,
            wersja_bpp=wersja_bpp,
        )
        stare = cls.objects.filter(uczelnia=uczelnia).values_list("pk", flat=True)[
            HISTORIA_MOTYWU_LIMIT:
        ]
        cls.objects.filter(pk__in=list(stare)).delete()


class MotywZapisany(models.Model):
    """Motyw z konfiguratora zapisany pod nazwą („Zapisz jako…”) — do
    wczytania później. Nie zmienia strony."""

    uczelnia = models.ForeignKey(
        "bpp.Uczelnia", on_delete=models.CASCADE, related_name="motywy_zapisane"
    )
    nazwa = models.CharField("Nazwa", max_length=100)
    konfig = models.JSONField("Ustawienia")
    zapisano = models.DateTimeField(auto_now=True)
    zapisal = models.ForeignKey(
        "bpp.BppUser", null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        ordering = ("nazwa",)
        constraints = [
            models.UniqueConstraint(
                fields=("uczelnia", "nazwa"), name="motyw_zapisany_unikalna_nazwa"
            )
        ]
        verbose_name = "zapisany motyw z konfiguratora"
        verbose_name_plural = "zapisane motywy z konfiguratora"

    def __str__(self):
        return self.nazwa


class MotywPrzymiarka(models.Model):
    """CSS przymierzanego motywu (bpp/przymiarka_motywu.py). W sesji osoby
    przymierzającej jest tylko skrót; wpisy starsze niż doba są usuwane."""

    skrot = models.CharField(max_length=64, unique=True)
    css = models.TextField()
    utworzono = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "przymiarka motywu"
        verbose_name_plural = "przymiarki motywu"
