from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils.functional import cached_property

from bpp.models import Dyscyplina_Naukowa, Wydawca
from bpp.models.cache import Cache_Punktacja_Autora, Cache_Punktacja_Dyscypliny
from bpp.models.patent import Patent
from bpp.models.sloty.wydawnictwo_ciagle import SlotKalkulator_Wydawnictwo_Ciagle_Prog3
from bpp.models.sloty.wydawnictwo_zwarte import (
    SlotKalkulator_Wydawnictwo_Zwarte_Prog1,
    SlotKalkulator_Wydawnictwo_Zwarte_Prog2,
    SlotKalkulator_Wydawnictwo_Zwarte_Prog3,
)
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte

from ... import const
from ...const import PBN_MAX_ROK, PBN_MIN_ROK
from .exceptions import CannotAdapt
from .wydawnictwo_ciagle import (
    SlotKalkulator_Wydawnictwo_Ciagle_Prog1,
    SlotKalkulator_Wydawnictwo_Ciagle_Prog2,
)


def _rozstrzygnij_uczelnie(original):
    """ISlot bez jawnej uczelni: zwróć jednoznaczną uczelnię albo CannotAdapt."""
    from bpp.models.uczelnia import Uczelnia

    if Uczelnia.objects.count() == 1:
        return Uczelnia.objects.get()

    uczelnie = list(original.uczelnie_rekordu())
    if len(uczelnie) == 1:
        return uczelnie[0]
    if len(uczelnie) == 0:
        raise CannotAdapt(
            "Rekord nie ma afiliujących i przypiętych autorów — "
            "nie można ustalić uczelni."
        )
    raise CannotAdapt(
        "Rekord ma autorów z wielu uczelni — podaj uczelnię jawnie "
        "(ISlot(rekord, uczelnia=...)); bez niej wynik jest niejednoznaczny."
    )


def ISlot(original, uczelnia=None):  # noqa
    if isinstance(original, Patent):
        raise CannotAdapt("Sloty dla patentów nie są liczone")

    if hasattr(original, "typ_kbn") and original.typ_kbn.skrot == "PW":
        raise CannotAdapt("Sloty dla prac wieloośrodkowych nie są liczone.")

    if hasattr(original, "rok") and original.rok is None:
        raise CannotAdapt("Rekord nie ma ustawionego roku — sloty nie są liczone.")

    if uczelnia is None:
        uczelnia = _rozstrzygnij_uczelnie(original)

    if hasattr(
        original, "status_korekty_id"
    ) and original.status_korekty_id in uczelnia.ukryte_statusy("sloty"):
        raise CannotAdapt(
            "Sloty nie będą liczone, zgodnie z ustawieniami obiektu Uczelnia dla ukrywanych "
            "statusów korekt. "
        )

    kalkulator = _dopasuj_kalkulator(original, uczelnia)
    kalkulator.uczelnia = uczelnia
    return kalkulator


def _dopasuj_kalkulator(original, uczelnia=None):  # noqa: C901
    if isinstance(original, Wydawnictwo_Ciagle):
        if original.rok in [2017, 2018]:
            if original.punkty_kbn >= 30:
                return SlotKalkulator_Wydawnictwo_Ciagle_Prog1(original)
            elif original.punkty_kbn in [20, 25]:
                return SlotKalkulator_Wydawnictwo_Ciagle_Prog2(original)
            elif original.punkty_kbn < 20 and original.punkty_kbn > 0:
                return SlotKalkulator_Wydawnictwo_Ciagle_Prog3(original)

        elif original.rok > 2018 and original.rok <= PBN_MAX_ROK:
            if original.punkty_kbn in [200, 140, 100]:
                return SlotKalkulator_Wydawnictwo_Ciagle_Prog1(original)
            elif original.punkty_kbn in [70, 40]:
                return SlotKalkulator_Wydawnictwo_Ciagle_Prog2(original)
            elif original.punkty_kbn <= 20 and original.punkty_kbn > 0:
                return SlotKalkulator_Wydawnictwo_Ciagle_Prog3(original)

        raise CannotAdapt(
            f"punkty MNiSW/MEiN rekordu ({original.punkty_kbn}) i rok ({original.rok}) nie pozwalają na dopasowanie "
            f"tego rekordu do jakiejkolwiek grupy"
        )

    elif isinstance(original, Wydawnictwo_Zwarte):
        if original.rok < PBN_MIN_ROK or original.rok > PBN_MAX_ROK:
            raise CannotAdapt(
                f"Rok poza zakresem procedur liczacych ({original.rok}). "
            )

        poziom_wydawcy = -1

        if original.wydawca_id is not None:
            try:
                wydawca = original.wydawca
                poziom_wydawcy = wydawca.get_tier(original.rok)
            except Wydawca.DoesNotExist:
                pass

        # Referaty zjazdowe

        if original.charakter_formalny.charakter_sloty == const.CHARAKTER_SLOTY_REFERAT:
            if (
                original.punkty_kbn == 15
                and original.zewnetrzna_baza_danych.filter(
                    baza__skrot__iexact="wos"
                ).exists()
            ):
                return SlotKalkulator_Wydawnictwo_Ciagle_Prog3(original)

            if original.punkty_kbn in [200, 140, 100]:
                return SlotKalkulator_Wydawnictwo_Ciagle_Prog1(original)

            if original.punkty_kbn in [70, 40]:
                return SlotKalkulator_Wydawnictwo_Ciagle_Prog2(original)

            if original.punkty_kbn == 20:
                if poziom_wydawcy == 1:
                    return SlotKalkulator_Wydawnictwo_Ciagle_Prog2(original)

                return SlotKalkulator_Wydawnictwo_Ciagle_Prog3(original)

            if original.punkty_kbn == 50 and poziom_wydawcy == 2:
                return SlotKalkulator_Wydawnictwo_Ciagle_Prog1(original)

            if original.punkty_kbn == 5:
                return SlotKalkulator_Wydawnictwo_Ciagle_Prog3(original)

            raise CannotAdapt("Nie dopasowano do żadnego rodzaju referatu.")

        # Koniec referatów zjazdowych

        rozdzial = ksiazka = autorstwo = redakcja = False

        rozdzial = original.warunek_rozdzial()
        ksiazka = original.warunek_ksiazka()

        if ksiazka and rozdzial:
            raise NotImplementedError("To sie nie powinno wydarzyc)")

        if ksiazka and original.pk:
            autorstwo = original.warunek_autorstwo()
            redakcja = original.warunek_redakcja()

            if autorstwo and redakcja:
                raise CannotAdapt("Rekord ma jednocześnie autorów i redaktorów.")

            if not autorstwo and not redakcja:
                raise CannotAdapt("Rekord nie posiada autorów ani redaktorów.")

        tryb_kalkulacji = None

        if ksiazka and autorstwo:
            tryb_kalkulacji = const.TRYB_KALKULACJI.AUTORSTWO_MONOGRAFII

        elif ksiazka and redakcja:
            tryb_kalkulacji = const.TRYB_KALKULACJI.REDAKCJA_MONOGRAFI

        elif rozdzial and autorstwo:
            tryb_kalkulacji = const.TRYB_KALKULACJI.ROZDZIAL_W_MONOGRAFI

        rodzaje_hst = {
            Dyscyplina_Naukowa.objects.get(pk=x[0]).dyscyplina_hst
            for x in original.wszystkie_dyscypliny_rekordu(uczelnia)
        }

        match len(rodzaje_hst):
            case 0:
                raise CannotAdapt("Rekord nie zawiera danych dyscyplin.")
            case 1:
                wiele_hst = False
                tryb_hst = list(rodzaje_hst)[0]
            case 2:
                wiele_hst = True
                tryb_hst = None
            case _:
                raise CannotAdapt(
                    "sytuacja przy obliczaniu punktacji nieprzewidziana, zgłoś autorowi oprogramowania"
                )

        if poziom_wydawcy == 2:
            warunek_dla_monografii = (
                ksiazka
                and autorstwo
                and (
                    (tryb_hst is not True and original.punkty_kbn in [200, 100])
                    or (tryb_hst is True and original.punkty_kbn == 300)
                )
            )
            warunek_dla_redakcji = (
                ksiazka
                and redakcja
                and (
                    (tryb_hst is not True and original.punkty_kbn in [100, 50])
                    or (tryb_hst is True and original.punkty_kbn == 150)
                )
            )
            warunek_dla_rozdzialow = rozdzial and (
                (tryb_hst is not True and original.punkty_kbn in [50, 25])
                or (tryb_hst is True and original.punkty_kbn == 75)
            )

            if wiele_hst is True and original.punkty_kbn in [300, 150, 75]:
                raise CannotAdapt(
                    "Publikacja ma autorów z dyscyplin HST oraz nie-HST; dla rekordu wpisz punktację "
                    "bazową (czyli np. 200, 100, 50 punktów). Dla autorów dyscyplin HST przy "
                    "obliczeniach punktacja zostanie zwiększona automatycznie. "
                )

            if warunek_dla_monografii or warunek_dla_redakcji or warunek_dla_rozdzialow:
                return SlotKalkulator_Wydawnictwo_Zwarte_Prog1(
                    original, tryb_kalkulacji, wiele_hst=wiele_hst
                )

        elif poziom_wydawcy == 1:
            warunek_dla_monografii = (
                ksiazka
                and autorstwo
                and (
                    (tryb_hst is not True and original.punkty_kbn in [80, 40, 100])
                    or (tryb_hst is True and original.punkty_kbn == 120)
                )
            )
            warunek_dla_redakcji = (
                ksiazka
                and redakcja
                and (
                    (tryb_hst is not True and original.punkty_kbn == 20)
                    or (tryb_hst is True and original.punkty_kbn == 40)
                )
            )
            warunek_dla_rozdzialow = rozdzial and (
                (tryb_hst is not True and original.punkty_kbn == 20)
                or (tryb_hst is True and original.punkty_kbn == 20)
            )

            if wiele_hst is True and original.punkty_kbn in [120, 40]:
                raise CannotAdapt(
                    "Publikacja ma autorów z dyscyplin HST oraz nie-HST; dla rekordu wpisz punktację "
                    "bazową (czyli np. 80 lub 20). Dla autorów dyscyplin HST przy "
                    "obliczeniach punktacja zostanie zwiększona automatycznie. "
                )

            if warunek_dla_monografii or warunek_dla_redakcji or warunek_dla_rozdzialow:
                _wiele_hst = wiele_hst
                if warunek_dla_rozdzialow:
                    _wiele_hst = False

                return SlotKalkulator_Wydawnictwo_Zwarte_Prog2(
                    original,
                    tryb_kalkulacji,
                    wiele_hst=_wiele_hst,
                    poziom_wydawcy=poziom_wydawcy,
                )

        else:
            warunek_dla_monografii = (
                ksiazka
                and autorstwo
                and (
                    (tryb_hst is not True and original.punkty_kbn in [20, 10])
                    or (tryb_hst is True and original.punkty_kbn in [20, 120])
                )
            )
            warunek_dla_redakcji = (
                ksiazka
                and redakcja
                and (
                    (tryb_hst is not True and original.punkty_kbn in [5, 2.5])
                    or (tryb_hst is True and original.punkty_kbn in [10, 20])
                )
            )
            warunek_dla_rozdzialow = rozdzial and (
                (tryb_hst is not True and original.punkty_kbn in [5, 2.5])
                or (tryb_hst is True and original.punkty_kbn in [5, 20])
            )

            if wiele_hst is True and original.punkty_kbn in [
                120,
            ]:
                raise CannotAdapt(
                    "Publikacja ma autorów z dyscyplin HST oraz nie-HST; dla rekordu wpisz punktację "
                    "bazową (czyli np 5, 10, 20 punkta). Dla autorów dyscyplin HST przy "
                    "obliczeniach punktacja zostanie zwiększona automatycznie. "
                )

            if warunek_dla_monografii or warunek_dla_redakcji or warunek_dla_rozdzialow:
                return SlotKalkulator_Wydawnictwo_Zwarte_Prog3(
                    original, tryb_kalkulacji, wiele_hst=True
                )

        raise CannotAdapt(
            f"Rekordu nie można dopasować do żadnej z grup monografii. {poziom_wydawcy=}, {ksiazka=},"
            f"{rozdzial=}, {autorstwo=}, {redakcja=}, {original.punkty_kbn=}, {tryb_hst=}, {wiele_hst=}"
        )

    if hasattr(original, "rok") and hasattr(original, "punkty_kbn"):
        raise CannotAdapt(
            f"Nie umiem policzyc dla {original} rok {original.rok} punkty_kbn {original.punkty_kbn}"
        )

    raise CannotAdapt(f"Nie umiem policzyć dla obiektu: {original!r}")


class IPunktacjaCacher:
    def __init__(self, original):
        self.original = original

    def canAdapt(self):
        try:
            _dopasuj_kalkulator(self.original)
            return True
        except CannotAdapt:
            return False

    @cached_property
    def ctype(self):
        return ContentType.objects.get_for_model(self.original).pk

    @property
    def cache_punktacja_autora(self):
        return Cache_Punktacja_Autora.objects.filter(
            rekord_id=[self.ctype, self.original.pk]
        )

    @property
    def cache_punktacja_dyscypliny(self):
        return Cache_Punktacja_Dyscypliny.objects.filter(
            rekord_id=[self.ctype, self.original.pk]
        )

    @transaction.atomic
    def removeEntries(self):
        self.cache_punktacja_dyscypliny.delete()
        self.cache_punktacja_autora.delete()

    def serialize(self):
        """
        Zwraca krotkę (autorzy, dyscypliny) z deterministycznie posortowaną
        zawartością cache dla tego rekordu.
        """
        ret1 = [
            elem.serialize()
            for elem in self.cache_punktacja_autora.order_by(
                "jednostka__uczelnia_id", "autor__nazwisko", "dyscyplina__nazwa", "pk"
            )
        ]
        ret2 = [
            elem.serialize()
            for elem in self.cache_punktacja_dyscypliny.order_by(
                "uczelnia_id", "dyscyplina__nazwa", "pk"
            )
        ]
        return ret1, ret2

    def get_pk(self):
        return (self.ctype, self.original.pk)

    def _uczelnie_do_przeliczenia(self):
        from bpp.models.uczelnia import Uczelnia

        # Fast-track dla single-install: jedna uczelnia w systemie => bez
        # enumeracji autorów rekordu (wszyscy autorzy i tak należą do tej
        # jednej uczelni). Jedno zapytanie zamiast JOIN-a po autorach.
        uczelnie_systemu = list(Uczelnia.objects.all()[:2])
        if len(uczelnie_systemu) == 1:
            return uczelnie_systemu
        return self.original.uczelnie_rekordu()

    @transaction.atomic
    def rebuildEntries(self):
        for uczelnia in self._uczelnie_do_przeliczenia():
            try:
                kalk = ISlot(self.original, uczelnia=uczelnia)
            except CannotAdapt:
                # Nie liczy się (typ/punkty/rok) lub ukryty status dla tej uczelni
                continue
            self._zapisz(kalk, uczelnia)

    def _zapisz(self, kalk, uczelnia):
        pk = self.get_pk()

        for dyscyplina in kalk.dyscypliny:
            azd = kalk.autorzy_z_dyscypliny(dyscyplina)
            if not azd:
                # Nie chcemy wpisów odnośnie dyscyplin i slotów, gdy nie ma
                # w nich żadnych autorów (zgłoszenie w Mantis #1009)
                continue

            Cache_Punktacja_Dyscypliny.objects.create(
                rekord_id=[pk[0], pk[1]],
                dyscyplina=dyscyplina,
                uczelnia=uczelnia,
                pkd=kalk.punkty_pkd(dyscyplina),
                slot=kalk.slot_dla_dyscypliny(dyscyplina),
                autorzy_z_dyscypliny=[a.pk for a in azd],
                zapisani_autorzy_z_dyscypliny=[a.zapisany_jako for a in azd],
            )

        if not self.original.pk:
            return

        # UWAGA (read-side): autorzy_z_dyscypliny zapisani w
        # Cache_Punktacja_Dyscypliny mogą zawierać PK autora z jednostki
        # skupia_pracownikow=False, dla którego NIE powstaje wiersz
        # Cache_Punktacja_Autora (ten filtr go pomija). Konsumenci widoku
        # nie powinni zakładać relacji 1:1 między listą autorów w CPD a
        # wierszami CPA.
        for wa in self.original.autorzy_set.filter(jednostka__uczelnia=uczelnia):
            if (
                not wa.afiliuje
                or not wa.jednostka.skupia_pracownikow
                or not wa.przypieta
                or not wa.rodzaj_autora_uwzgledniany_w_kalkulacjach_slotow()
            ):
                # Jeżeli autor NIE afiliuje lub afiliuje, ale jednostka nie skupia
                # pracowników (czyli jest OBCA, czyli realnie wpis błędny), lub
                # dyscyplina jest "odpięta" to nie licz punktów dla takiego autora
                continue

            dyscyplina = wa.okresl_dyscypline()
            if dyscyplina is None:
                continue

            pkdaut = kalk.pkd_dla_autora(wa)
            if pkdaut is None:
                continue
            Cache_Punktacja_Autora.objects.create(
                rekord_id=[pk[0], pk[1]],
                autor_id=wa.autor_id,
                jednostka_id=wa.jednostka_id,
                dyscyplina_id=dyscyplina.pk,
                pkdaut=pkdaut,
                slot=kalk.slot_dla_autora_z_dyscypliny(dyscyplina),
            )
