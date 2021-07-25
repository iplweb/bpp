class ZrodloPBNAdapter:
    def __init__(self, original):
        self.original = original

    def pbn_get_json(self):
        if self.original.pbn_uid_id is None:
            ret = {"title": self.original.nazwa}
            if self.original.wydawca:
                ret["publisher"] = {"name": self.original.wydawca}
            if self.original.issn:
                ret["issn"] = self.original.issn
            if self.original.www:
                ret["websiteLink"] = self.original.www
            if self.original.e_issn:
                ret["eissn"] = self.original.e_issn
            return ret

            #     "issue": {
            #       "doi": "string",
            #       "number": "string",
            #       "objectId": "string",
            #       "publishedYear": 0,
            #       "versionHash": "string",
            #       "volume": "string",
            #       "year": "string"
            #     },
            #     "mniswId": 0,
            #     "objectId": "string",

        #  "journal": {
        #     "eissn": "string",
        #     "issn": "string",
        #     "issue": {
        #       "doi": "string",
        #       "number": "string",
        #       "objectId": "string",
        #       "publishedYear": 0,
        #       "versionHash": "string",
        #       "volume": "string",
        #       "year": "string"
        #     },
        #     "publisher": {
        #       "mniswId": 0,
        #       "name": "string",
        #       "objectId": "string",
        #       "versionHash": "string"
        #     },
        #     "title": "string",
        #     "versionHash": "string",
        #     "websiteLink": "string"
        #   },

        journal = self.original.pbn_uid

        ret = {
            "objectId": journal.pk,
        }

        for attr in [
            "eissn",
            "issn",
            "publisher",
            "title",
            "websiteLink",
            "mniswId",
        ]:
            v = journal.value("object", attr, return_none=True)
            if v is not None:
                ret[attr] = v

        return ret
