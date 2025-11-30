"""Dictionaries API mixin."""

from pbn_api.const import PBN_GET_DISCIPLINES_URL, PBN_GET_LANGUAGES_URL


class DictionariesMixin:
    """Mixin providing dictionary-related API methods."""

    def get_countries(self):
        return self.transport.get("/api/v1/dictionary/countries")

    def get_disciplines(self):
        return self.transport.get(PBN_GET_DISCIPLINES_URL)

    def get_languages(self):
        return self.transport.get(PBN_GET_LANGUAGES_URL)
