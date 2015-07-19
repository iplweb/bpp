# -*- encoding: utf-8 -*-

import time

from django import template

from django_bpp.version import VERSION

register = template.Library()


@register.simple_tag
def bpp_version():
    return VERSION

@register.simple_tag
def bpp_localtime():
    return time.ctime()