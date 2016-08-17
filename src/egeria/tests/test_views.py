# -*- encoding: utf-8 -*-
from django.core.urlresolvers import reverse

from webtest import Upload

def test_egeria_views_main(first_page_after_upload):
    assert "nowe tytuły" in first_page_after_upload.content

