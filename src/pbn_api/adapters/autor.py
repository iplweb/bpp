class AutorSimplePBNAdapter:
    def __init__(self, original):
        self.original = original

    def pbn_get_json(self):
        ret = {"givenNames": self.original.imiona, "lastName": self.original.nazwisko}

        if self.original.pbn_uid_id is not None:
            ret.update({"objectId": self.original.pbn_uid_id})

            s = self.original.pbn_uid
            # Jeżeli powiązany rekord w tabeli pbn_api.Sciencist ma PESEL to
            # dodamy go teraz do eksportowanych informacji:
            pesel = s.value("object", "externalIdentifiers", "PESEL", return_none=True)
            if pesel:
                ret.update({"naturalId": pesel})
        return ret


class AutorZDyscyplinaPBNAdapter(AutorSimplePBNAdapter):
    # To samo, co AutorSimplePBNAdapter, ale eksportuje ORCID

    def pbn_get_json(self):
        ret = super(AutorZDyscyplinaPBNAdapter, self).pbn_get_json()

        # Eksportuj ORCID wyłacznie, gdy nie został wyeksportowany identyfikator PBN
        if (
            self.original.orcid is not None and "objectId" not in ret
        ):  # and self.orcid_w_pbn is True:
            ret.update({"orcidId": self.original.orcid})

        return ret
