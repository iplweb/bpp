from unittest import mock

import pytest
from model_bakery import baker


@pytest.mark.django_db
def test_batch_task_eksportuje_kazdy_rekord():
    from dspace_api.tasks import queue_dspace_export_batch

    r1 = baker.make("bpp.Wydawnictwo_Ciagle")
    r2 = baker.make("bpp.Wydawnictwo_Ciagle")

    with mock.patch("dspace_api.tasks.eksportuj_rekord", return_value=[]) as m:
        queue_dspace_export_batch(
            app_label="bpp",
            model_name="wydawnictwo_ciagle",
            record_ids=[r1.id, r2.id],
            user_id=None,
        )
    assert m.call_count == 2
