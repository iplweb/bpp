from django.contrib.auth import get_user_model
from django.db import models

from bpp.models.fields import TupleField


class OptymalizacjaPublikacji(models.Model):
    """Model to track publication optimization sessions"""

    publikacja_id = TupleField(models.IntegerField(), size=2, db_index=True)
    utworzono = models.DateTimeField(auto_now_add=True)
    zmodyfikowano = models.DateTimeField(auto_now=True)
    uzytkownik = models.ForeignKey(
        get_user_model(), on_delete=models.SET_NULL, null=True, blank=True
    )
    notatki = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Optymalizacja publikacji"
        verbose_name_plural = "Optymalizacje publikacji"
        ordering = ["-utworzono"]

    def __str__(self):
        return f"Optymalizacja: {self.publikacja_id} ({self.utworzono})"


class HistoriaZmianDyscypliny(models.Model):
    """Track discipline pinning/unpinning history"""

    optymalizacja = models.ForeignKey(
        OptymalizacjaPublikacji, on_delete=models.CASCADE, related_name="historia_zmian"
    )
    autor = models.ForeignKey("bpp.Autor", on_delete=models.CASCADE)
    jednostka = models.ForeignKey("bpp.Jednostka", on_delete=models.CASCADE)
    dyscyplina = models.ForeignKey("bpp.Dyscyplina_Naukowa", on_delete=models.CASCADE)
    rekord_id = TupleField(models.IntegerField(), size=2, db_index=True)
    akcja = models.CharField(
        max_length=20, choices=[("pin", "Przypięto"), ("unpin", "Odpięto")]
    )
    punkty_przed = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True
    )
    punkty_po = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True
    )
    sloty_przed = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True
    )
    sloty_po = models.DecimalField(
        max_digits=10, decimal_places=4, null=True, blank=True
    )
    utworzono = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Historia zmiany dyscypliny"
        verbose_name_plural = "Historie zmian dyscyplin"
        ordering = ["-utworzono"]

    def __str__(self):
        return f"{self.autor} - {self.dyscyplina} - {self.akcja} ({self.utworzono})"
