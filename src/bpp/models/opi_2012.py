from django.db import models
from django.db.models import CASCADE

from bpp.fields import YearField
from bpp.models import Wydawnictwo_Zwarte
from bpp.models.autor import Autor
from bpp.models.jednostka import Jednostka
from bpp.util import zrob_cache


class Opi_2012_Afiliacja_Do_Wydzialu(models.Model):
    """Tymczasowa klasa, zawierająca przypisania autorów do wydziałów, ponieważ
    dla pewnej grupy autorów otrzymałem w plikach XLS jedynie afiliację do wydziału,
    nie zaś do jednostki.

    Faza B (#438) II-2: ``wydzial`` wskazuje teraz węzeł ``Jednostka`` (korzeń
    drzewa, mirror dawnego ``Wydzial`` — patrz ``struktura_konwersja.py``).
    """

    # db_index=False: redundantny względem unique_together
    # (autor, wydzial, rok) — autor jest wiodącą kolumną tego indeksu.
    autor = models.ForeignKey(Autor, CASCADE, db_index=False)
    wydzial = models.ForeignKey(Jednostka, CASCADE)
    rok = YearField(db_index=True)

    class Meta:
        unique_together = [
            ("autor", "wydzial", "rok"),
        ]
        app_label = "bpp"


class Opi_2012_Tytul_Cache_Manager(models.Manager):
    def rebuild(self):
        self.all().delete()
        for w in Wydawnictwo_Zwarte.objects.all():
            c = zrob_cache(w.tytul_oryginalny)
            self.create(wydawnictwo_zwarte=w, tytul_oryginalny_cache=c)


class Opi_2012_Tytul_Cache(models.Model):
    """Ta klasa to cache tytułów publikacji - wszystkie litery zmniejszone,
    wycięte znaki przestankowe typu kropka lub przecinek, wycięte spacje.
    """

    wydawnictwo_zwarte = models.ForeignKey(Wydawnictwo_Zwarte, CASCADE)
    tytul_oryginalny_cache = models.TextField(db_index=True)

    objects = Opi_2012_Tytul_Cache_Manager()

    class Meta:
        app_label = "bpp"
