from dspace_api.adapters.base import BaseDSpaceAdapter


class WydawnictwoCiagleDSpaceAdapter(BaseDSpaceAdapter):
    dc_type = "article"

    def to_dspace_dict(self):
        d = self.common_dict()
        rec = self.rec
        autorzy = self._autorzy_wg_typu(None)
        if autorzy:
            d["dc.contributor.author"] = self._multi(autorzy)
        if getattr(rec, "issn", ""):
            d["dc.identifier.issn"] = self._val(rec.issn)
        if getattr(rec, "zrodlo_id", None):
            d["dc.relation.ispartof"] = self._val(str(rec.zrodlo))
        return d
