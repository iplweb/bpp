from uuid import uuid4

from django import template
from django.template import Node, TemplateSyntaxError
from django.template.defaultfilters import stringfilter

register = template.Library()


@register.filter(name="message_level_to_css_class")
@stringfilter
def message_level_to_css_class(value):
    from django.contrib.messages import constants

    return constants.DEFAULT_TAGS.get(int(value))
