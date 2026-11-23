from django.db.models import Q

from bpp import const
from bpp.models.abstract import BazaModeluOdpowiedzialnosciAutorow
from pbn_api.models import TlumaczDyscyplin


def powiazania_bez_identyfikatora_osoby(powiazania):
    """Zawęża powiązania autor–rekord do tych, których oświadczenia NIE da się
    wysłać do PBN z braku identyfikatora osoby (FD#509).

    Warunek jest lustrzanym odbiciem ``WydawnictwoAutorToStatementPBNAdapter``:
    oświadczenie powstałoby (autor afiliuje, jednostka skupia pracowników i nie
    jest obca, dyscyplina jest wybrana i przypięta), ale autor nie ma ani
    odpowiednika w PBN (``pbn_uid``), ani ORCID. Autor z samym ORCID tu NIE
    trafia — jego oświadczenie idzie po ORCID.

    Jedno źródło prawdy dla blokady wysyłki, komunikatów i zestawienia
    w komendzie ``pbn_oswiadczenia_bez_identyfikatora``. Zgodność z adapterem
    pilnują testy w ``pbn_api/tests/test_repro_fd509.py``.

    :param powiazania: queryset ``Wydawnictwo_Ciagle_Autor`` /
        ``Wydawnictwo_Zwarte_Autor`` (np. ``rekord.autorzy_set``).
    """
    return (
        powiazania.filter(
            afiliuje=True,
            jednostka__skupia_pracownikow=True,
            jednostka_id__gte=0,
            dyscyplina_naukowa__isnull=False,
            przypieta=True,
            autor__pbn_uid_id__isnull=True,
        )
        .filter(Q(autor__orcid__isnull=True) | Q(autor__orcid=""))
        .select_related("autor", "dyscyplina_naukowa")
    )


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

        # if self.original.profil_orcid:
        #     # To jest flaga dot. czy dane są w indeksie ORCID
        #     ret["orcid"] = True

        if self.original.dyscyplina_naukowa_id is not None and self.original.przypieta:
            przetlumaczona = TlumaczDyscyplin.objects.przetlumacz_dyscypline(
                self.original.dyscyplina_naukowa, self.original.rekord.rok
            )
            ret["disciplineId"] = przetlumaczona.code
            ret["disciplineUuid"] = str(przetlumaczona.uuid)
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
            # Bez identyfikatora osoby PBN nie przyjmie oświadczenia. Wysyłka
            # PRACY z takim autorem jest blokowana wcześniej
            # (``AutorBezIdentyfikatoraPBN``, FD#509) — tu zostaje pas
            # bezpieczeństwa dla ścieżek, które budują same oświadczenia.
            return

        if self.original.data_oswiadczenia is not None:
            ret["statementDate"] = str(self.original.data_oswiadczenia)

        return ret
