from django.db import transaction

from ... import const
from ...const import PBN_MAX_ROK, PBN_MIN_ROK
from .exceptions import CannotAdapt
from .wydawnictwo_ciagle import (
    SlotKalkulator_Wydawnictwo_Ciagle_Prog1,
    SlotKalkulator_Wydawnictwo_Ciagle_Prog2,
)

from django.contrib.contenttypes.models import ContentType

from django.utils.functional import cached_property

from bpp.models import Dyscyplina_Naukowa, Typ_Odpowiedzialnosci, Uczelnia, Wydawca
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


def ISlot(original, uczelnia=None):
    if isinstance(original, Patent):
        raise CannotAdapt("Sloty dla patentów nie są liczone")

    if hasattr(original, "typ_kbn") and original.typ_kbn.skrot == "PW":
        raise CannotAdapt("Sloty dla prac wieloośrodkowych nie są liczone.")

    if uczelnia is None:
        uczelnia = Uczelnia.objects.get_default()

    if uczelnia is not None and original.status_korekty_id in uczelnia.ukryte_statusy(
        "sloty"
    ):
        raise CannotAdapt(
            "Sloty nie będą liczone, zgodnie z ustawieniami obiektu Uczelnia dla ukrywanych "
            "statusów korekt. "
        )

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
            "Punkty KBN rekordu (%s) i rok (%s) nie pozwalają na dopasowanie tego rekordu do jakiejkolwiek grupy"
            % (original.punkty_kbn, original.rok)
        )

    elif isinstance(original, Wydawnictwo_Zwarte):
        if original.rok < PBN_MIN_ROK or original.rok > PBN_MAX_ROK:
            raise CannotAdapt(
                "Rok poza zakresem procedur liczacych (%s). " % original.rok
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

        if (
            original.charakter_formalny.charakter_sloty
            == const.CHARAKTER_SLOTY_ROZDZIAL
        ):
            rozdzial = True

        if original.charakter_formalny.charakter_sloty == const.CHARAKTER_SLOTY_KSIAZKA:
            ksiazka = True

        if ksiazka and rozdzial:
            raise NotImplementedError("To sie nie powinno wydarzyc)")

        if ksiazka and original.pk:
            for elem in Typ_Odpowiedzialnosci.objects.filter(
                pk__in=original.autorzy_set.values_list("typ_odpowiedzialnosci_id")
            ).distinct():
                if elem.typ_ogolny == const.TO_AUTOR:
                    autorstwo = True
                    continue
                if elem.typ_ogolny == const.TO_REDAKTOR:
                    redakcja = True
                    continue

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
            for x in original.wszystkie_dyscypliny_rekordu()
        }
        if len(rodzaje_hst) > 1:
            raise CannotAdapt(
                """Rekord zawiera zarówno dyscypliny z grupy HST (nauki humanistyczne, nauki społeczne
                i nauki teologiczne) jak i dyscypliny spoza tej grupy. Na obecną chwilę algorytm tego
                oprogramowania nie obsługuje takich rekordów. Proszę o weryfikację rekordu i ewentualne
                zgłoszenie problemu. """
            )
        elif len(rodzaje_hst) == 0:
            raise CannotAdapt("Rekord nie zawiera danych dyscyplin.")

        tryb_hst = list(rodzaje_hst)[0]

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

            if warunek_dla_monografii or warunek_dla_redakcji or warunek_dla_rozdzialow:
                return SlotKalkulator_Wydawnictwo_Zwarte_Prog1(
                    original, tryb_kalkulacji
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
                    (tryb_hst is not True and original.punkty_kbn in [20, 10])
                    or (tryb_hst is True and original.punkty_kbn == 40)
                )
            )
            warunek_dla_rozdzialow = rozdzial and (
                (tryb_hst is not True and original.punkty_kbn in [20, 10])
                or (tryb_hst is True and original.punkty_kbn == 20)
            )

            if warunek_dla_monografii or warunek_dla_redakcji or warunek_dla_rozdzialow:
                return SlotKalkulator_Wydawnictwo_Zwarte_Prog2(
                    original, tryb_kalkulacji
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

            if warunek_dla_monografii or warunek_dla_redakcji or warunek_dla_rozdzialow:
                return SlotKalkulator_Wydawnictwo_Zwarte_Prog3(
                    original, tryb_kalkulacji
                )

        raise CannotAdapt(
            "Rekordu nie można dopasować do żadnej z grup monografii. Poziom "
            "wydawcy: %(poziom_wydawcy)s, ksiazka: %(ksiazka)s, rozdzial: %(rozdzial)s, "
            "autorstwo: %(autorstwo)s, redakcja: %(redakcja)s, punkty kbn: %(punkty_kbn)s, "
            "tryb_hst: %(tryb_hst)s"
            % dict(
                poziom_wydawcy=poziom_wydawcy,
                ksiazka=ksiazka,
                rozdzial=rozdzial,
                autorstwo=autorstwo,
                redakcja=redakcja,
                punkty_kbn=original.punkty_kbn,
                tryb_hst=tryb_hst,
            )
        )

    if hasattr(original, "rok") and hasattr(original, "punkty_kbn"):
        raise CannotAdapt(
            "Nie umiem policzyc dla %s rok %s punkty_kbn %s"
            % (original, original.rok, original.punkty_kbn)
        )

    raise CannotAdapt("Nie umiem policzyć dla obiektu: %r" % original)


class IPunktacjaCacher:
    def __init__(self, original, uczelnia=None):
        self.original = original
        self.slot = None
        self.uczelnia = uczelnia

    def canAdapt(self):
        try:
            self.slot = ISlot(self.original, uczelnia=self.uczelnia)
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
        Zwraca słownik JSON z zawartością danych rekordu
        """
        ret1 = []
        for elem in self.cache_punktacja_autora:
            ret1.append(elem.serialize())

        ret2 = []
        for elem in self.cache_punktacja_dyscypliny:
            ret2.append(elem.serialize())

        return ret1, ret2

    @transaction.atomic
    def rebuildEntries(self):
        pk = (self.ctype, self.original.pk)

        # Jeżeli nie można zaadaptować danego rekordu do kalkulatora
        # punktacji, to po skasowaniu ewentualnej scache'owanej punktacji
        # wyjdź z funkcji:
        if self.canAdapt() is False:
            return

        _slot_cache = {}

        for dyscyplina in self.slot.dyscypliny:
            _slot_cache[dyscyplina] = self.slot.slot_dla_dyscypliny(dyscyplina)
            azd = self.slot.autorzy_z_dyscypliny(dyscyplina)
            if not azd:
                # Na ten moment nie chcemy wpisów odnosnie dyscyplin i slotów, gdy nie ma
                # w nich żadnych autorów (zgłoszenie w Mantis #1009)
                continue

            Cache_Punktacja_Dyscypliny.objects.create(
                rekord_id=[pk[0], pk[1]],
                dyscyplina=dyscyplina,
                pkd=self.slot.punkty_pkd(dyscyplina),
                slot=_slot_cache[dyscyplina],
                autorzy_z_dyscypliny=[a.pk for a in azd],
                zapisani_autorzy_z_dyscypliny=[a.zapisany_jako for a in azd],
            )

        if not self.original.pk:
            return

        for wa in self.original.autorzy_set.all():
            if (
                not wa.afiliuje
                or not wa.jednostka.skupia_pracownikow
                or not wa.przypieta
            ):
                # Jeżeli autor NIE afiliuje lub afiliuje, ale jednostka nie skupia
                # pracowników (czyli jest OBCA, czyli realnie wpis błędny), lub
                # dyscyplina jest "odpięta" to nie licz punktów dla takiego autora
                continue

            dyscyplina = wa.okresl_dyscypline()
            if dyscyplina is None:
                continue

            pkdaut = self.slot.pkd_dla_autora(wa)
            if pkdaut is None:
                continue

            Cache_Punktacja_Autora.objects.create(
                rekord_id=[pk[0], pk[1]],
                autor_id=wa.autor_id,
                jednostka_id=wa.jednostka_id,
                dyscyplina_id=dyscyplina.pk,
                pkdaut=pkdaut,
                slot=self.slot.slot_dla_autora_z_dyscypliny(dyscyplina),
            )
