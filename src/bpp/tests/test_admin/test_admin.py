# -*- encoding: utf-8 -*-
import pytest
from django.urls import NoReverseMatch
from django.urls.base import reverse
from model_mommy import mommy

from bpp.models import Jednostka, Praca_Doktorska, Praca_Habilitacyjna, Zrodlo
from bpp.models.autor import Autor
from bpp.models.cache import Autorzy, Rekord
from bpp.models.patent import Patent, Patent_Autor
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte, Wydawnictwo_Zwarte_Autor


@pytest.mark.parametrize(
    "klass",
    [
        Wydawnictwo_Ciagle,
        Wydawnictwo_Zwarte,
        Patent,
        Praca_Doktorska,
        Praca_Habilitacyjna,
    ],
)
def test_safe_html_dwa_tytuly_DwaTytuly(klass, admin_app):
    """Upewnij sie, ze bleach jest uruchamiany dla tych dwóch pól z DwaTytuly"""
    i = mommy.make(klass)
    if hasattr(i, "zrodlo"):
        z = mommy.make(Zrodlo)
        i.zrodlo = z
        i.save()

    if hasattr(i, "promotor"):
        p = mommy.make(Autor)
        i.promotor = p
        i.save()

    url = reverse(f"admin:bpp_{klass._meta.model_name}_change", args=(i.pk,))
    page = admin_app.get(url)

    page.forms[1]["tytul_oryginalny"].value = "<script>hi</script>"
    if hasattr(i, "tytul"):
        page.forms[1]["tytul"].value = "<script>hi</script>"
    page.forms[1].submit()

    i.refresh_from_db()

    assert i.tytul_oryginalny == "hi"
    if hasattr(i, "tytul"):
        assert i.tytul == "hi"


@pytest.mark.parametrize(
    "klass,autor_klass,name,url",
    [
        (
            Wydawnictwo_Ciagle,
            Wydawnictwo_Ciagle_Autor,
            "wydawnictwo_ciagle",
            "admin:bpp_wydawnictwo_ciagle_change",
        ),
        (
            Wydawnictwo_Zwarte,
            Wydawnictwo_Zwarte_Autor,
            "wydawnictwo_zwarte",
            "admin:bpp_wydawnictwo_zwarte_change",
        ),
        (Patent, Patent_Autor, "patent", "admin:bpp_patent_change"),
    ],
)
def test_zapisz_wydawnictwo_w_adminie(klass, autor_klass, name, url, admin_app):

    if klass == Wydawnictwo_Ciagle:
        wc = mommy.make(klass, zrodlo__nazwa="Kopara")
    else:
        wc = mommy.make(klass)

    wca = mommy.make(
        autor_klass,
        autor__imiona="Jan",
        autor__nazwisko="Kowalski",
        zapisany_jako="Jan Kowalski",
        rekord=wc,
    )

    url = reverse(url, args=(wc.pk,))
    res = admin_app.get(url)

    form = res.forms[name + "_form"]

    ZMIENIONE = "J[an] Kowalski"
    form["autorzy_set-0-zapisany_jako"].options.append((ZMIENIONE, False, ZMIENIONE))
    form["autorzy_set-0-zapisany_jako"].value = ZMIENIONE

    res2 = form.submit().maybe_follow()
    assert res2.status_code == 200
    assert "Please correct the error" not in res2.text
    assert "Proszę, popraw poniższe błędy." not in res2.text

    wca.refresh_from_db()
    assert wca.zapisany_jako == ZMIENIONE

    Rekord.objects.all().delete()
    Autorzy.objects.all().delete()


from django.apps import apps


@pytest.mark.parametrize("model", apps.get_models())
@pytest.mark.django_db
def test_widok_admina(admin_client, model):
    """Wejdź na podstrony admina 'changelist' oraz 'add' dla każdego modelu z aplikacji
    'bpp' który to istnieje w adminie (został zarejestrowany) i do którego to admin_client
    ma uprawnienia.

    W ten sposób możemy wyłapać błędy z nazwami pól w adminie, których to Django nie wyłapie
    przed uruchomieniem aplikacji.
    """

    # for model in apps.get_models():
    app_label = model._meta.app_label
    model_name = model._meta.model_name

    if app_label != "bpp":
        return

    url_name = "admin:%s_%s_changelist" % (app_label, model_name)
    try:
        url = reverse(url_name)
    except NoReverseMatch:
        return

    res = admin_client.get(url)
    assert res.status_code == 200, "changelist failed for %r" % model

    res = admin_client.get(url + "?q=fafa")
    assert res.status_code == 200, "changelist query failed for %r" % model

    url_name = "admin:%s_%s_add" % (app_label, model_name)
    url = reverse(url_name)
    res = admin_client.get(url)

    assert res.status_code == 200, "add failed for %r" % model


@pytest.mark.django_db
def test_admin_jednostka_sortowanie(uczelnia, admin_client):
    url_name = reverse("admin:bpp_jednostka_changelist")

    mommy.make(Jednostka)
    mommy.make(Jednostka)
    mommy.make(Jednostka)

    uczelnia.sortuj_jednostki_alfabetycznie = True
    uczelnia.save()

    assert admin_client.get(url_name).status_code == 200

    uczelnia.sortuj_jednostki_alfabetycznie = False
    uczelnia.save()

    assert admin_client.get(url_name).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["wydawnictwo_zwarte", "wydawnictwo_ciagle"])
def test_admin_zewnetrzna_baza_danych(admin_client, url):
    url_name = reverse(f"admin:bpp_{url}_add")
    res = admin_client.get(url_name)
    assert "z zewnętrznymi bazami" in res.content.decode("utf-8")
