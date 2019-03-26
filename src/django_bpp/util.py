import time


def wait_for_object(klass, pk, no_tries=3):
    obj = None

    while no_tries > 0:
        try:
            obj = klass.objects.get(pk=pk)
            break
        except klass.DoesNotExist:
            time.sleep(1)
            no_tries = no_tries - 1

    if obj is None:
        raise klass.DoesNotExist("Cannot fetch klass %r with pk %r" % (klass, pk))

    return obj

