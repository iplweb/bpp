# -*- encoding: utf-8 -*-

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse


def test_wybor(app, wydzial):
    page = app.get(reverse('eksport_pbn:zamow'))
    assert '2013' in page.text
