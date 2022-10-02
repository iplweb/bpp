def qual(clazz):
    """
    Return full import path of a class.
    """
    return clazz.__module__ + "." + clazz.__name__


import sys


def str_to_class(path):
    split = path.split(".")
    module = ".".join(split[:-1])
    field = split[-1]

    try:
        identifier = getattr(sys.modules[module], field)
    except AttributeError:
        raise NameError("%s doesn't exist." % field)
    return identifier
