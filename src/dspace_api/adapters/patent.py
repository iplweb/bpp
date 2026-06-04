from dspace_api.adapters.base import BaseDSpaceAdapter


class PatentDSpaceAdapter(BaseDSpaceAdapter):
    dc_type = "patent"

    def to_dspace_dict(self):
        d = self.common_dict()
        rec = self.rec
        autorzy = self._autorzy_wg_typu(None)
        if autorzy:
            d["dc.contributor.author"] = self._multi(autorzy)
        numer = getattr(rec, "numer_prawa_wylacznego", "") or getattr(
            rec, "numer_zgloszenia", ""
        )
        if numer:
            d["dc.identifier"] = self._val(numer)
        return d
