"""Conferences API mixin."""


class ConferencesMixin:
    """Mixin providing conference-related API methods."""

    def get_conferences(self, *args, **kw):
        return self.transport.get_pages("/api/v1/conferences/page", *args, **kw)

    def get_conferences_mnisw(self, *args, **kw):
        return self.transport.get_pages("/api/v1/conferences/mnisw/page", *args, **kw)

    def get_conference(self, id):
        return self.transport.get(f"/api/v1/conferences/{id}")

    def get_conference_editions(self, id):
        return self.transport.get(f"/api/v1/conferences/{id}/editions")

    def get_conference_metadata(self, id):
        return self.transport.get(f"/api/v1/conferences/{id}/metadata")
