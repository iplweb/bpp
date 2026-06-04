from dspace_api.adapters.base import BaseDSpaceAdapter


class _PracaJednoautorskaAdapter(BaseDSpaceAdapter):
    def to_dspace_dict(self):
        d = self.common_dict()
        autor = getattr(self.rec, "autor", None)
        if autor:
            d["dc.contributor.author"] = self._val(f"{autor.nazwisko}, {autor.imiona}")
        promotor = getattr(self.rec, "promotor", None)
        if promotor:
            d["dc.contributor.advisor"] = self._val(
                f"{promotor.nazwisko}, {promotor.imiona}"
            )
        return d


class PracaDoktorskaDSpaceAdapter(_PracaJednoautorskaAdapter):
    dc_type = "doctoralThesis"


class PracaHabilitacyjnaDSpaceAdapter(_PracaJednoautorskaAdapter):
    dc_type = "Thesis"
