from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from bpp.models import const, Typ_Odpowiedzialnosci
from bpp.models.cache import Cache_Punktacja_Dyscypliny, Cache_Punktacja_Autora
from bpp.models.sloty.wydawnictwo_ciagle import SlotKalkulator_Wydawnictwo_Ciagle_Prog3
from bpp.models.sloty.wydawnictwo_zwarte import SlotKalkulator_Wydawnictwo_Zwarte_Prog3, \
    SlotKalkulator_Wydawnictwo_Zwarte_Prog2, SlotKalkulator_Wydawnictwo_Zwarte_Prog1
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from .exceptions import CannotAdapt
from .wydawnictwo_ciagle import SlotKalkulator_Wydawnictwo_Ciagle_Prog1, SlotKalkulator_Wydawnictwo_Ciagle_Prog2


def ISlot(original):
    if isinstance(original, Wydawnictwo_Ciagle):
        if original.rok in [2017, 2018]:
            if original.punkty_kbn >= 30:
                return SlotKalkulator_Wydawnictwo_Ciagle_Prog1(original)
            elif original.punkty_kbn in [20, 25]:
                return SlotKalkulator_Wydawnictwo_Ciagle_Prog2(original)
            elif original.punkty_kbn < 20:
                return SlotKalkulator_Wydawnictwo_Ciagle_Prog3(original)

        elif original.rok in [2019, 2020]:
            if original.punkty_kbn in [200, 140, 100]:
                return SlotKalkulator_Wydawnictwo_Ciagle_Prog1(original)
            elif original.punkty_kbn in [70, 40]:
                return SlotKalkulator_Wydawnictwo_Ciagle_Prog2(original)
            elif original.punkty_kbn <= 20:
                return SlotKalkulator_Wydawnictwo_Ciagle_Prog3(original)

        raise CannotAdapt(
            "Punkty KBN rekordu (%s) i rok (%s) nie pozwalają na dopasowanie tego rekordu do jakiejkolwiek grupy" % (
            original.punkty_kbn, original.rok))

    elif isinstance(original, Wydawnictwo_Zwarte):
        if original.rok < 2017 or original.rok > 2020:
            raise CannotAdapt("Rok poza zakresem procedur liczacych (%s). " % original.rok)

        rozdzial = ksiazka = autorstwo = redakcja = False

        poziom_wydawcy = -1

        if original.charakter_formalny.charakter_sloty == const.CHARAKTER_SLOTY_ROZDZIAL:
            rozdzial = True

        if original.charakter_formalny.charakter_sloty == const.CHARAKTER_SLOTY_KSIAZKA:
            ksiazka = True

        if ksiazka and rozdzial:
            raise NotImplementedError("To sie nie powinno wydarzyc)")

        if ksiazka:
            for elem in Typ_Odpowiedzialnosci.objects.filter(
                    pk__in=original.autorzy_set.values_list("typ_odpowiedzialnosci_id")).distinct():
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

        if original.wydawca_id is not None:
            poziom_wydawcy = original.wydawca.get_tier(original.rok)

        if poziom_wydawcy == 2:
            if (ksiazka and autorstwo and original.punkty_kbn == 200) or \
                    (ksiazka and redakcja and original.punkty_kbn == 100) or \
                    (rozdzial and original.punkty_kbn == 50):
                return SlotKalkulator_Wydawnictwo_Zwarte_Prog1(original)

        elif poziom_wydawcy == 1:
            if (ksiazka and autorstwo and original.punkty_kbn == 80) or \
                    (ksiazka and redakcja and original.punkty_kbn == 20) or \
                    (rozdzial and original.punkty_kbn == 20):
                return SlotKalkulator_Wydawnictwo_Zwarte_Prog2(original)

        else:
            if (ksiazka and autorstwo and original.punkty_kbn == 20) or \
                    (ksiazka and redakcja and original.punkty_kbn == 5) or \
                    (rozdzial and original.punkty_kbn == 5):
                return SlotKalkulator_Wydawnictwo_Zwarte_Prog3(original)

        raise CannotAdapt("Rekordu nie można dopasować do żadnej z grup monografii. Poziom "
                          "wydawcy: %(poziom_wydawcy)s, ksiazka: %(ksiazka)s, rozdzial: %(rozdzial)s, "
                          "autorstwo: %(autorstwo)s, redakcja: %(redakcja)s, punkty kbn: %(punkty_kbn)s" % dict(
            poziom_wydawcy=poziom_wydawcy,
            ksiazka=ksiazka,
            rozdzial=rozdzial,
            autorstwo=autorstwo,
            redakcja=redakcja,
            punkty_kbn=original.punkty_kbn
        ))

    if hasattr(original, 'rok') and hasattr(original, 'punkty_kbn'):
        raise CannotAdapt(
            "Nie umiem policzyc dla %s rok %s punkty_kbn %s" % (
                original,
                original.rok,
                original.punkty_kbn))

    raise CannotAdapt("Nie umiem policzyć dla obiektu: %r" % original)


class IPunktacjaCacher:
    def __init__(self, original):
        self.original = original
        self.slot = None

    def canAdapt(self):
        try:
            self.slot = ISlot(self.original)
            return True

        except CannotAdapt:
            return False

    @transaction.atomic
    def rebuildEntries(self):

        pk = (
            ContentType.objects.get_for_model(self.original).pk,
            self.original.pk
        )

        Cache_Punktacja_Dyscypliny.objects.filter(rekord_id=pk).delete()
        Cache_Punktacja_Autora.objects.filter(rekord_id=pk).delete()

        # Jeżeli nie można zaadaptować danego rekordu do kalkulatora
        # punktacji, to po skasowaniu ewentualnej scache'owanej punktacji
        # wyjdź z funkcji:
        if self.canAdapt() is False:
            return

        _slot_cache = {}

        for dyscyplina in self.slot.dyscypliny:
            _slot_cache[dyscyplina] = self.slot.slot_dla_dyscypliny(dyscyplina)
            Cache_Punktacja_Dyscypliny.objects.create(
                rekord_id=pk,
                dyscyplina=dyscyplina,
                pkd=self.slot.punkty_pkd(dyscyplina),
                slot=_slot_cache[dyscyplina]
            )

        for wa in self.original.autorzy_set.all():
            dyscyplina = wa.okresl_dyscypline()
            if dyscyplina is None:
                continue

            pkdaut = self.slot.pkd_dla_autora(wa)
            if pkdaut is None:
                continue

            Cache_Punktacja_Autora.objects.create(
                rekord_id=pk,
                autor_id=wa.autor_id,
                dyscyplina_id=dyscyplina.pk,
                pkdaut=pkdaut,
                slot=self.slot.slot_dla_autora_z_dyscypliny(dyscyplina)
            )
