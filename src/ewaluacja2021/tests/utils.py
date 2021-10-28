import os


def curdir(fn):
    return os.path.join(os.path.dirname(__name__), fn)
