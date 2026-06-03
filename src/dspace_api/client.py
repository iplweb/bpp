from dspace_rest_client.client import DSpaceClient as RawDSpaceClient
from dspace_rest_client.models import Item


class DSpaceAuthError(RuntimeError):
    pass


class DSpaceClient:
    """Otoczka na dspace-rest-client skonfigurowana z obiektu Uczelnia."""

    def __init__(self, uczelnia):
        self.uczelnia = uczelnia
        self._raw = RawDSpaceClient(
            api_endpoint=uczelnia.dspace_api_endpoint,
            username=uczelnia.dspace_api_username,
            password=uczelnia.dspace_api_password,
        )

    def authenticate(self):
        ok = self._raw.authenticate()
        if not ok:
            raise DSpaceAuthError(
                f"Logowanie do DSpace {self.uczelnia.dspace_api_endpoint} "
                f"nie powiodło się."
            )
        return ok

    def create_item(self, collection_uuid, dc_dict):
        item = Item({"metadata": dc_dict, "inArchive": True})
        created = self._raw.create_item(parent=str(collection_uuid), item=item)
        return getattr(created, "uuid", None)

    def patch_item(self, item_uuid, dc_dict):
        item = Item({"uuid": str(item_uuid), "metadata": dc_dict, "inArchive": True})
        self._raw.update_item(item)
        return item_uuid
