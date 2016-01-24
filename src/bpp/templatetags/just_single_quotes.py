# -*- encoding: utf-8 -*-

from django import template


register = template.Library()


@register.filter
def just_single_quotes(value):
    if value:
        return value.replace("'", "&#39;")
    return value