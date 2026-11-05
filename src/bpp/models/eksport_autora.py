"""Model zadania asynchronicznego eksportu publikacji autora (§3.3).

Eksport BibTeX/RIS/XLSX jest budowany w tle przez Celery i pobierany dopiero
gdy gotowy. Strony są PUBLICZNE (anonimowe) — dlatego klucz główny to
nieodgadywalny UUID, a autoryzacja statusu/pobrania odbywa się przez ten
klucz (nie przez właściciela; właściciela nie ma). Wyjątek: zadania
``tylko_dla_redakcji`` (pełny dorobek) są dostępne wyłącznie dla redakcji.
"""

import uuid

from django.contrib.postgres.fields import ArrayField
from django.db import models

__all__ = ["AutorEksportTask"]


class AutorEksportTask(models.Model):
    STATUS_CHOICES = [
        ("pending", "Oczekuje"),
        ("running", "W trakcie"),
        ("completed", "Zakończony"),
        ("failed", "Błąd"),
    ]
    FORMAT_CHOICES = [
        ("bib", "BibTeX"),
        ("ris", "RIS"),
        ("xlsx", "XLSX z punktacją"),
    ]
    #: Rozszerzenie pliku per format (równe wartości formatu, ale jawnie).
    FORMAT_EXTENSIONS = {"bib": "bib", "ris": "ris", "xlsx": "xlsx"}
    #: Typ MIME zwracany przy pobraniu, per format.
    FORMAT_CONTENT_TYPES = {
        "bib": "application/x-bibtex; charset=utf-8",
        "ris": "application/x-research-info-systems; charset=utf-8",
        "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    autor = models.ForeignKey("bpp.Autor", on_delete=models.CASCADE)
    format = models.CharField(max_length=4, choices=FORMAT_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    result_file = models.FileField(
        upload_to="protected/eksport_autora/",
        null=True,
        blank=True,
    )
    #: Statusy korekty wykluczane z eksportu — zakres widoczności ustalony
    #: w chwili startu (worker Celery nie ma requestu). Posortowane, bo
    #: wchodzą do deduplikacji zadań.
    ukryte_statusy = ArrayField(models.IntegerField(), default=list, blank=True)
    #: Zadanie zlecone przez redakcję (``moze_wprowadzac_dane``) z pełnym
    #: zakresem (bez wykluczania ukrytych statusów). Status i plik takiego
    #: zadania widzi wyłącznie redakcja — dla pozostałych 404.
    tylko_dla_redakcji = models.BooleanField(default=False)
    #: XLSX: czy dołożyć punktację autora (PKdAut, sloty). Ustalane przy
    #: starcie tą samą bramką co sekcja slotów na stronie autora
    #: (``pokazuj_raport_slotow_autor``); wchodzi do deduplikacji.
    z_punktacja_autora = models.BooleanField(default=False)
    #: XLSX: statusy korekty, dla których punktacji autora nie pokazujemy
    #: (kanał „sloty”) — jak w sekcji slotów strony autora.
    ukryte_statusy_slotow = ArrayField(models.IntegerField(), default=list, blank=True)
    #: Zadanie zlecone przez niezalogowanego użytkownika — liczone do
    #: globalnego limitu anonimowych zadań w kolejce
    #: (``settings.EKSPORT_AUTORA_LIMIT_ANON_W_KOLEJCE``).
    zlecone_anonimowo = models.BooleanField(default=False)
    error_message = models.TextField(blank=True, default="")
    celery_task_id = models.CharField(max_length=255, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Eksport {self.format} ({self.status}) - {self.created_at}"

    @property
    def nazwa_pliku(self) -> str:
        """Nazwa pliku do pobrania: ``<slug-autora>.<ext>``."""
        ext = self.FORMAT_EXTENSIONS.get(self.format, self.format)
        baza = self.autor.slug or f"autor-{self.autor_id}"
        return f"{baza}.{ext}"

    @property
    def content_type(self) -> str:
        """Typ MIME odpowiadający formatowi eksportu."""
        return self.FORMAT_CONTENT_TYPES[self.format]
