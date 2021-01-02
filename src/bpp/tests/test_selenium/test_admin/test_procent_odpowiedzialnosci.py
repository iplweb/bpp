# -*- encoding: utf-8 -*-

from django.apps import apps

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

import pytest

from bpp.tests import (
    add_extra_autor_inline,
    fill_admin_form,
    fill_admin_inline,
    set_element,
    submit_admin_form,
    submitted_form_bad,
    submitted_form_good,
)

from django_bpp.selenium_util import wait_for_page_load

ID = "id_tytul_oryginalny"

pytestmark = [pytest.mark.slow, pytest.mark.selenium]


@pytest.mark.parametrize(
    "klass", ["wydawnictwo_ciagle", "wydawnictwo_zwarte", "patent"]
)
def test_procent_odpowiedzialnosci_baseModel_AutorFormset_jeden_autor(
    asgi_live_server,
    admin_browser,
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    typ_odpowiedzialnosci_autor,
    zrodlo,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    jezyki,
    klass,
):
    url = asgi_live_server.url + reverse("admin:bpp_%s_add" % klass)

    with wait_for_page_load(admin_browser):
        admin_browser.visit(url)
    fill_admin_form(admin_browser)
    add_extra_autor_inline(admin_browser)
    fill_admin_inline(
        admin_browser,
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        zapisany_jako="Kopara",
        procent="100.00",
    )
    submit_admin_form(admin_browser)
    assert submitted_form_good(admin_browser)


@pytest.mark.parametrize(
    "klass", ["wydawnictwo_ciagle", "wydawnictwo_zwarte", "patent"]
)
def test_procent_odpowiedzialnosci_baseModel_AutorFormset_problem_jeden_autor(
    asgi_live_server,
    admin_browser,
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    typ_odpowiedzialnosci_autor,
    zrodlo,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    jezyki,
    klass,
):
    url = asgi_live_server.url + reverse("admin:bpp_%s_add" % klass)

    with wait_for_page_load(admin_browser):
        admin_browser.visit(url)
    fill_admin_form(admin_browser)
    add_extra_autor_inline(admin_browser)
    fill_admin_inline(
        admin_browser,
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        zapisany_jako="Kopara",
        procent="100.01",
    )
    submit_admin_form(admin_browser)
    assert submitted_form_bad(admin_browser)


@pytest.mark.parametrize(
    "klass", ["wydawnictwo_ciagle", "wydawnictwo_zwarte", "patent"]
)
def test_procent_odpowiedzialnosci_baseModel_AutorFormset_dwoch_autorow(
    asgi_live_server,
    admin_browser,
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    typ_odpowiedzialnosci_autor,
    zrodlo,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    jezyki,
    klass,
):
    url = asgi_live_server.url + reverse("admin:bpp_%s_add" % klass)

    with wait_for_page_load(admin_browser):
        admin_browser.visit(url)
    fill_admin_form(admin_browser)
    add_extra_autor_inline(admin_browser)
    fill_admin_inline(
        admin_browser,
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        zapisany_jako="Kopara",
        procent="50.00",
    )
    add_extra_autor_inline(admin_browser, 1)
    fill_admin_inline(
        admin_browser,
        autor=autor_jan_nowak,
        jednostka=jednostka,
        zapisany_jako="Kopara",
        procent="50.00",
        no=1,
    )
    submit_admin_form(admin_browser)
    assert submitted_form_good(admin_browser)


@pytest.mark.parametrize(
    "klass", ["wydawnictwo_ciagle", "wydawnictwo_zwarte", "patent"]
)
def test_procent_odpowiedzialnosci_baseModel_AutorFormset_problem_dwoch_autorow(
    asgi_live_server,
    admin_browser,
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    typ_odpowiedzialnosci_autor,
    zrodlo,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    jezyki,
    klass,
):
    url = asgi_live_server.url + reverse("admin:bpp_%s_add" % klass)

    with wait_for_page_load(admin_browser):
        admin_browser.visit(url)
    fill_admin_form(admin_browser)
    add_extra_autor_inline(admin_browser)
    fill_admin_inline(
        admin_browser,
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        zapisany_jako="Kopara",
        procent="50.00",
    )
    add_extra_autor_inline(admin_browser, 1)
    fill_admin_inline(
        admin_browser,
        autor=autor_jan_nowak,
        jednostka=jednostka,
        zapisany_jako="Kopara",
        procent="50.01",
        no=1,
    )
    submit_admin_form(admin_browser)
    assert submitted_form_bad(admin_browser)


@pytest.mark.parametrize(
    "klass", ["wydawnictwo_ciagle", "wydawnictwo_zwarte", "patent"]
)
def test_procent_odpowiedzialnosci_baseModel_AutorFormset_dobrze_potem_zle_dwoch_autorow(
    asgi_live_server,
    admin_browser,
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    typ_odpowiedzialnosci_autor,
    zrodlo,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    jezyki,
    klass,
):
    url = asgi_live_server.url + reverse("admin:bpp_%s_add" % klass)

    with wait_for_page_load(admin_browser):
        admin_browser.visit(url)

    fill_admin_form(admin_browser)

    add_extra_autor_inline(admin_browser)
    fill_admin_inline(
        admin_browser,
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        zapisany_jako="Kopara",
        procent="50.00",
    )

    add_extra_autor_inline(admin_browser)
    fill_admin_inline(
        admin_browser,
        autor=autor_jan_nowak,
        jednostka=jednostka,
        zapisany_jako="Kopara",
        procent="50.00",
        no=1,
    )

    submit_admin_form(admin_browser)

    assert submitted_form_good(admin_browser)

    model = apps.get_app_config("bpp").get_model(klass)

    url = asgi_live_server.url + reverse(
        "admin:bpp_%s_change" % klass, args=(model.objects.first().pk,)
    )

    with wait_for_page_load(admin_browser):
        admin_browser.visit(url)

    set_element(admin_browser, "id_autorzy_set-0-procent", "50.01")

    submit_admin_form(admin_browser)
    assert submitted_form_bad(admin_browser)
