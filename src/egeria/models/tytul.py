# -*- encoding: utf-8 -*-

from django.db import models

from bpp.models.autor import Tytul
from egeria.models.abstract import Diff_Delete, Diff_Create


class Diff_Tytul_Create(Diff_Create):
    klass = Tytul


class Diff_Tytul_Delete(Diff_Delete):
    reference = models.ForeignKey(Tytul)

    @classmethod
    def check_if_needed(cls, reference):
        return reference.autor_set.count() == 0
