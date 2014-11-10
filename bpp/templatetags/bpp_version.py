# -*- encoding: utf-8 -*-

import time

from django import template

from django_bpp.version import version


register = template.Library()


@register.simple_tag
def bpp_version():
    return version

@register.simple_tag
def bpp_localtime():
    return time.ctime()