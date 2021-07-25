raise NotImplementedError(
    """

1) wywalic ta procedure

2) eksport autora z ORCIDem lub innym identyfikatorem JEDYNIE gdy posiada on dyscypline

3) jezeli nie posiada dyscypliny to imie/nazwisko i styka. """
)


def pbn_get_json(self):
    ret = {"givenNames": self.imiona, "lastName": self.nazwisko}

    if self.pbn_uid_id is not None:
        ret.update({"objectId": self.pbn_uid.pk})

        s = self.pbn_uid

        # Jeżeli powiązany rekord w tabeli pbn_api.Sciencist ma PESEL to
        # dodamy go teraz do eksportowanych informacji:
        pesel = s.value("object", "externalIdentifiers", "PESEL", return_none=True)
        if pesel:
            ret.update({"naturalId": pesel})

    else:
        if self.orcid is not None:  # and self.orcid_w_pbn is True:
            ret.update({"orcidId": self.orcid})

    return ret
