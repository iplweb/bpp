# -*- encoding: utf-8 -*-
from bpp.models.abstract import NazwaISkrot


class Tryb_OpenAccess_Wydawnictwo_Ciagle(NazwaISkrot):
    class Meta:
        verbose_name = "tryb OpenAccess wyd. ciągłych"
        verbose_name_plural = "tryby OpenAccess wyd. ciągłych"
        ordering = ['nazwa']
        app_label = 'bpp'


class Tryb_OpenAccess_Wydawnictwo_Zwarte(NazwaISkrot):
    class Meta:
        verbose_name = "tryb OpenAccess wyd. zwartych"
        verbose_name_plural = "tryby OpenAccess wyd. zwartych"
        ordering = ['nazwa']
        app_label = 'bpp'


class Czas_Udostepnienia_OpenAccess(NazwaISkrot):
    class Meta:
        verbose_name = 'czas udostępnienia OpenAccess'
        verbose_name_plural = 'czasy udostępnienia OpenAccess'
        ordering = ['nazwa']
        app_label = 'bpp'


class Licencja_OpenAccess(NazwaISkrot):
    class Meta:
        verbose_name = 'licencja OpenAccess'
        verbose_name_plural = 'licencja OpenAccess'
        ordering = ['nazwa']
        app_label = 'bpp'

    def webname(self):
        """
        Zwróc nazwę licencji, którą możemy podlinkować na WWW. Generalnie oznacza to
        zmniejszenie znaków i wyrzucenie początkowego CC- ze skrótu. Jeżeli skrót
        nie jest zamienialny na nazwę linku licencji Creative Commons, zwracaj None.
        """
        if self.skrot == "OTHER":
            return

        if self.skrot is not None:
            return self.skrot.lower().replace("cc-", "")


class Wersja_Tekstu_OpenAccess(NazwaISkrot):
    class Meta:
        verbose_name = 'wersja tekstu OpenAccess'
        verbose_name_plural = 'wersje tekstu OpenAccess'
        ordering = ['nazwa']
        app_label = 'bpp'
