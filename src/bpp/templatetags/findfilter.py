# -*- encoding: utf-8 -*-
from django.template import Library

register = Library()


def find(ciag, znaki):
    if ciag is None:
        return

    return ciag.find(znaki) >= 0


register.filter(find)