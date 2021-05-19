from django import template

register = template.Library()


from django.template.base import FilterExpression, kwarg_re


def parse_tag(token, parser):
    """
    Generic template tag parser.

    Returns a three-tuple: (tag_name, args, kwargs)

    tag_name is a string, the name of the tag.

    args is a list of FilterExpressions, from all the arguments that didn't look like kwargs,
    in the order they occurred, including any that were mingled amongst kwargs.

    kwargs is a dictionary mapping kwarg names to FilterExpressions, for all the arguments that
    looked like kwargs, including any that were mingled amongst args.

    (At rendering time, a FilterExpression f can be evaluated by calling f.resolve(context).)
    """
    # Split the tag content into words, respecting quoted strings.
    bits = token.split_contents()

    # Pull out the tag name.
    tag_name = bits.pop(0)

    # Parse the rest of the args, and build FilterExpressions from them so that
    # we can evaluate them later.
    args = []
    kwargs = {}
    for bit in bits:
        # Is this a kwarg or an arg?
        match = kwarg_re.match(bit)
        kwarg_format = match and match.group(1)
        if kwarg_format:
            key, value = match.groups()
            kwargs[key] = FilterExpression(value, parser)
        else:
            args.append(FilterExpression(bit, parser))

    return (tag_name, args, kwargs)


class CzyPokazywacNode(template.Node):
    def __init__(self, nodelist, attr):
        self.nodelist = nodelist

        self.attr = attr

    def render(self, context):
        uczelnia = context.get("uczelnia")
        if uczelnia is not None:
            if uczelnia.sprawdz_uprawnienie(self.attr.token, context.request):
                return self.nodelist.render(context)
        return ""


def czy_pokazywac(parser, token):
    tag_name, args, kwargs = parse_tag(token, parser)
    nodelist = parser.parse("end_czy_pokazywac")
    parser.delete_first_token()
    return CzyPokazywacNode(nodelist, args[0])


register.tag("czy_pokazywac", czy_pokazywac)
