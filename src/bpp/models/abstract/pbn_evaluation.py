"""Modele abstrakcyjne związane z polami ewaluacji PBN."""

from django.db import models


class ModelZPolamiEwaluacjiPBN(models.Model):
    """Mixin zawierający pola ewaluacji dla eksportu PBN/SEDN."""

    pbn_czy_projekt_fnp = models.BooleanField(
        "PBN: Projekt FNP",
        null=True,
        blank=True,
        default=None,
        help_text="evaluationBookProjectFNP - czy publikacja powstała w ramach "
        "projektu Fundacji na rzecz Nauki Polskiej",
    )

    pbn_czy_projekt_ncn = models.BooleanField(
        "PBN: Projekt NCN",
        null=True,
        blank=True,
        default=None,
        help_text="evaluationBookProjectNCN - czy publikacja powstała w ramach "
        "projektu Narodowego Centrum Nauki",
    )

    pbn_czy_projekt_nprh = models.BooleanField(
        "PBN: Projekt NPRH",
        null=True,
        blank=True,
        default=None,
        help_text="evaluationBookProjectNPHR - czy publikacja powstała w ramach "
        "projektu Narodowego Programu Rozwoju Humanistyki",
    )

    pbn_czy_projekt_ue = models.BooleanField(
        "PBN: Projekt UE",
        null=True,
        blank=True,
        default=None,
        help_text="evaluationBookProjectUE - czy publikacja powstała w ramach "
        "projektu finansowanego przez Unię Europejską",
    )

    pbn_czy_czasopismo_indeksowane = models.BooleanField(
        "PBN: Czasopismo indeksowane",
        null=True,
        blank=True,
        default=None,
        help_text="evaluationIndexedJournal - czy czasopismo jest indeksowane",
    )

    pbn_czy_artykul_recenzyjny = models.BooleanField(
        "PBN: Artykuł recenzyjny",
        null=True,
        blank=True,
        default=None,
        help_text="evaluationIsReview - czy jest recenzją/artykułem recenzyjnym "
        "(NIEZALEŻNE od pola 'recenzowana')",
    )

    pbn_czy_edycja_naukowa = models.BooleanField(
        "PBN: Edycja naukowa",
        null=True,
        blank=True,
        default=None,
        help_text="evaluationScientificEdition - czy jest edycją naukową",
    )

    class Meta:
        abstract = True
