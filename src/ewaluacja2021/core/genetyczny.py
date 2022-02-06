import itertools
import math
import os
import random
from operator import attrgetter

# import multiprocessing
import billiard as multiprocessing
import pygad

from .ewaluacja3n_base import Ewaluacja3NBase
from .genetyczny_multiprocessing import (
    FitnessFuncMixin,
    MultiprocessingGAD,
    multiprocessing_gad_pool_initializer,
)
from .util import splitEveryN


class GAD(FitnessFuncMixin, Ewaluacja3NBase):
    def __init__(
        self,
        nazwa_dyscypliny="nauki medyczne",
        max_gen=1000,
        saturate=500,
        ile_najlepszych=50,
        ile_losowych=100,
        ile_zupelnie_losowych=50,
        ile_epok=5,
        output_path=None,
    ):
        Ewaluacja3NBase.__init__(
            self=self, nazwa_dyscypliny=nazwa_dyscypliny, output_path=output_path
        )

        self.get_data()

        self.saturate = saturate

        self.max_gen = max_gen
        self.best_pkd = 0
        self.starting_pkd = 0

        self.maks_epok = ile_epok

        self.lista_prac_dict = {x.id: x for x in self.lista_prac_tuples}

        self.ile_najlepszych = ile_najlepszych
        self.ile_losowych = ile_losowych
        self.ile_zupelnie_losowych = ile_zupelnie_losowych

    def on_generation(self, ga_instance: pygad.GA):
        no_generations = ga_instance.generations_completed or 1
        best_solution = ga_instance.best_solution()

        print(
            f"Generacja: {no_generations}\t"
            f"Procent: {no_generations * 100 // self.max_gen} \t"
            f"Najlepsze rozwiązanie: {best_solution[1]}\t"
            "\r",
            end="",
        )

    def pracuj(self):

        self.lista_prac_by_index = {
            idx: praca for idx, praca in enumerate(self.lista_prac_tuples)
        }
        self.index_prac_by_id = {
            praca.id: idx for idx, praca in self.lista_prac_by_index.items()
        }

        self.najlepszy_osobnik = [
            self.index_prac_by_id[x.id]
            for x in sorted(
                self.lista_prac_tuples,
                key=lambda x: attrgetter("pkdaut")(x) / attrgetter("slot")(x),
                reverse=True,
            )
        ]

        no_workers = int(math.ceil(os.cpu_count() * 0.75))

        self.pool = multiprocessing.Pool(
            processes=no_workers,
            initializer=multiprocessing_gad_pool_initializer,
            initargs=(
                self.lista_prac_by_index,
                self.liczba_2_2_n,
                self.liczba_0_8_n,
                self.maks_pkt_aut_calosc,
                self.maks_pkt_aut_monografie,
            ),
        )

        def cykl_genetyczny(najlepszy_osobnik, nr_cyklu):

            osbn_czesciowo_losowe = []

            baza_dla_randomizera = najlepszy_osobnik

            # Generuje połowe osobnikow losowych
            # Tutaj osobnik losowy ma zamieniane geny losowo w zakresie od 20% do 80%
            dlugosc = len(baza_dla_randomizera)
            start = dlugosc // 5
            end = dlugosc * 3 // 5
            for a in range(self.ile_losowych // 2):
                start = random.randint(start, end)
                end = random.randint(start, dlugosc)
                osobnik = (
                    baza_dla_randomizera[:start]
                    + random.sample(baza_dla_randomizera[start:end], end - start)
                    + baza_dla_randomizera[end:]
                )
                osbn_czesciowo_losowe.append(osobnik)

            # Generuje druga połowe losowych
            # Tutaj osobnik losowy ma zamieniane segmenty genów losowo, tzn jest dzielony
            # na od 4 do 50 czesci i te czesci ma potem łączone w losowy sposób
            for a in range(self.ile_losowych // 2):
                num_parts = random.randint(2, 50)
                split_size = dlugosc // num_parts
                if split_size == 0:
                    split_size = 1

                parts = splitEveryN(split_size, najlepszy_osobnik)
                random.shuffle(parts)
                osobnik = list(itertools.chain(*parts))
                osbn_czesciowo_losowe.append(osobnik)

            osbn_losowe = [  # noqa
                random.sample(baza_dla_randomizera, len(baza_dla_randomizera))
                for n in range(self.ile_zupelnie_losowych)
            ]

            initial_population = (
                [najlepszy_osobnik] * self.ile_najlepszych
                + osbn_losowe
                + osbn_czesciowo_losowe
            )

            sum_all = sum(praca.pkdaut for praca in self.lista_prac_tuples)

            # mutation

            self.ga_instance = MultiprocessingGAD(
                pool=self.pool,
                num_generations=self.max_gen,
                num_parents_mating=2,
                initial_population=initial_population,
                gene_type=int,
                gene_space=baza_dla_randomizera,
                crossover_type="single_point",
                mutation_type="swap",
                # mutation_num_genes=int(math.ceil(len(najlepszy_osobnik) * 0.5)),
                on_generation=lambda s: self.on_generation(s),
                stop_criteria=[f"reach_{sum_all}", f"saturate_{self.saturate}"],
            )

            self.ga_instance.run()

            solution, fitness, idx = self.ga_instance.best_solution()

            print(f"\n\nNajlepsze rozwiązanie z algorytmu genetycznego: {fitness}")

            solution = solution.tolist()
            print("Przeprowadzam przesuwanie bąbelkowe...")
            direction = 1
            ile_razy_nie_znaleziono_lepszych = 0
            while True:

                znaleziono_lepsze = False

                for a in range(0, len(solution)):
                    if a == 0 and direction == 1:
                        continue

                    if a == len(solution) - 1 and direction == -1:
                        continue

                    new_solution = solution[:]
                    if direction == 1:
                        new_solution.insert(0, new_solution.pop(a))
                    else:
                        new_solution.append(new_solution.pop(a))

                    self.fitness_func(new_solution)

                    if self.suma_pkd > fitness:
                        fitness = self.suma_pkd
                        print(
                            f"Nowe rozwiązanie z przesuwania bąbelkowego: {fitness}\r",
                            end="",
                        )
                        solution = new_solution
                        ile_razy_nie_znaleziono_lepszych = 0
                        znaleziono_lepsze = True

                if not znaleziono_lepsze:
                    direction = -direction
                    ile_razy_nie_znaleziono_lepszych += 1

                    if ile_razy_nie_znaleziono_lepszych == 2:
                        # Nie znaleziono lepszych zestawów w obydwu kierunkach
                        break

            self.fitness_func(solution)
            print(f"Po przesuwaniu bąbelkowym: {self.suma_pkd}")

            return solution

        self.suma_pkd = 0
        ile_epok = 0

        solution = self.najlepszy_osobnik

        while ile_epok < self.maks_epok:  # and poprzedni_wynik < self.suma_pkd:
            ile_epok += 1
            print(f"Obliczam epoke nr {ile_epok}")
            solution = cykl_genetyczny(solution, nr_cyklu=ile_epok)
            self.fitness_func(solution)

        # self.fitness_func(solution)
        self.lista_prac = self.lista_prac_tuples

    def pozegnanie(self):
        print(
            "Number of generations passed is {generations_completed}".format(
                generations_completed=self.ga_instance.generations_completed
            )
        )

        print("Najlepsza punktacja:", self.ga_instance.best_solution()[1])
