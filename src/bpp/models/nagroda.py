# -*- encoding: utf-8 -*-
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import CASCADE
from lxml.etree import SubElement, Element

from bpp.models.abstract import NazwaISkrot


class OrganPrzyznajacyNagrody(NazwaISkrot):
    class Meta:
        verbose_name_plural = 'Organy przyznające nagrody'
        verbose_name = 'Organ przyznający nagrodę'


class Nagroda(models.Model):
    content_type = models.ForeignKey(ContentType, CASCADE)
    object_id = models.PositiveIntegerField()
    object = GenericForeignKey()

    nazwa = models.CharField(max_length=200)
    organ_przyznajacy = models.ForeignKey(OrganPrzyznajacyNagrody, CASCADE)
    rok_przyznania = models.PositiveIntegerField()
    uzasadnienie = models.CharField(max_length=512, default='', blank=True)
    adnotacja = models.CharField(max_length=100, default='', blank=True)

    def eksport_pbn_serializuj(self):
        award = Element("award")

        awardGrantingEntity = SubElement(award, "awardGrantingEntity")
        awardGrantingEntity.text = str(self.organ_przyznajacy.skrot)

        awardName = SubElement(award, "awardName")
        awardName.text = self.nazwa

        grantYear = SubElement(award, "grantYear")
        grantYear.text = str(self.rok_przyznania)

        awardReason = SubElement(award, "awardReason")
        awardReason.text = self.uzasadnienie

        return award

    class Meta:
        verbose_name_plural = 'nagrody'
        verbose_name = 'nagroda'
        unique_together = (
            'content_type',
            'object_id',
            'organ_przyznajacy',
            'rok_przyznania')
