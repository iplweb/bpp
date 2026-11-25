from django.db.models import Q

from bpp import const
from bpp.models.abstract import BazaModeluOdpowiedzialnosciAutorow
from pbn_api.models import TlumaczDyscyplin


def powiazania_do_oswiadczenia(powiazania):
    """Zawęża powiązania autor–rekord do tych, dla których redaktor CHCE
    oświadczenia w PBN: autor afiliuje, jednostka skupia pracowników i nie
    jest obca, dyscyplina jest wybrana i przypięta.

    Nie patrzy na identyfikatory osoby — to mianownik ostrzeżenia „w PBN
    znajdzie się M z N oświadczeń” (FD#509).
    """
    return powiazania.filter(
        afiliuje=True,
        jednostka__skupia_pracownikow=True,
        jednostka_id__gte=0,
        dyscyplina_naukowa__isnull=False,
        przypieta=True,
    )


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
        powiazania_do_oswiadczenia(powiazania)
        .filter(autor__pbn_uid_id__isnull=True)
        .filter(Q(autor__orcid__isnull=True) | Q(autor__orcid=""))
        .select_related("autor", "dyscyplina_naukowa")
    )


MAKS_NAZWISK_W_OSTRZEZENIU = 3


def ostrzezenie_o_pominietych_oswiadczeniach(rekord, pominieci=None):
    """Jednoliniowe ostrzeżenie „w PBN znajdzie się M z N oświadczeń” (FD#509).

    Dla uczelni z włączonym „Wysyłaj prace, gdy autor nie ma identyfikatora
    w PBN”: praca idzie do PBN, ale bez oświadczeń autorów bez odpowiednika
    w PBN i bez ORCID. Zwraca ``None``, gdy nikogo nie pominięto.

    :param rekord: praca (``Wydawnictwo_Ciagle`` / ``Wydawnictwo_Zwarte``).
    :param pominieci: już policzona lista powiązań bez identyfikatora osoby
        (żeby nie pytać bazy drugi raz); domyślnie liczona z ``rekord``.
    """
    if pominieci is None:
        pominieci = list(powiazania_bez_identyfikatora_osoby(rekord.autorzy_set))
    if not pominieci:
        return None

    wszystkich = powiazania_do_oswiadczenia(rekord.autorzy_set).count()
    nazwiska = [str(wa.autor) for wa in pominieci[:MAKS_NAZWISK_W_OSTRZEZENIU]]
    reszta = len(pominieci) - len(nazwiska)
    kto = ", ".join(nazwiska)
    if reszta > 0:
        kto += f" (oraz {reszta} kolejnych)"
    return (
        f"oświadczenia w PBN będą niepełne: z {wszystkich} autorów z przypiętą "
        f"dyscypliną do PBN trafi {wszystkich - len(pominieci)} oświadczeń, "
        f"pominięto {len(pominieci)} — bez odpowiednika w PBN i bez ORCID: {kto}"
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
