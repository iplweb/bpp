import functools

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
        return getattr(created, "uuid", None), getattr(created, "handle", "") or ""

    def fetch_handle(self, item_uuid):
        """Pobierz handle (trwały identyfikator) istniejącego itemu — używane
        do backfillu rekordów wysłanych zanim zaczęliśmy zapisywać handle."""
        item = self._raw.get_item(str(item_uuid))
        return getattr(item, "handle", "") or ""

    def fetch_collections(self, timeout=4):
        """Zwróć listę kolekcji DSpace tej uczelni jako ``[{uuid, name}, ...]``.

        Odpytuje API na żywo (bez cache). Każde żądanie HTTP ma narzucony
        ``timeout`` (w sekundach), żeby formularz admina nie wisiał, gdy DSpace
        jest nieosiągalny."""
        session = getattr(self._raw, "session", None)
        if session is not None:
            # requests.Session nie ma timeoutu domyślnego — wstrzykujemy go
            # jako wartość domyślną na owijce session.request.
            session.request = functools.partial(session.request, timeout=timeout)
        self.authenticate()
        kolekcje = []
        for c in self._raw.get_collections_iter():
            kolekcje.append({"uuid": str(c.uuid), "name": c.name or str(c.uuid)})
        return kolekcje

    def patch_item(self, item_uuid, dc_dict):
        item = Item({"uuid": str(item_uuid), "metadata": dc_dict, "inArchive": True})
        self._raw.update_item(item)
        return item_uuid

    def ensure_bundle(self, item_uuid, name="ORIGINAL"):
        # Faza 11: zweryfikować sygnaturę wobec żywego DSpace 9.x
        return self._raw.create_bundle(parent=str(item_uuid), name=name)

    def create_bitstream(self, bundle, element):
        # element: bpp.Element_Repozytorium z polem .plik (FileField)
        # Faza 11: zweryfikować sygnaturę (path vs file-obj) wobec żywego DSpace
        import mimetypes

        nazwa = element.nazwa_pliku or element.plik.name.rsplit("/", 1)[-1]
        mime, _ = mimetypes.guess_type(nazwa)
        created = self._raw.create_bitstream(
            bundle=bundle,
            name=nazwa,
            path=element.plik.path,
            mime=mime or "application/octet-stream",
            metadata={},
        )
        return getattr(created, "uuid", None)

    def delete_bitstream(self, bitstream_uuid):
        # Faza 11: zweryfikować nazwę metody (delete_bitstream / delete_dso)
        deleter = getattr(self._raw, "delete_bitstream", None)
        if deleter is None:
            deleter = self._raw.delete_dso
        return deleter(str(bitstream_uuid))
