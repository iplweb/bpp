import os


def curdir(fn, name):
    return os.path.join(os.path.dirname(name), fn)
