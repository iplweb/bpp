from unittest.mock import MagicMock, Mock

import pytest

from integrator2.models import ListaMinisterialnaIntegration


@pytest.mark.django_db
def test_models_base(normal_django_user):

    bi = ListaMinisterialnaIntegration()  # BaseIntegration()

    bi.file.name = "foo"
    assert bi.filename() == "foo"

    filter = Mock()
    bi.klass = Mock(objects=Mock(filter=filter))
    bi.records()
    assert filter.called

    bi.integrated()
    bi.not_integrated()
    assert filter.call_count == 3

    bi.match_single_record = Mock()
    elem = Mock()
    bi.records = Mock(return_value=[elem])
    bi.match_records()
    assert elem.zanalizowano
    assert elem.save.call_count == 1
    assert bi.match_single_record.called

    elem = Mock()
    bi.records = MagicMock()
    bi.records().filter.return_value = [elem]
    [x for x in bi.records().filter()]

    bi.integrate_single_record = Mock()
    bi.integrate()
    assert bi.integrate_single_record.call_count == 1
    assert elem.zintegrowano
    assert elem.save.called
