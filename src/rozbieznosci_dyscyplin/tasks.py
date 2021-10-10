from celery import shared_task

from rozbieznosci_dyscyplin.admin import real_ustaw_dyscypline


@shared_task
def task_ustaw_dyscypline(pole, elements):
    from rozbieznosci_dyscyplin.admin import ResultNotifier

    notifier = ResultNotifier()
    real_ustaw_dyscypline(pole, elements, notifier)
    return notifier.retbuf
