"""Publishers API mixin."""


class PublishersMixin:
    """Mixin providing publisher-related API methods."""

    def get_publishers_mnisw(self, *args, **kw):
        return self.transport.get_pages("/api/v1/publishers/mnisw/page", *args, **kw)

    def get_publishers_mnisw_yearlist(self, *args, **kw):
        return self.transport.get_pages(
            "/api/v1/publishers/mnisw/page/yearlist", *args, **kw
        )

    def get_publishers(self, *args, **kw):
        return self.transport.get_pages("/api/v1/publishers/page", *args, **kw)

    def get_publisher_by_version(self, version):
        return self.transport.get(f"/api/v1/publishers/version/{version}")

    def get_publisher_by_id(self, id):
        return self.transport.get(f"/api/v1/publishers/{id}")

    def get_publisher_metadata(self, id):
        return self.transport.get(f"/api/v1/publishers/{id}/metadata")
