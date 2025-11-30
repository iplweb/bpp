"""
Modele abstrakcyjne związane z identyfikatorami zewnętrznymi.
"""

from django.db import models

from bpp import const
from bpp.fields import DOIField


class ModelZPBN_ID(models.Model):
    """Zawiera informacje o PBN_ID"""

    pbn_id = models.IntegerField(
        verbose_name="[Przestarzałe] Identyfikator PBN",
        help_text="[Pole o znaczeniu historycznym] Identyfikator w systemie Polskiej Bibliografii Naukowej (PBN)",
        null=True,
        blank=True,
        unique=True,
        db_index=True,
    )

    class Meta:
        abstract = True


class ModelZISSN(models.Model):
    """Model z numerem ISSN oraz E-ISSN"""

    issn = models.CharField("ISSN", max_length=32, blank=True, default="")
    e_issn = models.CharField("e-ISSN", max_length=32, blank=True, default="")

    class Meta:
        abstract = True


class ModelZISBN(models.Model):
    """Model z numerem ISBN oraz E-ISBN"""

    isbn = models.CharField(
        "ISBN", max_length=64, blank=True, default="", db_index=True
    )
    e_isbn = models.CharField(
        "E-ISBN", max_length=64, blank=True, default="", db_index=True
    )

    class Meta:
        abstract = True


class ModelZDOI(models.Model):
    doi = DOIField(const.DOI_FIELD_LABEL, null=True, blank=True, db_index=True)

    class Meta:
        abstract = True


class ModelZPubmedID(models.Model):
    pubmed_id = models.BigIntegerField(
        "PubMed ID", blank=True, null=True, help_text="Identyfikator PubMed (PMID)"
    )
    pmc_id = models.CharField(
        "PubMed Central ID", max_length=32, blank=True, default=""
    )

    class Meta:
        abstract = True
