import pytest
from dbtemplates.models import Template
from django.db import IntegrityError

from django.contrib.contenttypes.models import ContentType

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

    if not SzablonDlaOpisuBibliograficznego.objects.filter(model=None).exists():
        # przy ponownym uruchamianiu testow moze byc taka sytuacja
        SzablonDlaOpisuBibliograficznego.objects.create(template=test_template)

    with pytest.raises(IntegrityError):
        SzablonDlaOpisuBibliograficznego.objects.create(template=test_template)


@pytest.mark.django_db
def test_rozne_opisy_rozne_klasy(wydawnictwo_ciagle, wydawnictwo_zwarte):
    SzablonDlaOpisuBibliograficznego.objects.all().delete()

    test_template = Template.objects.create(name="test", content="test")
    second_template = Template.objects.create(name="2nd", content="2nd")

    # Szablon dla każdej klasy
    try:
        sz = SzablonDlaOpisuBibliograficznego.objects.get(model=None)
        sz.template = test_template
        sz.save()
    except SzablonDlaOpisuBibliograficznego.DoesNotExist:
        SzablonDlaOpisuBibliograficznego.objects.create(template=test_template)

    assert wydawnictwo_ciagle.opis_bibliograficzny() == test_template.content
    assert wydawnictwo_zwarte.opis_bibliograficzny() == test_template.content

    # Szablon tylko dla zwartych
    SzablonDlaOpisuBibliograficznego.objects.create(
        model=ContentType.objects.get_for_model(Wydawnictwo_Zwarte),
        template=second_template,
    )

    assert wydawnictwo_ciagle.opis_bibliograficzny() == test_template.content
    assert wydawnictwo_zwarte.opis_bibliograficzny() == second_template.content
