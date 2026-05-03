"""Testy mechanizmu offloadingu zadań do Celery (`ustaw_dyscypline_task_or_instant`)."""

from celery.result import AsyncResult

from rozbieznosci_dyscyplin.admin import (
    DYSCYPLINA_AUTORA,
    OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE,
    SUBDYSCYPLINA_AUTORA,
    ustaw_dyscypline_task_or_instant,
)
from rozbieznosci_dyscyplin.models import RozbieznosciView

from .conftest import middleware


def test_RozbieznosciDyscyplinAdmin_test_task_offloading_offloads_dyscyplina(
    rf, zle_przypisana_praca, dyscyplina1
):
    req = rf.get("/")
    lst = [
        RozbieznosciView.objects.first().pk
    ] * OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE
    with middleware(req):
        ret = ustaw_dyscypline_task_or_instant(DYSCYPLINA_AUTORA, req, lst)
    assert isinstance(ret, AsyncResult)
    zle_przypisana_praca.refresh_from_db()
    assert zle_przypisana_praca.autorzy_set.first().dyscyplina_naukowa == dyscyplina1


def test_RozbieznosciDyscyplinAdmin_test_task_offloading_offloads_subdyscyplina(
    rf, zle_przypisana_praca, dyscyplina2
):
    req = rf.get("/")
    lst = [
        RozbieznosciView.objects.first().pk
    ] * OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE
    with middleware(req):
        ret = ustaw_dyscypline_task_or_instant(SUBDYSCYPLINA_AUTORA, req, lst)
    assert isinstance(ret, AsyncResult)
    zle_przypisana_praca.refresh_from_db()
    assert zle_przypisana_praca.autorzy_set.first().dyscyplina_naukowa == dyscyplina2


def test_RozbieznosciDyscyplinAdmin_test_task_offloading_instant_dyscyplina(
    rf, zle_przypisana_praca, dyscyplina1
):
    req = rf.get("/")
    lst = [RozbieznosciView.objects.first().pk] * (
        OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE - 1
    )
    with middleware(req):
        ret = ustaw_dyscypline_task_or_instant(DYSCYPLINA_AUTORA, req, lst)
    assert ret is None

    zle_przypisana_praca.refresh_from_db()
    assert zle_przypisana_praca.autorzy_set.first().dyscyplina_naukowa == dyscyplina1


def test_RozbieznosciDyscyplinAdmin_test_task_offloading_instant_subdyscyplina(
    rf, zle_przypisana_praca, dyscyplina2
):
    req = rf.get("/")
    lst = [RozbieznosciView.objects.first().pk] * (
        OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE - 1
    )
    with middleware(req):
        ret = ustaw_dyscypline_task_or_instant(SUBDYSCYPLINA_AUTORA, req, lst)
    assert ret is None

    zle_przypisana_praca.refresh_from_db()
    assert zle_przypisana_praca.autorzy_set.first().dyscyplina_naukowa == dyscyplina2
