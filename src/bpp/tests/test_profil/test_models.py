"""Testy pól profilu na modelu Autor oraz modelu WybranaPublikacjaAutora."""

import pytest
from django.contrib.contenttypes.models import ContentType
from model_bakery import baker

from bpp.models import Autor


@pytest.mark.django_db
def test_autor_ma_domyslnie_pusty_uklad():
    autor = baker.make(Autor)
    assert autor.uklad_profilu is None


@pytest.mark.django_db
def test_autor_biogram_html_renderuje_markdown():
    autor = baker.make(Autor, biogram="**x**", biogram_format="md")
    assert "<strong>x</strong>" in autor.biogram_html


@pytest.mark.django_db
def test_autor_biogram_html_pusty_daje_pusty_string():
    autor = baker.make(Autor, biogram="", biogram_format="md")
    assert autor.biogram_html == ""


@pytest.mark.django_db
def test_wybrana_publikacja_resolves_gfk(wydawnictwo_zwarte):
    from bpp.models import WybranaPublikacjaAutora

    autor = baker.make(Autor)
    wp = WybranaPublikacjaAutora.objects.create(
        autor=autor,
        content_type=ContentType.objects.get_for_model(wydawnictwo_zwarte),
        object_id=wydawnictwo_zwarte.pk,
        kolejnosc=1,
    )
    assert wp.publikacja == wydawnictwo_zwarte
    assert list(autor.wybrane_publikacje.all()) == [wp]
