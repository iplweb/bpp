import itertools
import os
import random
import time
from operator import attrgetter

import matplotlib
import pygad

from ..util import SHUFFLE_TYPE, shuffle_array
from .mixins import Ewaluacja3NMixin
from .util import splitEveryN

from bpp.util import pbar


class GAD(Ewaluacja3NMixin):
    def __init__(
        self,
        nazwa_dyscypliny="nauki medyczne",
        max_gen=1000,
        saturate=300,
        ile_najlepszych=40,
        ile_losowych=50,
        ile_zupelnie_losowych=30,
        ile_epok=10,
        enable_bubbles=True,
        enable_swapper=False,
        enable_mutation=False,
        output_path=None,
    ):
        Ewaluacja3NMixin.__init__(
            self=self, nazwa_dyscypliny=nazwa_dyscypliny, output_path=output_path
        )

        self.get_data()

        self.saturate = saturate

        self.max_gen = max_gen
        self.best_pkd = 0
        self.starting_pkd = 0

        self.maks_epok = ile_epok

        self.enable_bubbles = enable_bubbles
        self.enable_swapper = enable_swapper
        self.enable_mutation = enable_mutation

        self.lista_prac_dict = {x.id: x for x in self.lista_prac_tuples}

        self.ile_najlepszych = ile_najlepszych
        self.ile_losowych = ile_losowych
        self.ile_zupelnie_losowych = ile_zupelnie_losowych

    def fitness_func(
        self, lista_prac, solution_idx, silent=False, swap_idx_a=None, swap_idx_b=None
    ):
        self.zeruj()

        for praca_idx in lista_prac:

            # Jezeli praca_idx jest rowna swap_idx_a, to zamiast pracy praca_idx
            # weź pracę swap_idx_b i na odwrót:
            if praca_idx == swap_idx_a:
                praca_idx = swap_idx_b
            elif praca_idx == swap_idx_b:
                praca_idx = swap_idx_a

            praca_tuple = self.lista_prac_by_index.get(praca_idx, None)
            if praca_tuple is None:
                print(f"BRAK PRACY O INDEKSIE {praca_idx}")
                continue

            if self.czy_moze_przejsc(praca_tuple):
                self.zsumuj_pojedyncza_prace(praca_tuple, praca_idx)

        return self.suma_pkd

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

    def plot_fitness(
        self,
        title="PyGAD - Generation vs. Fitness",
        xlabel="Generation",
        ylabel="Fitness",
        linewidth=3,
        font_size=14,
        plot_type="plot",
        color="#3870FF",
        save_dir=None,
        filename_prefix="",
        filename_suffix="",
    ):

        self = self.ga_instance

        fig = matplotlib.pyplot.figure()
        if plot_type == "plot":
            matplotlib.pyplot.plot(
                self.best_solutions_fitness, linewidth=linewidth, color=color
            )
        elif plot_type == "scatter":
            matplotlib.pyplot.scatter(
                range(self.generations_completed + 1),
                self.best_solutions_fitness,
                linewidth=linewidth,
                color=color,
            )
        elif plot_type == "bar":
            matplotlib.pyplot.bar(
                range(self.generations_completed + 1),
                self.best_solutions_fitness,
                linewidth=linewidth,
                color=color,
            )
        matplotlib.pyplot.title(title, fontsize=font_size)
        matplotlib.pyplot.xlabel(xlabel, fontsize=font_size)
        matplotlib.pyplot.ylabel(ylabel, fontsize=font_size)

        if save_dir is not None:
            matplotlib.pyplot.savefig(
                fname=os.path.join(
                    save_dir, f"{filename_prefix}fitness{filename_suffix}.png"
                ),
                bbox_inches="tight",
            )

        return fig

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
                parts = splitEveryN(
                    max(dlugosc // num_parts, dlugosc), najlepszy_osobnik
                )
                random.shuffle(parts)
                osobnik = list(itertools.chain(*parts))
                osbn_czesciowo_losowe.append(osobnik)

            osbn_losowe = [
                random.sample(baza_dla_randomizera, len(baza_dla_randomizera))
                for n in range(self.ile_zupelnie_losowych)
            ]

            initial_population = (
                [najlepszy_osobnik] * self.ile_najlepszych
                + osbn_losowe
                + osbn_czesciowo_losowe
            )

            sum_all = sum(praca.pkdaut for praca in self.lista_prac_tuples)

            self.ga_instance = pygad.GA(
                num_generations=self.max_gen,
                num_parents_mating=2,
                initial_population=initial_population,
                gene_type=int,
                gene_space=baza_dla_randomizera,
                crossover_type="single_point",
                mutation_type="swap",
                on_generation=lambda s: self.on_generation(s),
                fitness_func=lambda a, b: self.fitness_func(a, b),
                stop_criteria=[f"reach_{sum_all}", f"saturate_{self.saturate}"],
            )

            self.ga_instance.run()

            solution, fitness, idx = self.ga_instance.best_solution()

            print(f"\n\nNajlepsze rozwiązanie z algorytmu genetycznego: {fitness}")
            print("Sprawdz wykres wydajnosci.")

            self.plot_fitness(
                title=f"{self.nazwa_dyscypliny} - cykl {nr_cyklu}",
                xlabel="generacja",
                ylabel="suma PKDaut",
                save_dir=self.output_path,
                filename_suffix=f"_{nr_cyklu}",
            )

            solution = solution.tolist()

            if self.enable_bubbles:
                # bubble
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

                        self.fitness_func(new_solution, None)

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

            if self.enable_swapper:
                # swapper
                print("Przeprowadzam swapping")

                seen_pairs = set()

                for a in pbar(range(len(solution)), count=len(solution)):
                    for b in range(len(solution)):
                        if a == b:
                            continue

                        if (a, b) in seen_pairs:
                            continue

                        self.fitness_func(
                            new_solution, None, swap_idx_a=a, swap_idx_b=b
                        )

                        seen_pairs.add((a, b))
                        seen_pairs.add((b, a))

                        if self.suma_pkd > fitness:
                            fitness = self.suma_pkd
                            print(f"\nswap lepsze rozwiazanie: {fitness} {b} {a}\n")

                            tmp = solution[a]
                            solution[a] = solution[b]
                            solution[b] = tmp
                            seen_pairs = set()

            if self.enable_mutation:
                # mutator
                print("Mutuje losowo przez nastepne 5 minut...")
                a = 0
                czas_start = time.monotonic()
                while (time.monotonic() - czas_start) < 5 * 60:
                    start = random.randint(0, len(solution))
                    end = random.randint(start, len(solution))
                    new_solution = shuffle_array(
                        solution,
                        start,
                        end,
                        no_shuffles=random.randint(1, 3),
                        shuffle_type=random.choice(
                            [SHUFFLE_TYPE.BEGIN, SHUFFLE_TYPE.MIDDLE, SHUFFLE_TYPE.END]
                        ),
                    )
                    self.fitness_func(new_solution, a)
                    if a % 10:
                        print("A: %i %.2f\r" % (a, a * 100 / len(solution)), end="")
                    if self.suma_pkd > fitness:
                        fitness = self.suma_pkd
                        solution = new_solution
                        print(
                            "\nNEW best solution",
                            self.suma_pkd,
                            f"mutacja na {start} {end}",
                        )

            return solution

        solution = self.najlepszy_osobnik
        poprzedni_wynik = 0
        self.fitness_func(solution, None)

        ile_epok = 0

        while ile_epok < self.maks_epok and poprzedni_wynik < self.suma_pkd:
            ile_epok += 1
            poprzedni_wynik = self.suma_pkd
            print(f"Obliczam epoke nr {ile_epok}")
            solution = cykl_genetyczny(solution, nr_cyklu=ile_epok)

        # self.fitness_func(solution)
        self.lista_prac = self.lista_prac_tuples

    def pozegnanie(self):
        print(
            "Number of generations passed is {generations_completed}".format(
                generations_completed=self.ga_instance.generations_completed
            )
        )

        print("Najlepsza punktacja:", self.ga_instance.best_solution()[1])
