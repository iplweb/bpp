from django.db import models

from pbn_api.models import Scientist

from django.contrib.auth import get_user_model

User = get_user_model()


class DoNotRemind(models.Model):
    """Model to track PBN Scientists that should be permanently ignored"""

    scientist = models.OneToOneField(
        Scientist,
        on_delete=models.CASCADE,
        verbose_name="Naukowiec PBN",
        related_name="do_not_remind",
    )
    ignored_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data ignorowania",
    )
    ignored_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Ignorowany przez",
    )
    reason = models.TextField(
        blank=True,
        verbose_name="Powód ignorowania",
        help_text="Opcjonalny powód ignorowania tego naukowca",
    )

    class Meta:
        verbose_name = "Ignorowany naukowiec PBN"
        verbose_name_plural = "Ignorowani naukowcy PBN"
        ordering = ["-ignored_at"]

    def __str__(self):
        return f"{self.scientist} (ignorowany {self.ignored_at.strftime('%Y-%m-%d')})"
