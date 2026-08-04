from django.db import models

from bpp.models.abstract import NazwaISkrot

COAR_ACCESS_RIGHT_HELP_TEXT = (
    "Pełny identyfikator prawa dostępu ze słownika COAR Access Rights, np. "
    "http://purl.org/coar/access_right/c_abf2 dla „open access”. Używany w "
    "eksporcie CERIF/OpenAIRE; gdy pusty, prace o tym trybie zostaną "
    "wyeksportowane bez określonego prawa dostępu."
)


class Tryb_OpenAccess_Wydawnictwo_Ciagle(NazwaISkrot):
    coar_access_right = models.CharField(
        "Prawo dostępu wg COAR",
        max_length=200,
        blank=True,
        default="",
        help_text=COAR_ACCESS_RIGHT_HELP_TEXT,
    )

    class Meta:
        verbose_name = "tryb OpenAccess wyd. ciągłych"
        verbose_name_plural = "tryby OpenAccess wyd. ciągłych"
        ordering = ["nazwa"]
        app_label = "bpp"


class Tryb_OpenAccess_Wydawnictwo_Zwarte(NazwaISkrot):
    coar_access_right = models.CharField(
        "Prawo dostępu wg COAR",
        max_length=200,
        blank=True,
        default="",
        help_text=COAR_ACCESS_RIGHT_HELP_TEXT,
    )

    class Meta:
        verbose_name = "tryb OpenAccess wyd. zwartych"
        verbose_name_plural = "tryby OpenAccess wyd. zwartych"
        ordering = ["nazwa"]
        app_label = "bpp"


class Czas_Udostepnienia_OpenAccess(NazwaISkrot):
    class Meta:
        verbose_name = "czas udostępnienia OpenAccess"
        verbose_name_plural = "czasy udostępnienia OpenAccess"
        ordering = ["nazwa"]
        app_label = "bpp"


class Licencja_OpenAccess(NazwaISkrot):
    uri = models.URLField(
        "Adres URI licencji",
        max_length=512,
        blank=True,
        default="",
        help_text="Kanoniczny adres URI licencji, np. "
        "https://creativecommons.org/licenses/by/4.0/ . Używany w eksporcie "
        "CERIF/OpenAIRE; gdy pusty, prace na tej licencji zostaną "
        "wyeksportowane bez odnośnika do jej treści.",
    )

    class Meta:
        verbose_name = "licencja OpenAccess"
        verbose_name_plural = "licencja OpenAccess"
        ordering = ["nazwa"]
        app_label = "bpp"

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
        verbose_name = "wersja tekstu OpenAccess"
        verbose_name_plural = "wersje tekstu OpenAccess"
        ordering = ["nazwa"]
        app_label = "bpp"
