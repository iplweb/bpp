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


@pytest.mark.django_db
def test_batch_task_eksportuje_patenty():
    from dspace_api.tasks import queue_dspace_export_batch

    p1, p2 = baker.make("bpp.Patent", _quantity=2)

    with mock.patch("dspace_api.tasks.eksportuj_rekord", return_value=[]) as m:
        queue_dspace_export_batch(
            app_label="bpp", model_name="patent", record_ids=[p1.id, p2.id]
        )
    assert {c.args[0] for c in m.call_args_list} == {p1, p2}
