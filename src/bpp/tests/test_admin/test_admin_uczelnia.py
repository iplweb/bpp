import pytest
from django.urls import reverse
from model_mommy import mommy

from bpp.models import Jednostka


@pytest.mark.django_db(transaction=True)
def test_uczelnia_reorder(uczelnia, admin_app):
    try:
        uczelnia.sortuj_jednostki_alfabetycznie = False
        uczelnia.save()

        mommy.make(Jednostka, uczelnia=uczelnia)
        mommy.make(Jednostka, uczelnia=uczelnia)
        mommy.make(Jednostka, uczelnia=uczelnia)

        assert (
            Jednostka.objects.all()
            .values_list("kolejnosc", flat=True)
            .distinct()
            .count()
            == 1
        )

        res = admin_app.get(reverse("admin:bpp_uczelnia_change", args=(uczelnia.pk,)))
        uf = res.forms["uczelnia_form"]
        uf["sortuj_jednostki_alfabetycznie"].value = True
        uf.submit().maybe_follow()

        assert (
            Jednostka.objects.all()
            .values_list("kolejnosc", flat=True)
            .distinct()
            .count()
            == 3
        )

    finally:
        Jednostka.objects.all().delete()
        uczelnia.delete()
