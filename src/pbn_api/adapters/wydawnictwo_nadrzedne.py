class WydawnictwoNadrzednePBNAdapter:
    def __init__(self, original):
        self.original = original

    def pbn_get_json(self):
        if self.original.pbn_uid_id is not None:
            return {"objectId": self.original.pbn_uid_id}

        ret = {}

        for attr in "isbn", "issn", "title", "year":
            if hasattr(self.original, attr):
                v = getattr(self.original, attr)
                if v is not None:
                    ret[attr] = v

        ret["title"] = self.original.tytul_oryginalny
        ret["year"] = self.original.rok

        from pbn_api.adapters.wydawnictwo import WydawnictwoPBNAdapter

        volume = WydawnictwoPBNAdapter(self.original).nr_tomu()
        if volume:
            ret["volume"] = volume

        translation = WydawnictwoPBNAdapter(self.original).get_translation()
        ret["translation"] = translation

        return ret
