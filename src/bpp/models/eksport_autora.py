"""Model zadania asynchronicznego eksportu publikacji autora (§3.3).

Eksport BibTeX/RIS jest budowany w tle przez Celery i pobierany dopiero
gdy gotowy. Strony są PUBLICZNE (anonimowe) — dlatego klucz główny to
nieodgadywalny UUID, a autoryzacja statusu/pobrania odbywa się wyłącznie
przez ten klucz (nie przez właściciela; właściciela nie ma).
"""

import uuid

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
    ]
    #: Rozszerzenie pliku per format (równe wartości formatu, ale jawnie).
    FORMAT_EXTENSIONS = {"bib": "bib", "ris": "ris"}
    #: Typ MIME zwracany przy pobraniu, per format.
    FORMAT_CONTENT_TYPES = {
        "bib": "application/x-bibtex; charset=utf-8",
        "ris": "application/x-research-info-systems; charset=utf-8",
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    autor = models.ForeignKey("bpp.Autor", on_delete=models.CASCADE)
    format = models.CharField(max_length=3, choices=FORMAT_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    result_file = models.FileField(
        upload_to="protected/eksport_autora/",
        null=True,
        blank=True,
    )
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
