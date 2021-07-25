class WydawcaPBNAdapter:
    def __init__(self, original):
        self.original = original

    def pbn_get_json(self):
        wydawca = self.original.get_toplevel()

        if wydawca.pbn_uid_id is not None:
            pbn_wydawca = wydawca.pbn_uid
            ret = {
                "objectId": pbn_wydawca.pk,
                "name": pbn_wydawca.value("object", "publisherName"),
            }
            mniswId = pbn_wydawca.value_or_none("object", "mniswId")
            if mniswId:
                ret["mniswId"] = mniswId
            return ret

        return {
            "name": wydawca.nazwa,
        }
