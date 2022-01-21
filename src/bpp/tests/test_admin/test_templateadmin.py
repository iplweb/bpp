import pytest
from dbtemplates.models import Template
from django.urls import reverse

from django.contrib.contenttypes.models import ContentType

from bpp.models import Wydawnictwo_Ciagle
from bpp.models.szablondlaopisubibliograficznego import SzablonDlaOpisuBibliograficznego


@pytest.mark.django_db
def test_BppTemplateAdmin_templatka_zmienia_rekordy(
    admin_app, wydawnictwo_zwarte, denorms, wydawnictwo_ciagle
):
    WERSJA_1 = "werjsa 1"
    WERSJA_2 = "wersja 2"

    t, _ign = Template.objects.update_or_create(
        name="opis_bibliograficzny.html",
        defaults={"content": WERSJA_1},
    )
    SzablonDlaOpisuBibliograficznego.objects.create(
        model=ContentType.objects.get_for_model(Wydawnictwo_Ciagle),
        template=t,
    )
    denorms.rebuild_instances_of(Wydawnictwo_Ciagle)
    denorms.flush()

    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.opis_bibliograficzny_cache == WERSJA_1
    #
    # Koniec inicjalizacji -- właściwy test poniżej
    #

    url = reverse("admin:dbtemplates_template_change", args=(t.pk,))
    res = admin_app.get(url)
    res.forms["template_form"]["content"] = WERSJA_2
    res.forms["template_form"]["name"] = "nazwa.html"
    res = res.forms["template_form"].submit().maybe_follow()

    denorms.flush()

    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.opis_bibliograficzny_cache == WERSJA_2


@pytest.mark.django_db
def test_BppTemplateAdmin_zmiana_szablonu_zmienia_rekordy(
    admin_app, denorms, wydawnictwo_ciagle
):
    WERSJA_1 = "werjsa 1"
    WERSJA_2 = "wersja 2"

    t1, _ign = Template.objects.update_or_create(
        name="opis_bibliograficzny.html",
        defaults={"content": WERSJA_1},
    )
    t2, _ign = Template.objects.update_or_create(
        name="opis_bibliograficzny_2.html", defaults={"content": WERSJA_2}
    )

    szablon = SzablonDlaOpisuBibliograficznego.objects.create(
        model=ContentType.objects.get_for_model(Wydawnictwo_Ciagle),
        template=t1,
    )
    denorms.rebuildall()

    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.opis_bibliograficzny_cache == WERSJA_1

    #
    # Koniec inicjalizacji -- właściwy test poniżej
    #

    url = reverse(
        "admin:bpp_szablondlaopisubibliograficznego_change", args=(szablon.pk,)
    )
    res = admin_app.get(url)

    form = res.forms["szablondlaopisubibliograficznego_form"]
    form["template"].value = t2.pk
    res = form.submit().maybe_follow()

    denorms.flush()

    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.opis_bibliograficzny_cache == WERSJA_2
