import pytest
from dbtemplates.models import Template
from django.db import IntegrityError

from bpp.models import Wydawnictwo_Zwarte
from bpp.models.szablondlaopisubibliograficznego import SzablonDlaOpisuBibliograficznego


@pytest.mark.django_db
def test_Template_name_idx():
    Template.objects.create(name="test", content="test")
    with pytest.raises(IntegrityError):
        Template.objects.create(name="test", content="test")


@pytest.mark.django_db
def test_nulltest_idx():
    test_template = Template.objects.create(name="test", content="test")

    SzablonDlaOpisuBibliograficznego.objects.create(template=test_template)
    with pytest.raises(IntegrityError):
        SzablonDlaOpisuBibliograficznego.objects.create(template=test_template)


def test_rozne_opisy_rozne_klasy(wydawnictwo_ciagle, wydawnictwo_zwarte):
    test_template = Template.objects.create(name="test", content="test")
    second_template = Template.objects.create(name="2nd", content="2nd")

    # Szablon dla każdej klasy
    SzablonDlaOpisuBibliograficznego.objects.create(model=None, template=test_template)

    assert wydawnictwo_ciagle.opis_bibliograficzny() == test_template.content
    assert wydawnictwo_zwarte.opis_bibliograficzny() == test_template.content

    # Szablon tylko dla zwartych
    SzablonDlaOpisuBibliograficznego.objects.create(
        model=Wydawnictwo_Zwarte, template=second_template
    )

    assert wydawnictwo_ciagle.opis_bibliograficzny() == test_template.content
    assert wydawnictwo_zwarte.opis_bibliograficzny() == second_template.content
