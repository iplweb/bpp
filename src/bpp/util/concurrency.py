import multiprocessing
from math import ceil, floor

from django.db.models import Max, Min


def partition(min, max, num_proc, fun=ceil):
    s = int(fun((max - min) / num_proc))
    cnt = min
    ret = []
    while cnt < max:
        ret.append((cnt, cnt + s))
        cnt += s
    return ret


def partition_ids(model, num_proc, attr="idt"):
    d = model.objects.aggregate(min=Min(attr), max=Max(attr))
    return partition(d["min"], d["max"], num_proc)


def partition_count(objects, num_proc):
    return partition(0, objects.count(), num_proc, fun=ceil)


def no_threads(multiplier=0.75):
    return max(int(floor(multiprocessing.cpu_count() * multiplier)), 1)


def disable_multithreading_by_monkeypatching_pool(pool):
    def apply(fun, args=()):
        return fun(*args)

    pool.apply = apply

    def starmap(fun, lst):
        for elem in lst:
            fun(*elem)

    pool.starmap = starmap
