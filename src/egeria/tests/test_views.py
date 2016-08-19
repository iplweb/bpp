# -*- encoding: utf-8 -*-

import pytest

from bpp.models.autor import Tytul


def test_egeria_views_main(first_page_after_upload):
    assert "nowe tytuły" in first_page_after_upload.content
    res = first_page_after_upload.click("import osób")
    assert "Pliki importu osób" in res.content


@pytest.mark.django_db
def test_egeria_views_difflistview_submit(first_page_after_upload):
    Tytul.objects.create(nazwa="do usunięcia", skrot="do u")
    res = first_page_after_upload.clickbutton("Zatwierdź")
    assert "tytuły do usunięcia" in res.content


@pytest.mark.django_db
def test_egeria_views_difflistview_cancel(first_page_after_upload):
    raise NotImplementedError
