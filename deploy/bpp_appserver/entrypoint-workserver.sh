#!/bin/sh

exec celery -A django_bpp.celery_tasks worker
