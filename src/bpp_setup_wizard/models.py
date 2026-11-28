"""Stan kroku „Dane demonstracyjne” kreatora pierwszego uruchomienia.

``KreatorDanychDemo`` — singleton (pk=1): odpowiedź „nie, bez danych demo”
oraz wiersz, który blokujemy (``select_for_update``) przy starcie
generowania, żeby dwa kliknięcia / dwie karty nie uruchomiły go dwa razy.

``GenerowanieDanychDemo`` — operacja ``django-liveops`` generująca dane demo
w tle (worker Celery, tak jak inne długie operacje BPP). Postęp zapisujemy
w polach ``percent`` / ``status_text`` operacji, więc strona postępu
kreatora odpytuje zwykły widok JSON i nie zależy od WebSocketów.
"""

from __future__ import annotations

from django.db import models
from liveops.models import LiveOperation


class KreatorDanychDemo(models.Model):
    ODPOWIEDZ_NIE = "nie"

    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    odpowiedz = models.CharField(max_length=8, blank=True, default="")
    odpowiedziano = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "kreator — decyzja o danych demo"
        verbose_name_plural = "kreator — decyzje o danych demo"

    def __str__(self) -> str:
        return f"KreatorDanychDemo(odpowiedz={self.odpowiedz!r})"

    @classmethod
    def load(cls) -> KreatorDanychDemo:
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @classmethod
    def zablokuj(cls) -> KreatorDanychDemo:
        """Wiersz-singleton z blokadą do końca bieżącej transakcji."""
        cls.objects.get_or_create(pk=1)
        return cls.objects.select_for_update().get(pk=1)


class GenerowanieDanychDemo(LiveOperation):
    motyw = models.CharField(max_length=32)

    # Bezpiecznik po stronie workera: przebieg „przejmuje” operację
    # warunkowym UPDATE-em, więc powtórzone dostarczenie zadania Celery
    # nie wygeneruje drugiego kompletu danych.
    przejete = models.BooleanField(default=False)
    postep_zaktualizowano = models.DateTimeField(null=True, blank=True)
    manifest = models.CharField(max_length=512, blank=True, default="")

    # Po błędzie: czy częściowo wygenerowane dane udało się usunąć (wtedy
    # kreator wraca do pytania o dane demo) i czy administrator przyjął
    # do wiadomości błąd, po którym dane zostały w bazie.
    dane_usuniete = models.BooleanField(null=True, blank=True)
    blad_zaakceptowany = models.BooleanField(default=False)

    class Meta(LiveOperation.Meta):
        verbose_name = "generowanie danych demo"
        verbose_name_plural = "generowanie danych demo"

    def __str__(self) -> str:
        return f"Generowanie danych demo ({self.motyw}, {self.get_state()})"

    def run(self, p) -> None:
        from bpp_setup_wizard.dane_demo import generuj_dane_demo

        generuj_dane_demo(self, p)

    @property
    def w_toku(self) -> bool:
        return self.finished_on is None and not self.cancelled

    @property
    def ostatnia_linia_bledu(self) -> str:
        if not self.traceback:
            return ""
        linie = [linia for linia in self.traceback.splitlines() if linia.strip()]
        return linie[-1] if linie else ""
