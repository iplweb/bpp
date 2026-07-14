import pytest
from django.db import connection, models

from django_pbn_client.models import (
    MAX_TEXT_FIELD_LENGTH,
    BasePBNMongoDBModel,
)
from django_pbn_client.persistence import upsert_pbn_object


class MirrorRecord(BasePBNMongoDBModel):
    title = models.TextField(blank=True, default="")
    year = models.IntegerField(blank=True, null=True)
    source = models.CharField(max_length=32, blank=True, default="")
    pull_up_on_save = ["title", "year"]

    class Meta:
        app_label = "django_pbn_client_package_tests"


@pytest.fixture(scope="module", autouse=True)
def mirror_record_table(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock(), connection.schema_editor() as editor:
        editor.create_model(MirrorRecord)

    yield

    with django_db_blocker.unblock(), connection.schema_editor() as editor:
        editor.delete_model(MirrorRecord)


def _element(
    *,
    status="ACTIVE",
    verification_level="VERIFIED",
    verified=True,
    title="A title",
    year=2026,
):
    return {
        "mongoId": "mongo-1",
        "status": status,
        "verificationLevel": verification_level,
        "verified": verified,
        "versions": [
            {
                "current": True,
                "object": {
                    "title": title,
                    "year": year,
                    "website": "https://pbn.example/object",
                },
            }
        ],
    }


@pytest.mark.django_db
def test_base_model_reads_current_version_and_pulls_up_text():
    record = upsert_pbn_object(_element(title="Downloaded title"), MirrorRecord)

    assert record.current_version["current"] is True
    assert record.value("object", "title") == "Downloaded title"
    assert record.value_or_none("object", "missing") is None
    assert record.website() == "https://pbn.example/object"
    assert record.title == "Downloaded title"
    assert record.year == 2026


@pytest.mark.django_db
def test_pull_up_truncates_pathological_indexed_text():
    title = "x" * (MAX_TEXT_FIELD_LENGTH + 50)

    record = upsert_pbn_object(_element(title=title), MirrorRecord)

    assert record.title == "x" * MAX_TEXT_FIELD_LENGTH


@pytest.mark.django_db
def test_upsert_updates_all_mirrored_state_and_extra_fields():
    upsert_pbn_object(_element(title="Before"), MirrorRecord, source="api")

    record = upsert_pbn_object(
        _element(
            status="DELETED",
            verification_level="REJECTED",
            verified=False,
            title="After",
        ),
        MirrorRecord,
        source="offline",
    )

    assert record.status == "DELETED"
    assert record.verificationLevel == "REJECTED"
    assert record.verified is False
    assert record.source == "offline"
    assert record.title == "After"


@pytest.mark.django_db
def test_unchanged_upsert_does_not_touch_last_updated_timestamp():
    payload = _element()
    original = upsert_pbn_object(payload, MirrorRecord)
    original_timestamp = original.last_updated_on

    unchanged = upsert_pbn_object(payload, MirrorRecord)

    assert unchanged.last_updated_on == original_timestamp
