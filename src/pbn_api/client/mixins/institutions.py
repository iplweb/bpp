"""Institutions API mixins."""

import json

from pbn_api.const import (
    PBN_DELETE_PUBLICATION_STATEMENT,
    PBN_GET_INSTITUTION_PUBLICATIONS_V2,
    PBN_GET_INSTITUTION_STATEMENTS,
    PBN_POST_INSTITUTION_STATEMENTS_URL,
)
from pbn_api.exceptions import (
    CannotDeleteStatementsException,
    HttpException,
    ResourceLockedException,
)

from ..pagination import PageableResource


class InstitutionsMixin:
    """Mixin providing institution-related API methods."""

    def get_institutions(self, status="ACTIVE", *args, **kw):
        return self.transport.get_pages(
            "/api/v1/institutions/page", *args, status=status, **kw
        )

    def get_institution_by_id(self, id):
        return self.transport.get(f"/api/v1/institutions/{id}")

    def get_institution_by_version(self, version):
        return self.transport.get_pages(f"/api/v1/institutions/version/{version}")

    def get_institution_metadata(self, id):
        return self.transport.get_pages(f"/api/v1/institutions/{id}/metadata")

    def get_institutions_polon(self, includeAllVersions="true", *args, **kw):
        return self.transport.get_pages(
            "/api/v1/institutions/polon/page",
            *args,
            includeAllVersions=includeAllVersions,
            **kw,
        )

    def get_institutions_polon_by_uid(self, uid):
        return self.transport.get(f"/api/v1/institutions/polon/uid/{uid}")

    def get_institutions_polon_by_id(self, id):
        return self.transport.get(f"/api/v1/institutions/polon/{id}")


class InstitutionsProfileMixin:
    """Mixin providing institution profile API methods."""

    def get_institution_publications(self, page_size=10) -> PageableResource:
        return self.transport.get_pages(
            "/api/v1/institutionProfile/publications/page", page_size=page_size
        )

    def get_institution_publications_v2(
        self,
    ) -> PageableResource:
        return self.transport.get_pages(PBN_GET_INSTITUTION_PUBLICATIONS_V2)

    def get_institution_statements(self, page_size=10):
        return self.transport.get_pages(
            PBN_GET_INSTITUTION_STATEMENTS,
            page_size=page_size,
        )

    def get_institution_statements_of_single_publication(
        self, pbn_uid_id, page_size=50
    ):
        return self.transport.get_pages(
            PBN_GET_INSTITUTION_STATEMENTS + "?publicationId=" + pbn_uid_id,
            page_size=page_size,
        )

    def get_institution_publication_v2(
        self,
        objectId,
    ):
        return self.transport.get_pages(
            PBN_GET_INSTITUTION_PUBLICATIONS_V2 + f"?publicationId={objectId}",
        )

    def delete_all_publication_statements(self, publicationId):
        url = PBN_DELETE_PUBLICATION_STATEMENT.format(publicationId=publicationId)
        try:
            return self.transport.delete(
                url,
                body={"all": True, "statementsOfPersons": []},
            )
        except HttpException as e:
            if e.status_code != 400 or not e.url.startswith(url):
                raise e

            try:
                ret_json = json.loads(e.content)
            except BaseException as parse_err:
                raise e from parse_err
            ZABLOKOWANE = (
                "zostało tymczasowo zablokowane z uwagi na równoległą operację. "
                "Prosimy spróbować ponownie."
            )
            NIE_MOZNA_USUNAC = "Nie można usunąć oświadczeń."
            NIE_ISTNIEJA = "Nie istnieją oświadczenia dla publikacji"
            NIE_ISTNIEJE = "Nie istnieje oświadczenie dla publikacji"

            if ret_json:
                if e.json.get("message") == "Locked" and ZABLOKOWANE in e.content:
                    raise ResourceLockedException(e.content) from e

                try:
                    try:
                        msg = e.json["details"]["publicationId"]
                    except KeyError:
                        msg = e.json["details"][f"publicationId.{publicationId}"]

                    if (
                        NIE_ISTNIEJA in msg or NIE_ISTNIEJE in msg
                    ) and NIE_MOZNA_USUNAC in msg:
                        # Opis odpowiada sytuacji "Nie można usunąć oświadczeń,
                        # nie istnieją"
                        raise CannotDeleteStatementsException(e.content)

                except (TypeError, KeyError) as key_err:
                    if (
                        NIE_ISTNIEJA in e.content or NIE_ISTNIEJE in e.content
                    ) and NIE_MOZNA_USUNAC in e.content:
                        raise CannotDeleteStatementsException(e.content) from key_err

            raise e

    def delete_publication_statement(self, publicationId, personId, role):
        return self.transport.delete(
            PBN_DELETE_PUBLICATION_STATEMENT.format(publicationId=publicationId),
            body={"statementsOfPersons": [{"personId": personId, "role": role}]},
        )

    def post_discipline_statements(self, statements_data):
        """
        Send discipline statements to PBN API.

        Args:
            statements_data (list): List of statement dictionaries containing
                discipline information

        Returns:
            dict: Response from PBN API
        """
        return self.transport.post(
            PBN_POST_INSTITUTION_STATEMENTS_URL, body=statements_data
        )
