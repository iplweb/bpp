from dspace_api.adapters.base import BaseDSpaceAdapter


class WydawnictwoZwarteDSpaceAdapter(BaseDSpaceAdapter):
    dc_type = "book"

    def to_dspace_dict(self):
        d = self.common_dict()
        rec = self.rec
        autorzy = self._autorzy_wg_typu(None)
        if autorzy:
            d["dc.contributor.author"] = self._multi(autorzy)
        if getattr(rec, "isbn", ""):
            d["dc.identifier.isbn"] = self._val(rec.isbn)
        if getattr(rec, "wydawca_id", None):
            d["dc.publisher"] = self._val(str(rec.wydawca))
        elif getattr(rec, "wydawca_opis", ""):
            d["dc.publisher"] = self._val(rec.wydawca_opis)
        return d
