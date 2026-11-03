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
        # Gdy jest już numer prawa wyłącznego, numer zgłoszenia nie ginie —
        # trafia do dc.identifier.other (pole z domyślnego rejestru DC DSpace).
        numer_zgloszenia = getattr(rec, "numer_zgloszenia", "") or ""
        if numer_zgloszenia and numer_zgloszenia != numer:
            d["dc.identifier.other"] = self._val(numer_zgloszenia)
        data_zgloszenia = getattr(rec, "data_zgloszenia", None)
        if data_zgloszenia:
            d["dc.date.submitted"] = self._val(data_zgloszenia.isoformat())
        return d
