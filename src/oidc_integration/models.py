from django.conf import settings
from django.db import models


class OIDCIdentity(models.Model):
    """Trwałe wiązanie konta BPP z tożsamością OIDC (issuer, sub).

    ``sub`` jest niezmienny i nadany przez IdP — w przeciwieństwie do e-maila
    nie da się go „wpisać". Dopasowanie konta po tej parze (zamiast po
    e-mailu) zamyka przejęcie konta przez zmianę adresu w realmie.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="oidc_identities",
    )
    issuer = models.CharField(max_length=255)
    sub = models.CharField(max_length=255)
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "tożsamość OIDC"
        verbose_name_plural = "tożsamości OIDC"
        constraints = [
            models.UniqueConstraint(
                fields=["issuer", "sub"], name="uniq_oidc_identity"
            ),
            models.UniqueConstraint(
                fields=["user", "issuer"], name="uniq_user_per_issuer"
            ),
        ]

    def __str__(self):
        return f"{self.user} @ {self.issuer}"
