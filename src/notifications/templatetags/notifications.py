from uuid import uuid4

from django import template
from django.template import Node, TemplateSyntaxError
from django.template.defaultfilters import stringfilter

register = template.Library()


@register.filter(name='message_level_to_css_class')
@stringfilter
def message_level_to_css_class(value):
    from django.contrib.messages import constants

    return constants.DEFAULT_TAGS.get(int(value))

#
# https://djangosnippets.org/snippets/1356/
#

class UUIDNode(Node):
    """
    Implements the logic of this tag.
    """

    def __init__(self, var_name):
        self.var_name = var_name

    def render(self, context):
        context[self.var_name] = str(uuid4())
        return ''


def do_uuid(parser, token):
    """
    The purpose of this template tag is to generate a random
    UUID and store it in a named context variable.

    Sample usage:
        {% uuid var_name %}
        var_name will contain the generated UUID
    """
    try:
        tag_name, var_name = token.split_contents()
    except ValueError:
        raise TemplateSyntaxError("%r tag requires exactly one argument" % token.contents.split()[0])
    return UUIDNode(var_name)


do_uuid = register.tag('uuid', do_uuid)
