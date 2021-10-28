import logging
import random
from collections import defaultdict, namedtuple
from datetime import datetime
from decimal import Decimal
from operator import attrgetter

import simplejson
from django.db.models import F, Sum, Transform

from ewaluacja2021.models import IloscUdzialowDlaAutora, LiczbaNDlaUczelni
from ewaluacja2021.util import shuffle_array
from pbn_api.integrator import PBN_MIN_ROK

from django.contrib.postgres.aggregates import ArrayAgg

from bpp.models import Cache_Punktacja_Autora_Query
from bpp.models.const import RODZAJ_PBN_ARTYKUL
from bpp.util import intsack, pbar

logger = logging.getLogger(__name__)

Praca = namedtuple(
    "Praca",
    [
        "id",
        "rekord_id",
        "slot",
        "autor_id",
        "rok",
        "pkdaut",
        "monografia",
        "autorzy",
        "ostatnio_zmieniony",
    ],
)

LATA_2019_2021 = 0
LATA_2017_2018 = 1

# LICZBA_N = 554.84  # nauki medyczne

DEC2INT = 10000

DEFAULT_MAX_SLOT_AUT = 4
DEFAULT_MAX_SLOT_MONO = 2


class NieArtykul(Transform):
    template = f"(%(expressions)s != {RODZAJ_PBN_ARTYKUL})"


def get_lista_prac(nazwa_dyscypliny):

    return (
        Cache_Punktacja_Autora_Query.objects.filter(
            rekord__rok__gte=PBN_MIN_ROK,
            dyscyplina__nazwa=nazwa_dyscypliny,
        )
        .exclude(rekord__charakter_formalny__charakter_ogolny=None)
        .annotate(
            monografia=NieArtykul(F("rekord__charakter_formalny__rodzaj_pbn")),
            rok=F("rekord__rok"),
        )
        .select_related(
            "rekord",
            "rekord__charakter_formalny",
        )
    )


def get_lista_autorow_na_rekord(nazwa_dyscypliny):
    return dict(
        [
            (x["rekord_id"], tuple(x["autorzy"]))
            for x in get_lista_prac(nazwa_dyscypliny)
            .values("rekord_id")
            .annotate(autorzy=ArrayAgg("autor_id"))
            .order_by()
        ]
    )


def lista_prac_na_tuples(lista_prac, lista_autorow):
    return tuple(
        [
            Praca(
                id=elem.id,
                rekord_id=elem.rekord_id,
                slot=elem.slot,
                autor_id=elem.autor_id,
                rok=elem.rekord.rok,
                pkdaut=elem.pkdaut,
                monografia=elem.monografia,
                autorzy=lista_autorow.get(elem.rekord_id),
                ostatnio_zmieniony=elem.rekord.ostatnio_zmieniony,
            )
            for elem in lista_prac
        ]
    )


def get_lista_prac_as_tuples(nazwa_dyscypliny):
    return lista_prac_na_tuples(
        list(get_lista_prac(nazwa_dyscypliny)),
        get_lista_autorow_na_rekord(nazwa_dyscypliny),
    )


def policz_knapsack(lista_prac, maks_slot=4.0):
    res = intsack(
        maks_slot,
        [x.slot for x in lista_prac],
        [x.pkdaut for x in lista_prac],
        [x for x in lista_prac],
    )
    return res


def encode_datetime(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(
        "Object of type %s is not JSON serializable" % obj.__class__.__name__
    )


def maks_pkt_aut_calosc_get_from_db(nazwa_dyscypliny):
    return {
        x["autor_id"]: x["ilosc_udzialow"]
        for x in IloscUdzialowDlaAutora.objects.filter(
            dyscyplina_naukowa__nazwa=nazwa_dyscypliny
        ).values("autor_id", "ilosc_udzialow")
    }


def maks_pkt_aut_monografie_get_from_db(nazwa_dyscypliny):
    return {
        x["autor_id"]: x["ilosc_udzialow_monografie"]
        for x in IloscUdzialowDlaAutora.objects.filter(
            dyscyplina_naukowa__nazwa=nazwa_dyscypliny
        ).values("autor_id", "ilosc_udzialow_monografie")
    }


class Ewaluacja3NMixin:
    def __init__(
        self,
        nazwa_dyscypliny="nauki medyczne",
        liczba_n=None,
        maks_pkt_aut_calosc=None,
        maks_pkt_aut_monografie=None,
    ):
        """
        maks_pkt_aut_calosc
            maksymalna ilość punktów dla poszczególnych autorów, słownik autor->maks pkt

        maks_pkt_aut_monografie
            maksymalna ilość punktów dla autorów za monografie, słownik autor->maks pkt

        """

        self.nazwa_dyscypliny = nazwa_dyscypliny
        self.liczba_n = liczba_n
        self.maks_pkt_aut_calosc = maks_pkt_aut_calosc
        if self.maks_pkt_aut_calosc is None:
            self.maks_pkt_aut_calosc = maks_pkt_aut_calosc_get_from_db(
                self.nazwa_dyscypliny
            )

        self.maks_pkt_aut_monografie = maks_pkt_aut_monografie
        if self.maks_pkt_aut_monografie is None:
            self.maks_pkt_aut_monografie = maks_pkt_aut_monografie_get_from_db(
                self.nazwa_dyscypliny
            )

        if self.liczba_n is None:
            self.liczba_n = LiczbaNDlaUczelni.objects.get(
                dyscyplina_naukowa__nazwa=self.nazwa_dyscypliny
            ).liczba_n
        self.liczba_2_2_n = Decimal("2.2") * self.liczba_n
        self.liczba_2_2_n_minus_2 = self.liczba_2_2_n - 2

        self.liczba_0_8_n = Decimal("0.8") * self.liczba_n
        self.liczba_0_8_n_minus_2 = self.liczba_0_8_n - 2

    def zeruj(self):
        self.suma_pkd = 0
        self.sumy_slotow = [0, 0]

        self.suma_prac_autorow_wszystko = defaultdict(int)
        self.suma_prac_autorow_monografie = defaultdict(int)

        self.id_rekordow = set()

    def get_data(self):
        logger.info("get_data start")
        self.autorzy_na_rekord = get_lista_autorow_na_rekord(self.nazwa_dyscypliny)

        self.id_wszystkich_autorow = set()
        for elem in self.autorzy_na_rekord.values():
            for x in elem:

                self.id_wszystkich_autorow.add(x)

        self.lista_prac_db = get_lista_prac(self.nazwa_dyscypliny)
        self.lista_prac_tuples = lista_prac_na_tuples(
            self.lista_prac_db, self.autorzy_na_rekord
        )
        logger.info("get_data finished")

    def czy_moze_przejsc_warunek_uczelnia(self, praca):
        if (
            self.sumy_slotow[LATA_2019_2021] < self.liczba_2_2_n_minus_2
            and self.sumy_slotow[LATA_2017_2018] < self.liczba_0_8_n_minus_2
        ):
            return True

        # Czy uczelnia nie ma już dość takich publikacji?
        if praca.rok >= 2019:
            if self.sumy_slotow[LATA_2019_2021] + praca.slot > self.liczba_2_2_n:
                return False
        else:
            if self.sumy_slotow[LATA_2017_2018] + praca.slot > self.liczba_0_8_n:
                return False

        # Uczelnia nie ma dość takich publikacji. Idziemy dalej.
        return True

    def czy_moze_przejsc_warunek_autor(self, praca):
        # Czy autor nie ma dość takich publikacji?
        if self.suma_prac_autorow_wszystko[
            praca.autor_id
        ] + praca.slot > self.maks_pkt_aut_calosc.get(
            praca.autor_id, DEFAULT_MAX_SLOT_AUT * DEC2INT
        ):
            return False

        # Jeżeli to jest monografia - czy autor nie ma dość już takich punktów za monografię?
        if praca.monografia:
            if self.suma_prac_autorow_monografie[
                praca.autor_id
            ] + praca.slot > self.maks_pkt_aut_monografie.get(
                praca.autor_id, DEFAULT_MAX_SLOT_MONO * DEC2INT
            ):
                return False

        return True

    def czy_moze_przejsc(self, praca):
        if self.czy_moze_przejsc_warunek_uczelnia(
            praca
        ) and self.czy_moze_przejsc_warunek_autor(praca):
            return True

    def zsumuj_pojedyncza_prace(self, praca):
        self.suma_pkd += praca.pkdaut

        # Tu dodajemy Cache_Punktacja_Autora.id, nie zaś rekord_id
        self.id_rekordow.add(praca.id)

        if praca.rok >= 2019:
            self.sumy_slotow[LATA_2019_2021] += praca.slot
        else:
            self.sumy_slotow[LATA_2017_2018] += praca.slot

        self.suma_prac_autorow_wszystko[praca.autor_id] += praca.slot
        if praca.monografia:
            self.suma_prac_autorow_monografie[praca.autor_id] += praca.slot

    def powitanie(self):
        print(
            f"Szukam dla: {self.nazwa_dyscypliny}, liczba N: {self.liczba_n}, 2.2*N: {self.liczba_2_2_n}, "
            f"0.8*N: {self.liczba_0_8_n}"
        )

    def pozegnanie(self):
        print(
            f"Obecna maks pkd: {self.suma_pkd}, suma slotow: {self.sumy_slotow}, ilosc prac: {len(self.id_rekordow)}"
        )

    def zrzuc_dane(self, nazwa):
        output = {
            "ostatnia_zmiana": getattr(
                max(self.lista_prac, key=attrgetter("ostatnio_zmieniony")),
                "ostatnio_zmieniony",
                "brak rekordów",
            ),
            "dyscyplina": self.nazwa_dyscypliny,
            "liczba_n": self.liczba_n,
            "liczba_0_8_n": self.liczba_0_8_n,
            "liczba_2_2_n": self.liczba_2_2_n,
            "sumy_slotow": self.sumy_slotow,
            "maks_pkt_aut_calosc": self.maks_pkt_aut_calosc,
            "maks_pkt_aut_monografie": self.maks_pkt_aut_monografie,
            "wejscie": [x for x in self.lista_prac],
            "wyjscie": [x for x in self.aktualna_lista_prac],
            "optimum": [x for x in self.id_rekordow],
        }

        nazwa = nazwa + "_" + str(self.suma_pkd).replace(".", "_") + ".json"
        with open(nazwa, "w") as f:
            simplejson.dump(
                output,
                f,
                indent=4,
                use_decimal=True,
                namedtuple_as_object=True,
                tuple_as_array=True,
                default=encode_datetime,
            )

        print(f"Dane zrzucone do {nazwa}")


class Plecakowy(Ewaluacja3NMixin):
    def __init__(
        self,
        nazwa_dyscypliny="nauki medyczne",
        liczba_n=None,
        maks_pkt_aut_calosc=None,
        maks_pkt_aut_monografia=None,
    ):
        Ewaluacja3NMixin.__init__(
            self=self,
            nazwa_dyscypliny=nazwa_dyscypliny,
            liczba_n=liczba_n,
            maks_pkt_aut_calosc=maks_pkt_aut_calosc,
            maks_pkt_aut_monografie=maks_pkt_aut_monografia,
        )

        self.get_data()

    @property
    def lista_prac(self):
        return self.lista_prac_tuples

    @property
    def aktualna_lista_prac(self):
        return self.lista_prac_tuples

    def get_lista_autorow_w_kolejnosci(self):

        punkty_na_id_autora = {
            i["autor_id"]: i["pkdaut__sum"]
            for i in Cache_Punktacja_Autora_Query.objects.values("autor_id").annotate(
                Sum("pkdaut")
            )
        }

        id_autorow = sorted(
            list(self.id_wszystkich_autorow),
            key=lambda item: punkty_na_id_autora[item],
            reverse=True,
        )

        return id_autorow

    def sumuj(self):

        self.zeruj()

        for autor_id in pbar(self.get_lista_autorow_w_kolejnosci()):

            wszystkie = list(
                [
                    praca
                    for praca in self.lista_prac_db.filter(autor_id=autor_id)
                    if self.czy_moze_przejsc_warunek_uczelnia(praca)
                ]
            )

            monografie = [x for x in wszystkie if x.monografia]

            slot_za_monografie = 0
            if monografie:
                pkt, prace = policz_knapsack(
                    monografie,
                    maks_slot=2.0,
                )

                [self.zsumuj_pojedyncza_prace(x) for x in prace]

            nie_monografie = [x for x in wszystkie if not x.monografia]

            if nie_monografie:
                pkt, prace = policz_knapsack(
                    nie_monografie,
                    maks_slot=4.0 - float(slot_za_monografie),
                )

                [self.zsumuj_pojedyncza_prace(x) for x in prace]


class Prosty(Ewaluacja3NMixin):
    def __init__(
        self,
        lista_prac,
        nazwa_dyscypliny="nauki medyczne",
        liczba_n=None,
        maks_pkt_aut_calosc=None,
        maks_pkt_aut_monografia=None,
    ):
        self.lista_prac = lista_prac

        Ewaluacja3NMixin.__init__(
            self=self,
            nazwa_dyscypliny=nazwa_dyscypliny,
            liczba_n=liczba_n,
            maks_pkt_aut_calosc=maks_pkt_aut_calosc,
            maks_pkt_aut_monografie=maks_pkt_aut_monografia,
        )

        self.get_data()

    def get_data(self):
        return

    def get_ordered_lista_prac(self):
        return self.lista_prac

    def sumuj(self):
        self.zeruj()

        self.aktualna_lista_prac = self.get_ordered_lista_prac()

        for praca in self.aktualna_lista_prac:
            if not self.czy_moze_przejsc(praca):
                continue
            self.zsumuj_pojedyncza_prace(praca)

    def promuj_obecna_liste(self):
        self.lista_prac = self.aktualna_lista_prac

    def ustaw_liste(self, lista):
        self.lista_prac = lista


class Randomizer:
    # 1) najlepsze miejsce startowe
    # 2) najlepsza długość listy
    # 3) najlepsza ilość iteracji

    def __init__(
        self,
        lista,
        start_elem=1500,
        end_elem=3000,
        step=100,
        list_size_min=500,
        list_size_max=2502,
        list_step=100,
        no_shuffles=1,
    ):
        self.lista = lista

        self.start_elem = start_elem
        self.end_elem = end_elem
        self.step = step
        self.list_size_min = list_size_min
        self.list_size_max = list_size_max
        self.list_step = list_step
        self.no_shuffles = no_shuffles

        self.reset()

    def reset(
        self,
        start_elem=None,
        end_elem=None,
        step=None,
        no_shuffles=None,
        list_size_min=None,
        list_size_max=None,
        list_step=None,
    ):
        self.a = self.b = None

        if start_elem is None:
            start_elem = self.start_elem + (200 - random.randint(0, 400))

        if end_elem is None:
            end_elem = self.end_elem

        if step is None:
            step = self.step

        if list_size_min is None:
            list_size_min = self.list_size_min

        if list_size_max is None:
            list_size_max = self.list_size_max

        if list_step is None:
            list_step = self.list_step

        if no_shuffles is None:
            no_shuffles = self.no_shuffles

        self.start_range_obj = range(start_elem, end_elem, step)
        self.start_range = iter(self.start_range_obj)

        self.list_length_range_obj = range(list_size_min, list_size_max, list_step)
        self.list_length_range = iter(self.list_length_range_obj)

        self.no_shuffles_range_obj = range(no_shuffles)
        self.no_shuffles_range = iter(self.no_shuffles_range_obj)

        self.current_start_range = None
        self.current_list_length = None
        self.current_no_shuffles = None

        self.a = next(self.start_range)

    def count(self):
        return (
            len(self.start_range_obj)
            * len(self.list_length_range_obj)
            * len(self.no_shuffles_range_obj)
        )

    def __iter__(self):
        return self

    def __next__(self):

        try:
            self.b = next(self.list_length_range)
        except StopIteration:
            try:
                self.a = next(self.start_range)

                self.list_length_range = iter(self.list_length_range_obj)
                self.b = next(self.list_length_range)
            except StopIteration:
                self.a = iter(self.start_range_obj)

                raise StopIteration

        return shuffle_array(self.lista, self.a, self.b, self.no_shuffles)

    def serialize(self):
        return {
            "current_start_range": self.a,
            "current_list_length": self.b,
            "current_no_shuffles": self.current_no_shuffles,
        }


class ZmieniajacyKolejnosc(Prosty):
    def __init__(self, *args, **kw):
        super(ZmieniajacyKolejnosc, self).__init__(*args, **kw)

        self.first_run = True

        self.randomizer = Randomizer(self.get_data())

    def get_data(self):
        return sorted(self.lista_prac, key=attrgetter("pkdaut"), reverse=True)

    def shuffle_random_percent(self):
        return next(self.randomizer)

    def get_ordered_lista_prac(self):
        if self.first_run:
            self.first_run = False
            return self.get_data()

        res = self.shuffle_random_percent()
        return res
