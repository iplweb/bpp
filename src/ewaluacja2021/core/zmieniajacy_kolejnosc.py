from operator import attrgetter

from .prosty import Prosty, Randomizer


class ZmieniajacyKolejnosc(Prosty):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

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
