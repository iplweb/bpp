import logging

from bpp.models import Autor, Uczelnia
from bpp.models.profile import BppUser

logger = logging.getLogger(__name__)


class OrcidAuthenticationBackend:
    """Authenticate users by matching an ORCID iD to an existing
    Autor record, then finding the BppUser with the same email.
    """

    def authenticate(self, request, orcid_id=None, **kwargs):
        if orcid_id is None:
            return None

        try:
            autor = Autor.objects.get(orcid=orcid_id)
        except Autor.DoesNotExist:
            logger.info("ORCID login: no Autor with orcid=%s", orcid_id)
            return None

        if not autor.email:
            logger.info(
                "ORCID login: Autor pk=%s has no email, cannot match to BppUser",
                autor.pk,
            )
            return None

        try:
            user = BppUser.objects.get(email=autor.email)
        except BppUser.DoesNotExist:
            logger.info(
                "ORCID login: no BppUser with email=%s (Autor pk=%s)",
                autor.email,
                autor.pk,
            )
            return None

        if not user.is_active:
            logger.info(
                "ORCID login: user pk=%s is inactive",
                user.pk,
            )
            return None

        uczelnia = Uczelnia.objects.get_for_request(request)
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
