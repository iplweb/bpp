"""Tests for source scoring synchronization."""

from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest
from model_bakery import baker

from bpp.models import Uczelnia
from pbn_import.models import ImportLog, ImportSession
from pbn_import.utils.source_scoring_import import (
    SourceScoringImporter,
    _import_disciplines_for_zrodlo,
    _import_points_for_zrodlo,
    _sync_single_source,
)


@pytest.fixture
def session(db, django_user_model):
    user = baker.make(django_user_model)
    return baker.make(ImportSession, user=user, config={})


class FakePbnUid:
    def __init__(self, values):
        self.values = values

    def value(self, *path, return_none=False):
        value = self.values
        for elem in path:
            value = value.get(elem)
            if value is None:
                return None if return_none else f"[brak {elem}]"
        return value


class FakePunktacjaManager:
    def __init__(self, existing=None):
        self.existing = existing
        self.created = []

    def get(self, rok):
        if self.existing and self.existing.rok == rok:
            return self.existing
        from bpp.models import Punktacja_Zrodla

        raise Punktacja_Zrodla.DoesNotExist

    def create(self, **kwargs):
        self.created.append(kwargs)
        return SimpleNamespace(**kwargs)


class FakeDyscyplinaManager:
    def __init__(self):
        self.deleted = False
        self.created = []

    def all(self):
        return self

    def delete(self):
        self.deleted = True

    def get_or_create(self, **kwargs):
        self.created.append(kwargs)
        return SimpleNamespace(**kwargs), True


class FakeZrodlo:
    def __init__(self, pbn_values, punktacja_manager=None):
        self.pbn_uid = FakePbnUid(pbn_values)
        self.punktacja_zrodla_set = punktacja_manager or FakePunktacjaManager()
        self.dyscyplina_zrodla_set = FakeDyscyplinaManager()


def test_import_points_creates_and_updates_points_from_min_year():
    existing = SimpleNamespace(
        rok="2020",
        punkty_kbn=40,
        save=MagicMock(),
    )
    punktacja = FakePunktacjaManager(existing=existing)
    zrodlo = FakeZrodlo(
        {
            "object": {
                "points": {
                    "2016": {"points": 10},
                    "2020": {"points": 70},
                    "2021": {"points": 100},
                    "2022": {},
                }
            }
        },
        punktacja_manager=punktacja,
    )

    last_year = _import_points_for_zrodlo(zrodlo, min_rok=2017)

    assert last_year == 2022
    assert existing.punkty_kbn == 70
    existing.save.assert_called_once_with()
    assert punktacja.created == [{"punkty_kbn": 100, "rok": "2021"}]


def test_import_disciplines_replaces_known_disciplines_only():
    zrodlo = FakeZrodlo(
        {
            "object": {
                "disciplines": [
                    {"code": "203"},
                    {"code": ""},
                    {"code": "999"},
                    "301",
                ]
            }
        }
    )

    _import_disciplines_for_zrodlo(
        zrodlo,
        ostatni_rok=2021,
        dyscypliny_dict={"2.3": 10, "3.1": 20},
    )

    assert zrodlo.dyscyplina_zrodla_set.deleted is True
    assert zrodlo.dyscyplina_zrodla_set.created == [
        {"dyscyplina_id": 10, "rok": 2021},
        {"dyscyplina_id": 20, "rok": 2021},
    ]


def test_import_disciplines_noops_without_year_or_payload():
    zrodlo = FakeZrodlo({"object": {"disciplines": [{"code": "203"}]}})

    _import_disciplines_for_zrodlo(zrodlo, ostatni_rok=None, dyscypliny_dict={})

    assert zrodlo.dyscyplina_zrodla_set.deleted is False

    zrodlo_no_disciplines = FakeZrodlo({"object": {"disciplines": []}})
    _import_disciplines_for_zrodlo(
        zrodlo_no_disciplines, ostatni_rok=2021, dyscypliny_dict={}
    )

    assert zrodlo_no_disciplines.dyscyplina_zrodla_set.deleted is False


@pytest.mark.django_db
def test_sync_single_source_reports_success_and_failure():
    zrodlo = FakeZrodlo({"object": {"points": {}}})

    with patch(
        "pbn_import.utils.source_scoring_import.Zrodlo.objects"
    ) as zrodlo_objects:
        zrodlo_objects.select_related.return_value.get.return_value = zrodlo
        with patch(
            "pbn_import.utils.source_scoring_import._import_points_for_zrodlo",
            return_value=2021,
        ) as import_points:
            with patch(
                "pbn_import.utils.source_scoring_import."
                "_import_disciplines_for_zrodlo"
            ) as import_disciplines:
                assert _sync_single_source(123, 2017, {"2.3": 10}) == (
                    123,
                    True,
                    None,
                )

    import_points.assert_called_once_with(zrodlo, 2017)
    import_disciplines.assert_called_once_with(zrodlo, 2021, {"2.3": 10})

    with patch(
        "pbn_import.utils.source_scoring_import.Zrodlo.objects"
    ) as zrodlo_objects:
        zrodlo_objects.select_related.return_value.get.side_effect = RuntimeError(
            "db failed"
        )

        assert _sync_single_source(456, 2017, {}) == (456, False, "db failed")


def test_run_returns_zero_when_no_sources(session):
    importer = SourceScoringImporter(session, client=None, max_workers=1)

    with patch(
        "pbn_import.utils.source_scoring_import.Dyscyplina_Naukowa.objects"
    ) as disciplines:
        with patch(
            "pbn_import.utils.source_scoring_import.Zrodlo.objects"
        ) as sources:
            disciplines.all.return_value = []
            sources.exclude.return_value.values_list.return_value = []

            result = importer.run()

    assert result == {"synchronized": 0, "failed": 0}
    assert ImportLog.objects.filter(
        session=session,
        level="info",
        message="Brak źródeł z pbn_uid do synchronizacji",
    ).exists()


def test_run_synchronizes_sources_and_logs_first_errors(session):
    importer = SourceScoringImporter(
        session,
        client=None,
        max_workers=1,
        uczelnia=baker.make(Uczelnia),
    )
    subtask = MagicMock()

    with patch(
        "pbn_import.utils.source_scoring_import.Dyscyplina_Naukowa.objects"
    ) as disciplines:
        with patch(
            "pbn_import.utils.source_scoring_import.Zrodlo.objects"
        ) as sources:
            with patch(
                "pbn_import.utils.source_scoring_import._sync_single_source",
                side_effect=[(1, True, None), (2, False, "bad source")],
            ) as sync_one:
                with patch(
                    "pbn_import.utils.source_scoring_import.tqdm",
                    side_effect=lambda iterable, **kwargs: iterable,
                ):
                    with patch.object(
                        importer, "create_subtask_progress", return_value=subtask
                    ):
                        disciplines.all.return_value = [
                            SimpleNamespace(kod="2.3", pk=10)
                        ]
                        sources.exclude.return_value.values_list.return_value = [1, 2]

                        result = importer.run()

    assert result == {"synchronized": 1, "failed": 1}
    assert sync_one.call_args_list == [
        call(1, 2017, {"2.3": 10}),
        call(2, 2017, {"2.3": 10}),
    ]
    assert subtask.update.call_count == 2
    assert ImportLog.objects.filter(
        session=session, level="warning", message__contains="bad source"
    ).exists()
    assert ImportLog.objects.filter(
        session=session,
        level="success",
        message="Zsynchronizowano 1 źródeł, 1 błędów",
    ).exists()
