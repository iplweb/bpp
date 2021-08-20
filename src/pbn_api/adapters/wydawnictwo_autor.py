from bpp.models import const
from bpp.models.abstract import BazaModeluOdpowiedzialnosciAutorow


class WydawnictwoAutorToStatementPBNAdapter:
    def __init__(self, original: BazaModeluOdpowiedzialnosciAutorow):
        self.original = original

    def pbn_get_json(self):
        if (
            not self.original.afiliuje
            or not self.original.jednostka.skupia_pracownikow
            or self.original.jednostka.pk < 0
        ):
            return

        ret = {
            "type": const.TYP_OGOLNY_DO_PBN.get(
                self.original.typ_odpowiedzialnosci.typ_ogolny, "AUTHOR"
            ),
        }

        if self.original.profil_orcid:
            # To jest flaga dot. czy dane są w indeksie ORCID
            ret["orcid"] = True

        if self.original.dyscyplina_naukowa_id is not None:
            ret["disciplineId"] = self.original.dyscyplina_naukowa.kod_dla_pbn()
        else:
            return

        # if self.original.jednostka.pbn_uid_id:
        #    ret["institutionId"] = self.original.jednostka.pbn_uid.pk

        if self.original.autor.pbn_uid_id:
            scientist = self.original.autor.pbn_uid

            pesel = scientist.value(
                "object", "externalIdentifiers", "PESEL", return_none=True
            )
            if pesel:
                ret["personNaturalId"] = pesel

            ret["personObjectId"] = scientist.pk

        else:
            if self.original.autor.orcid:  # and self.original.autor.orcid_w_pbn:
                ret["personOrcidId"] = self.original.autor.orcid

        if not ret.get("personOrcidId") and not ret.get("personObjectId"):
            return

        if self.original.data_oswiadczenia is not None:
            ret["statementDate"] = str(self.original.data_oswiadczenia)

        return ret
