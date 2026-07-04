"""Person API mixin."""


class PersonMixin:
    """Mixin providing person-related API methods."""

    def get_people_by_institution_id(self, id):
        return self.transport.get(f"/api/v1/person/institution/{id}")

    def get_person_by_natural_id(self, id):
        return self.transport.get(f"/api/v1/person/natural/{id}")

    def get_person_by_orcid(self, orcid):
        return self.transport.get(f"/api/v1/person/orcid/{orcid}")

    def get_people(self, *args, **kw):
        return self.transport.get_pages("/api/v1/person/page", *args, **kw)

    def get_person_by_polon_uid(self, uid):
        return self.transport.get(f"/api/v1/person/polon/{uid}")

    def get_person_by_version(self, version):
        return self.transport.get(f"/api/v1/person/version/{version}")

    def get_person_by_id(self, id):
        return self.transport.get(f"/api/v1/person/{id}")
