import os
import random
import time
from operator import attrgetter

import matplotlib
import pygad

from ..util import SHUFFLE_TYPE, shuffle_array
from .mixins import Ewaluacja3NMixin

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

        self.enable_bubbles = enable_bubbles
        self.enable_swapper = enable_swapper
        self.enable_mutation = enable_mutation

        self.lista_prac_dict = {x.id: x for x in self.lista_prac_tuples}

        self.ile_najlepszych = ile_najlepszych
        self.ile_losowych = ile_losowych
        self.ile_zupelnie_losowych = ile_zupelnie_losowych

    def fitness_func(self, lista_prac, solution_idx, silent=False):
        self.zeruj()

        for praca_idx in lista_prac:
            praca_tuple = self.lista_prac_by_index.get(praca_idx, None)
            if praca_tuple is None:
                print(f"BRAK PRACY O INDEKSIE {praca_idx}")
                continue

            if self.czy_moze_przejsc(praca_tuple):
                self.zsumuj_pojedyncza_prace(praca_tuple)

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
                fname=os.path.join(save_dir, "fitness.png"), bbox_inches="tight"
            )

        return fig

    def pracuj(self):

        self.lista_prac_by_index = {
            idx: praca for idx, praca in enumerate(self.lista_prac_tuples)
        }
        self.index_prac_by_id = {
            praca.id: idx for idx, praca in self.lista_prac_by_index.items()
        }

        osbn_najlepsze = [
            [
                self.index_prac_by_id[x.id]
                for x in sorted(
                    self.lista_prac_tuples,
                    key=lambda x: attrgetter("pkdaut")(x) / attrgetter("slot")(x),
                    reverse=True,
                )
            ]
        ] * self.ile_najlepszych

        osbn_czesciowo_losowe = []

        baza_dla_randomizera = osbn_najlepsze[0]
        dlugosc = len(baza_dla_randomizera)
        start = dlugosc // 5
        end = dlugosc * 3 // 5
        for a in range(self.ile_losowych):
            start = random.randint(start, end)
            end = random.randint(start, dlugosc)
            osobnik = (
                baza_dla_randomizera[:start]
                + random.sample(baza_dla_randomizera[start:end], end - start)
                + baza_dla_randomizera[end:]
            )
            osbn_czesciowo_losowe.append(osobnik)

        osbn_losowe = [
            random.sample(baza_dla_randomizera, len(baza_dla_randomizera))
            for n in range(self.ile_zupelnie_losowych)
        ]

        initial_population = osbn_najlepsze + osbn_losowe + osbn_czesciowo_losowe

        sum_all = sum(praca.pkdaut for praca in self.lista_prac_tuples)

        self.ga_instance = pygad.GA(
            num_generations=self.max_gen,
            initial_population=initial_population,
            gene_type=int,
            gene_space=baza_dla_randomizera,
            num_parents_mating=2,
            mutation_type="swap",
            crossover_type="two_points",
            on_generation=lambda s: self.on_generation(s),
            fitness_func=lambda a, b: self.fitness_func(a, b),
            stop_criteria=[f"reach_{sum_all}", f"saturate_{self.saturate}"],
        )

        self.ga_instance.run()

        solution, fitness, idx = self.ga_instance.best_solution()

        print(f"\n\nNajlepsze rozwiązanie z algorytmu genetycznego: {fitness}")
        print("Sprawdz wykres wydajnosci.")

        self.plot_fitness(
            title=self.nazwa_dyscypliny,
            xlabel="generacja",
            ylabel="suma PKDaut",
            save_dir=self.output_path,
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

                    praca = self.lista_prac_by_index[solution[a]]
                    if praca.id in self.id_rekordow:
                        # Praca jest juz ostatnich w "zdanych", przesuwanie jej na poczatek
                        # nic nie udowodni (chyba...)
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

            for a in pbar(range(len(solution)), count=len(solution)):
                for b in range(len(solution)):
                    if a == b:
                        continue

                    new_solution = solution[:]
                    swap = new_solution[a]
                    new_solution[a] = new_solution[b]
                    new_solution[b] = swap

                    self.fitness_func(new_solution, None)

                    if self.suma_pkd > fitness:
                        fitness = self.suma_pkd
                        print(f"\nswap lepsze rozwiazanie: {fitness} {b} {a}\n")
                        solution = new_solution

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

        self.lista_prac = self.lista_prac_tuples

    def pozegnanie(self):
        print(
            "Number of generations passed is {generations_completed}".format(
                generations_completed=self.ga_instance.generations_completed
            )
        )

        print("Najlepsza punktacja:", self.ga_instance.best_solution()[1])
