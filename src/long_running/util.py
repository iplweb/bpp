import time
import warnings


def wait_for_object(klass, pk, no_tries=10):
    warnings.warn(
        "Ta funkcja niepotrzebnie 'przetrzymuje' workera przez 10 sekund. "
        "Rozsadne byloby jej nie uzywac i przepisac kod na konstrukcje zblizona do"
        "long_running.tasks.perform_generic_long_running_task -- czyli funkcje, ktora"
        "probuje uruchomic sie za 10 sekund za pomoca mechanizmow celery, nie zas "
        "blokujaca worker za pomoca time.sleep ... ",
        category=DeprecationWarning,
    )

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
