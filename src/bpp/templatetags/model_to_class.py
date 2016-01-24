# -*- encoding: utf-8 -*-

from django import template


register = template.Library()

@register.filter
def model_to_class_name(value):
    return value.__class__.__name__