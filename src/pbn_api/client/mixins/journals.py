"""Journals API mixin."""

from pbn_api.const import PBN_GET_JOURNAL_BY_ID


class JournalsMixin:
    """Mixin providing journal-related API methods."""

    def get_journals_mnisw(self, *args, **kw):
        return self.transport.get_pages("/api/v1/journals/mnisw/page", *args, **kw)

    def get_journals_mnisw_v2(self, *args, **kw):
        return self.transport.get_pages("/api/v2/journals/mnisw/page", *args, **kw)

    def get_journals(self, *args, **kw):
        return self.transport.get_pages("/api/v1/journals/page", *args, **kw)

    def get_journals_v2(self, *args, **kw):
        return self.transport.get_pages("/api/v2/journals/page", *args, **kw)

    def get_journal_by_version(self, version):
        return self.transport.get(f"/api/v1/journals/version/{version}")

    def get_journal_by_id(self, id):
        return self.transport.get(PBN_GET_JOURNAL_BY_ID.format(id=id))

    def get_journal_metadata(self, id):
        return self.transport.get(f"/api/v1/journals/{id}/metadata")
