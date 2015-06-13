# -*- encoding: utf-8 -*-

from __future__ import absolute_import

import os

from celery import Celery
from django.conf import settings

# os.environ['DJANGO_SETTINGS_MODULE'] = 'natasz'
app = Celery('django_bpp')

app.config_from_object('django.conf:settings')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
