"""
Modele abstrakcyjne związane z eksportem przez API.
"""

from django.db import models


class ModelOpcjonalnieNieEksportowanyDoAPI(models.Model):
    nie_eksportuj_przez_api = models.BooleanField(
        "Nie eksportuj przez API",
        default=False,
        db_index=True,
        help_text="Jeżeli zaznaczone, to ten rekord nie będzie dostępny przez JSON REST API",
    )

    class Meta:
        abstract = True
