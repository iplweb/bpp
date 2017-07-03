# -*- encoding: utf-8 -*-
import pytest
from mock import Mock, MagicMock

from integrator2.models.base import BaseIntegration

@pytest.mark.django_db
def test_models_base(normal_django_user):

    bi = BaseIntegration()

    bi.file.name = 'foo'
    assert bi.filename() == 'foo'

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
    assert elem.zanalizowano == True
    assert elem.save.call_count == 1
    assert bi.match_single_record.called == True

    elem = Mock()
    bi.records = MagicMock()
    bi.records().filter.return_value = [elem]
    res = [x for x in bi.records().filter()]

    bi.integrate_single_record = Mock()
    bi.integrate()
    assert bi.integrate_single_record.call_count == 1
    assert elem.zintegrowano == True
    assert elem.save.called == True