from datetime import timedelta

from crossref.restful import Works
from django.db import models
from django.db.models import JSONField

from django.utils import timezone

from bpp.fields import DOIField


class CrossrefAPICacheManager(models.Manager):

    CACHE_DURATION_DAYS = 14
    cache_last_run = None

    def cleanup(self):
        cache_duration = timezone.now() - timedelta(days=self.CACHE_DURATION_DAYS)
        if self.cache_last_run is not None:
            if self.cache_last_run > cache_duration:
                return

        self.filter(ostatnio_zmodyfikowany__lte=cache_duration).delete()
        self.cache_last_run = timezone.now()

    def api_get_by_doi(self, doi):
        works = Works()
        return works.doi(doi)

    def get_by_doi(self, doi):
        self.cleanup()

        ret = self.filter(doi=doi).first()
        if ret is None:
            data = self.api_get_by_doi(doi)
            if data is None:
                return

            ret = self.create(doi=doi, data=data)

        return ret.data


class CrossrefAPICache(models.Model):
    objects = CrossrefAPICacheManager()

    doi = DOIField(unique=True)
    data = JSONField()
    ostatnio_zmodyfikowany = models.DateTimeField(auto_now=True)
