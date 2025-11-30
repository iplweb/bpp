"""Publications API mixin."""

from urllib.parse import quote

from pbn_api.const import PBN_GET_PUBLICATION_BY_ID_URL


class PublicationsMixin:
    """Mixin providing publication-related API methods."""

    def get_publication_by_doi(self, doi):
        return self.transport.get(
            f"/api/v1/publications/doi/?doi={quote(doi, safe='')}",
        )

    def get_publication_by_doi_page(self, doi):
        return self.transport.get_pages(
            f"/api/v1/publications/doi/page?doi={quote(doi, safe='')}",
            headers={"doi": doi},
        )

    def get_publication_by_id(self, id):
        return self.transport.get(PBN_GET_PUBLICATION_BY_ID_URL.format(id=id))

    def get_publication_metadata(self, id):
        return self.transport.get(f"/api/v1/publications/id/{id}/metadata")

    def get_publications(self, **kw):
        return self.transport.get_pages("/api/v1/publications/page", **kw)

    def get_publication_by_version(self, version):
        return self.transport.get(f"/api/v1/publications/version/{version}")
