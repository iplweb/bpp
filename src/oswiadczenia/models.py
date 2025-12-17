from django.conf import settings
from django.db import models


class OswiadczeniaExportTask(models.Model):
    STATUS_CHOICES = [
        ("pending", "Oczekuje"),
        ("running", "W trakcie"),
        ("completed", "Zakończony"),
        ("failed", "Błąd"),
    ]
    FORMAT_CHOICES = [
        ("html", "HTML (ZIP)"),
        ("pdf", "PDF (ZIP)"),
        ("docx", "DOCX (ZIP)"),
        ("html_single", "HTML (jeden plik)"),
        ("pdf_single", "PDF (jeden plik)"),
        ("docx_single", "DOCX (jeden plik)"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    export_format = models.CharField(max_length=15, choices=FORMAT_CHOICES)

    # Filter parameters (stored for reproducibility)
    rok_od = models.IntegerField()
    rok_do = models.IntegerField()
    szukaj_autor = models.CharField(max_length=200, blank=True, default="")
    szukaj_tytul = models.CharField(max_length=200, blank=True, default="")
    dyscyplina_id = models.IntegerField(null=True, blank=True)
    przypieta = models.CharField(max_length=10, blank=True, default="")

    # Pagination for chunked exports
    offset = models.IntegerField(default=0)
    limit = models.IntegerField(default=5000)

    # Progress tracking
    total_items = models.IntegerField(default=0)
    processed_items = models.IntegerField(default=0)
    current_item = models.CharField(max_length=200, blank=True, default="")

    # Result
    result_file = models.FileField(
        upload_to="protected/oswiadczenia/",
        null=True,
        blank=True,
    )
    error_message = models.TextField(blank=True, default="")

    celery_task_id = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Export {self.export_format} ({self.status}) - {self.created_at}"

    @property
    def progress_percent(self):
        if self.total_items == 0:
            return 0
        return int((self.processed_items / self.total_items) * 100)
