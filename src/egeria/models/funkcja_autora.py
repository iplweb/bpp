# -*- encoding: utf-8 -*-

from django.db import models

from bpp.models.autor import Funkcja_Autora
from egeria.models.abstract import Diff_Delete, Diff_Create


class Diff_Funkcja_Autora_Create(Diff_Create):
    klass = Funkcja_Autora


class Diff_Funkcja_Autora_Delete(Diff_Delete):
    reference = models.ForeignKey(Funkcja_Autora)

    @classmethod
    def check_if_needed(cls, reference):
        return reference.autor_jednostka_set.count() == 0
