import itertools


def chunker(n, iterable):
    iterable = iter(iterable)
    while True:
        x = tuple(itertools.islice(iterable, n))
        if not x:
            return
        yield x
