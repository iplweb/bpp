import itertools
from enum import Enum


def chunker(n, iterable):
    iterable = iter(iterable)
    while True:
        x = tuple(itertools.islice(iterable, n))
        if not x:
            return
        yield x


class SHUFFLE_TYPE(Enum):
    BEGIN = 1
    MIDDLE = 2
    END = 3
    RANDOM = 4


import random


def shuffle_array(
    array, start, length, no_shuffles=1, shuffle_type=SHUFFLE_TYPE.MIDDLE
):

    first = array[:start]
    second = array[start : start + length]
    third = array[start + length :]

    i = shuffle_type
    if shuffle_type == SHUFFLE_TYPE.RANDOM:
        i = random.randint(1, 3)

    if i == SHUFFLE_TYPE.BEGIN:
        for a in range(no_shuffles):
            random.shuffle(first)
    elif i == SHUFFLE_TYPE.MIDDLE:
        for a in range(no_shuffles):
            random.shuffle(second)
    elif i == SHUFFLE_TYPE.END:
        for a in range(no_shuffles):
            random.shuffle(third)

    return first + second + third
