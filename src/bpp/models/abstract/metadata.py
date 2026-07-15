"""
Modele abstrakcyjne związane z metadanymi rekordów.
"""

from django.db import models
from django.db.models import CASCADE, SET_NULL

from bpp.util import safe_html


class ModelZAdnotacjami(models.Model):
    """Zawiera adnotację  dla danego obiektu, czyli informacje, które
    użytkownik może sobie dowolnie uzupełnić.
    """

    ostatnio_zmieniony = models.DateTimeField(auto_now=True, null=True, db_index=True)

    adnotacje = models.TextField(
        help_text="""Pole do użytku wewnętrznego -
        wpisane tu informacje nie są wyświetlane na stronach WWW dostępnych
        dla użytkowników końcowych.""",
        default="",
        blank=True,
        null=False,
        db_index=True,
    )

    class Meta:
        abstract = True


class ModelZInformacjaZ(models.Model):
    """Model zawierający pole 'Informacja z' - czyli od kogo została
    dostarczona informacja o publikacji (np. od autora, od redakcji)."""

    informacja_z = models.ForeignKey(
        "Zrodlo_Informacji", SET_NULL, null=True, blank=True
    )

    class Meta:
        abstract = True


class ModelZeStatusem(models.Model):
    """Model zawierający pole statusu korekty, oraz informację, czy
    punktacja została zweryfikowana."""

    status_korekty = models.ForeignKey("Status_Korekty", CASCADE)

    class Meta:
        abstract = True


class ModelZCharakterem(models.Model):
    charakter_formalny = models.ForeignKey(
        "bpp.Charakter_Formalny",
        CASCADE,
        verbose_name="Charakter formalny",
        limit_choices_to={"ukryty": False},
    )

    class Meta:
        abstract = True


class ModelZeSzczegolami(models.Model):
    """Model zawierający pola: informacje, szczegóły, uwagi, słowa kluczowe."""

    informacje = models.TextField("Informacje", blank=True, default="", db_index=True)

    szczegoly = models.CharField(
        "Szczegóły", max_length=512, blank=True, default="", help_text="Np. str. 23-45"
    )

    uwagi = models.TextField(blank=True, default="", db_index=True)

    utworzono = models.DateTimeField(
        "Utworzono", auto_now_add=True, blank=True, null=True
    )

    strony = models.CharField(
        max_length=250,
        blank=True,
        default="",
        help_text="""Jeżeli uzupełnione, to pole będzie eksportowane do
        danych PBN. Jeżeli puste, informacja ta będzie ekstrahowana z
        pola "Szczegóły" w chwili generowania eksportu PBN. Aby uniknąć
        sytuacji, gdy wskutek błędnego wprowadzenia tekstu do pola
        "Szczegóły" informacja ta nie będzie mogła być wyekstrahowana
        z tego pola, kliknij przycisk "Uzupełnij", aby spowodować uzupełnienie
        tego pola na podstawie pola "Szczegóły".
        """,
    )

    tom = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="""Jeżeli uzupełnione, to pole będzie eksportowane do
        danych PBN. Jeżeli puste, informacja ta będzie ekstrahowana z
        pola 'Informacje'. Kliknięcie przycisku "Uzupełnij" powoduje
        również automatyczne wypełnienie tego pola, o ile do formularza
        zostały wprowadzone odpowiednie informacje. """,
    )

    class Meta:
        abstract = True

    def clean(self):
        # Pola renderowane w opisie bibliograficznym przez |safe (także przez
        # zdenormalizowany opis_bibliograficzny_cache na publicznych stronach
        # i w globalnej wyszukiwarce). Sanityzujemy na wejściu tak jak tytuły
        # (DwaTytuly.clean), inaczej redaktor wstrzykuje stored XSS.
        self.informacje = safe_html(self.informacje)
        self.szczegoly = safe_html(self.szczegoly)
        self.uwagi = safe_html(self.uwagi)

    def pierwsza_strona(self):
        return self.strony.split("-")[0]

    def ostatnia_strona(self):
        try:
            return self.strony.split("-")[1]
        except IndexError:
            return self.pierwsza_strona()


class ModelZNumeremZeszytu(models.Model):
    nr_zeszytu = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="""Jeżeli uzupełnione, to pole będzie eksportowane do
        danych PBN. Jeżeli puste, informacja ta będzie ekstrahowana z
        pola 'Informacje'. Kliknięcie przycisku "Uzupełnij" powoduje
        również automatyczne wypełnienie tego pola, o ile do formularza
        zostały wprowadzone odpowiednie informacje. """,
    )

    class Meta:
        abstract = True
