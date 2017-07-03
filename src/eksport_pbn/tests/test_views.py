# -*- encoding: utf-8 -*-

from django.core.urlresolvers import reverse


def test_wybor(app, wydzial):
    page = app.get(reverse('eksport_pbn:zamow'))
    assert '2013' in page.text
