from bpp.models import const


class WydawnictwoAutorPBNAdapter:
    def __init__(self, original):
        self.original = original

    def pbn_get_json(self):
        if (
            not self.afiliuje
            or not self.jednostka.skupia_pracownikow
            or self.jednostka.pk < 0
        ):
            return

        ret = {
            # to NIE jest ta flaga; to jest flaga dot. czy dane są w indeksie ORCID
            # a nie czy autor ma Orcid ID
            "type": const.TYP_OGOLNY_DO_PBN.get(
                self.typ_odpowiedzialnosci.typ_ogolny, "AUTHOR"
            ),
        }

        if self.profil_orcid:
            ret["orcid"] = True

        if self.dyscyplina_naukowa_id is not None:
            ret["disciplineId"] = self.dyscyplina_naukowa.kod_dla_pbn()
        else:
            return

        # if self.jednostka.pbn_uid_id:
        #    ret["institutionId"] = self.jednostka.pbn_uid.pk

        if self.autor.pbn_uid_id:
            scientist = self.autor.pbn_uid

            pesel = scientist.value(
                "object", "externalIdentifiers", "PESEL", return_none=True
            )
            if pesel:
                ret["personNaturalId"] = pesel

            ret["personObjectId"] = scientist.pk

        else:
            if self.autor.orcid:  # and self.autor.orcid_w_pbn:
                ret["personOrcidId"] = self.autor.orcid

        if not ret.get("personOrcidId") and not ret.get("personObjectId"):
            return

        ret["statementDate"] = str(self.rekord.ostatnio_zmieniony.date())

        return ret
