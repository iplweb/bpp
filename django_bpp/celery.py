# -*- encoding: utf-8 -*-

from __future__ import absolute_import

import os, sys
from celery import Celery

from django.conf import settings

# set the default Django settings module for the 'celery' program.
s = 'production'
if sys.platform == 'win32':
    s = 'devel'

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_bpp.settings.%s' % s)

app = Celery('bpp')

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object('django.conf:settings')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))

