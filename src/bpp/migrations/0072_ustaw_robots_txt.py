# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.contrib.sites.models import Site
from django.db import migrations
from robots.models import Url, Rule

DISALLOW_URLS = [
    "/multiseek/",
    "/bpp/raporty/",
    "/eksport_pbn/",
    "/admin/",
    "/integrator2/",
    "/password_change/",
]


def ustaw_robots_txt(apps, schema_editor):
    for elem in DISALLOW_URLS:
        Url.objects.create(pattern=elem)

    if Site.objects.all().count() != 1:
        raise Exception("Not supported")

    r = Rule.objects.create(robot="*")
    r.sites.add(Site.objects.all()[0])
    for elem in DISALLOW_URLS:
        r.disallowed.add(Url.objects.get(pattern=elem))
    r.save()


def usun_robots_txt(apps, schema_editor):
    for elem in DISALLOW_URLS:
        try:
            u = Url.objects.get(pattern=elem)
            u.delete()
        except Url.DoesNotExist:
            pass

    if Site.objects.all().count() != 1:
        raise Exception("Not supported")

    Rule.objects.get(robot="*").delete()


class Migration(migrations.Migration):
    dependencies = [
        ('bpp', '0071_fix_liczba_znakow_wyd'),
        ('robots', '0001_initial')
    ]

    operations = [
        migrations.RunPython(ustaw_robots_txt, usun_robots_txt)
    ]
