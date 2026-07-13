import logging

from bpp.models import Uczelnia
from bpp.models.profile import BppUser

from .models import ORCIDIdentity

logger = logging.getLogger(__name__)


class OrcidAuthenticationBackend:
    """Uwierzytelnia po powiązanej tożsamości ORCID (issuer, ORCID iD).

    Konto NIE jest już wybierane po ``Autor.email`` — ten adres jest edytowalny
    przez redaktorów (grupa „wprowadzanie danych" ma ``change_autor``), więc
    dawał przejęcie konta: wystarczyło wpisać w rekordzie ``Autor`` swój ORCID
    i e-mail administratora. Teraz login rozwiązuje się do konta wyłącznie przez
    ``ORCIDIdentity`` — wiązaną świadomie z poziomu profilu (re-auth hasłem).
    """

    def _issuer_for(self, request, orcid_issuer, uczelnia):
        """Ustal issuera (środowisko ORCID) — jawny argument albo z uczelni."""
        if orcid_issuer:
            return orcid_issuer
        if uczelnia is not None:
            return uczelnia.orcid_base_url
        return None

    def authenticate(
        self, request, orcid_id=None, orcid_issuer=None, username=None, **kwargs
    ):
        if orcid_id is None:
            return None

        uczelnia = Uczelnia.objects.get_for_request(request)
        issuer = self._issuer_for(request, orcid_issuer, uczelnia)
        if not issuer:
            logger.info(
                "ORCID login: brak issuera (uczelni w requeście) — "
                "nie mogę dopasować tożsamości dla orcid=%s",
                orcid_id,
            )
            return None

        identity = (
            ORCIDIdentity.objects.filter(
                issuer=issuer, sub=orcid_id, user__is_active=True
            )
            .select_related("user")
            .first()
        )
        if identity is None:
            logger.info(
                "ORCID login: brak powiązanej tożsamości (issuer=%s, orcid=%s)",
                issuer,
                orcid_id,
            )
            return None

        user = identity.user

        if uczelnia and uczelnia.orcid_tylko_dla_pracownikow:
            if not (user.is_staff or user.is_superuser):
                logger.info(
                    "ORCID login: user pk=%s denied — "
                    "orcid_tylko_dla_pracownikow is enabled "
                    "and user is not staff/superuser",
                    user.pk,
                )
                return None

        return user

    def get_user(self, user_id):
        try:
            return BppUser.objects.get(pk=user_id)
        except BppUser.DoesNotExist:
            return None
