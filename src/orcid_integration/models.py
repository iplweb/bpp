from django.conf import settings
from django.db import models


class ORCIDIdentity(models.Model):
    """Trwałe wiązanie konta BPP z tożsamością ORCID (issuer, ORCID iD).

    ORCID iD (``sub``) jest zweryfikowany przez przepływ OAuth (użytkownik
    faktycznie zalogował się do ORCID) i — w przeciwieństwie do ``Autor.email``
    czy ``Autor.orcid`` — nie da się go „wpisać" w edytowalnym rekordzie autora.
    Dopasowanie konta po tej parze (zamiast po e-mailu przepisanym z ``Autor``)
    zamyka przejęcie konta przez redaktora z uprawnieniem ``change_autor``.

    ``issuer`` = ``Uczelnia.orcid_base_url`` (``https://orcid.org`` vs
    ``https://sandbox.orcid.org``) — jedyne realne rozróżnienie „środowiska":
    tożsamość z sandboxa nie może zalogować na produkcji i odwrotnie.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orcid_identities",
    )
    issuer = models.CharField(max_length=255)
    sub = models.CharField("ORCID iD", max_length=255)
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "tożsamość ORCID"
        verbose_name_plural = "tożsamości ORCID"
        constraints = [
            models.UniqueConstraint(
                fields=["issuer", "sub"], name="uniq_orcid_identity"
            ),
            models.UniqueConstraint(
                fields=["user", "issuer"], name="uniq_user_per_orcid_issuer"
            ),
        ]

    def __str__(self):
        return f"{self.user} @ {self.issuer} ({self.sub})"
