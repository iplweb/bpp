"""Search API mixin."""

from pbn_api.const import PBN_SEARCH_PUBLICATIONS_URL


class SearchMixin:
    """Mixin providing search-related API methods."""

    def search_publications(self, *args, **kw):
        return self.transport.post_pages(PBN_SEARCH_PUBLICATIONS_URL, body=kw)
