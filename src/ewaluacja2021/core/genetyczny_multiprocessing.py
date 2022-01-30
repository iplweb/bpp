import numpy
import pygad

from .sumator_base import SumatorBase


class FitnessFuncMixin:
    def fitness_func(self, lista_prac):
        self.zeruj()
        for praca_idx in lista_prac:
            praca_tuple = self.lista_prac_by_index.get(praca_idx, None)
            assert praca_tuple is not None, "Brak pracy o indeksie"
            if self.czy_moze_przejsc(praca_tuple):
                self.zsumuj_pojedyncza_prace(praca_tuple, praca_idx)
        return self.suma_pkd


class GenetycznySumator(FitnessFuncMixin, SumatorBase):
    def __init__(self, lista_prac_by_index, *args, **kw):
        super().__init__(*args, **kw)
        self.lista_prac_by_index = lista_prac_by_index


def fitness_wrapper(lista_prac):
    return fitness_wrapper.instancja_genetycznego_sumatora.fitness_func(lista_prac)


def multiprocessing_gad_pool_initializer(
    lista_prac_by_index,
    liczba_2_2_n,
    liczba_0_8_n,
    maks_pkt_aut_calosc,
    maks_pkt_aut_monografie,
):
    """Ta funkcja wywoływana jest przy inicjalizacji multiprocessing.Pool.

    Tworzy ona instancję sumatora genetycznego a następnie zapisuje go jako atrybut
    funkcji fitness_wrapper (coby nie używać "global").

    W ten sposób funkcja fitness_wrapper
    może wywołać później funkcję sumatora genetycznego fitness_func celem obliczenia punktacji
    dla populacji w sposób wielowątkowy."""
    sumator = GenetycznySumator(
        lista_prac_by_index=lista_prac_by_index,
        liczba_2_2_n=liczba_2_2_n,
        liczba_0_8_n=liczba_0_8_n,
        maks_pkt_aut_calosc=maks_pkt_aut_calosc,
        maks_pkt_aut_monografie=maks_pkt_aut_monografie,
    )

    fitness_wrapper.instancja_genetycznego_sumatora = sumator


class MultiprocessingGAD(pygad.GA):
    def __init__(self, pool, *args, **kw):
        assert (
            "fitness_func" not in kw
        ), "Argument nie obsługiwany - fitness_func jest ustalone na sztywno w tej klasie"
        super().__init__(fitness_func=GenetycznySumator.fitness_func, *args, **kw)
        self.pool = pool

    def cal_pop_fitness(self):
        pop_fitness = self.pool.map(fitness_wrapper, self.population)
        pop_fitness = numpy.array(pop_fitness)
        return pop_fitness
