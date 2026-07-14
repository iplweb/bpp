import pytest
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, connection

from django_pbn_client.persistence import (
    download_pbn_objects,
    get_total_count,
    upsert_pbn_object,
)


def _element():
    return {
        "mongoId": "race-winner",
        "status": "ACTIVE",
        "verificationLevel": "VERIFIED",
        "verified": True,
        "versions": [{"current": True, "object": {}}],
    }


def test_download_uses_paginator_total_and_host_progress_wrapper():
    saved = []
    progress_calls = []

    class Elements:
        total_elements = 2

        def __iter__(self):
            yield {"mongoId": "one"}
            yield {"mongoId": "two"}

    def save(element, model_class, client=None):
        saved.append((element["mongoId"], model_class, client))

    def progress(elements, total, label):
        progress_calls.append((total, label))
        return elements

    model_class = object()
    client = object()
    download_pbn_objects(
        Elements(),
        model_class,
        label="Downloading",
        save=save,
        client=client,
        progress=progress,
    )

    assert progress_calls == [(2, "Downloading")]
    assert saved == [
        ("one", model_class, client),
        ("two", model_class, client),
    ]


def test_total_count_supports_sized_and_counted_iterables():
    class Counted:
        count = 7

    assert get_total_count([1, 2, 3]) == 3
    assert get_total_count(Counted()) == 7
    assert get_total_count(iter([1, 2])) is None


@pytest.mark.django_db
def test_insert_race_fallback_keeps_outer_transaction_usable():
    class RaceDoesNotExist(ObjectDoesNotExist):
        pass

    class WinningInstance:
        status = "OLD"
        verificationLevel = "OLD"
        verified = False
        versions = []
        save_calls = 0

        def save(self):
            self.save_calls += 1

    winner = WinningInstance()

    class MissingQuery:
        def get(self):
            raise RaceDoesNotExist

    class RaceManager:
        def select_for_update(self):
            return self

        def filter(self, **kwargs):
            assert kwargs == {"pk": "race-winner"}
            return MissingQuery()

        def create(self, **kwargs):
            raise IntegrityError("another worker inserted the row")

        def get(self, **kwargs):
            assert kwargs == {"pk": "race-winner"}
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            return winner

    class RaceModel:
        objects = RaceManager()
        DoesNotExist = RaceDoesNotExist

    result = upsert_pbn_object(_element(), RaceModel)

    assert result is winner
    assert winner.status == "ACTIVE"
    assert winner.verificationLevel == "VERIFIED"
    assert winner.verified is True
    assert winner.versions == [{"current": True, "object": {}}]
    assert winner.save_calls == 1
