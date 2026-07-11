from unittest.mock import patch

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Jednostka
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow


@pytest.mark.django_db
def test_strona_live_uzywa_get_absolute_url(admin_client, admin_user):
    imp = baker.make(ImportPracownikow, owner=admin_user)
    url = imp.get_absolute_url()
    assert url == (f"/live/import_pracownikow.importpracownikow/{imp.pk}/")
    resp = admin_client.get(url)
    assert resp.status_code == 200


@pytest.mark.django_db
def test_strona_live_uzywa_wlasnego_host_template(admin_client, admin_user):
    """Host-page (T6) musi być faktycznie użyty, nie tylko fallback
    liveops/operation.html (LiveOperationView.get_template_names próbuje
    naszego szablonu jako pierwszego)."""
    imp = baker.make(ImportPracownikow, owner=admin_user)
    resp = admin_client.get(imp.get_absolute_url())
    template_names = [t.name for t in resp.templates if t.name]
    assert "import_pracownikow/import_pracownikow.html" in template_names


@pytest.mark.django_db
def test_strona_live_wstrzykuje_csrf_header_dla_htmx(admin_client, admin_user):
    """Anuluj/Ponów liveops to gołe przyciski htmx POZA formularzem. Przy
    CSRF_COOKIE_HTTPONLY=True liveops.js nie odczyta tokenu z ciasteczka
    (document.cookie go nie widzi), więc POST /cancel/ i /restart/ dostawał 403
    CSRF token missing. Host-page wstrzykuje token nagłówkiem X-CSRFToken przez
    dziedziczone hx-headers — regresja na obecność wrappera i NIEPUSTY token."""
    imp = baker.make(ImportPracownikow, owner=admin_user)
    resp = admin_client.get(imp.get_absolute_url())
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "hx-headers" in content
    assert "X-CSRFToken" in content
    assert '"X-CSRFToken": ""' not in content  # token musi być realny, nie pusty


@pytest.mark.django_db
def test_panel_wyniku_zatwierdz_jedzie_przez_htmx(admin_user):
    """Panel wyniku bywa renderowany przez workera (OOB-swap po WebSockecie) BEZ
    kontekstu requestu, więc {% csrf_token %} w body jest pusty. Przycisk „Zapisz"
    musi więc jechać przez htmx (hx-post), żeby dziedziczyć nagłówek X-CSRFToken
    z wrappera host-page — inaczej POST /zatwierdz/ dostaje 403 w wersji push."""
    from django.template.loader import render_to_string

    imp = baker.make(ImportPracownikow, owner=admin_user)
    # render BEZ requestu — dokładnie tak jak robi to worker przy OOB-swapie
    html = render_to_string(
        "import_pracownikow/import_pracownikow_result.html",
        {"operation": imp, "byl_dry_run": True, "total": 5, "zmiany_potrzebne": 3},
    )
    assert "hx-post=" in html
    assert 'hx-swap="none"' in html
    assert f"/{imp.pk}/zatwierdz/" in html


@pytest.mark.django_db
def test_index_renderuje_bez_noreversematch(admin_client, admin_user):
    """Landmine: importpracownikow_list.html linkował do usuniętego URL-a
    ``import_pracownikow:importpracownikow-router`` — NoReverseMatch przy
    renderze strony index, gdy na liście jest choć jeden import."""
    baker.make(ImportPracownikow, owner=admin_user)
    url = reverse("import_pracownikow:index")
    resp = admin_client.get(url)
    assert resp.status_code == 200


@pytest.mark.django_db
def test_zatwierdz_ustawia_stan_zatwierdzony_i_reenqueue(admin_client, admin_user):
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
    )
    url = reverse("import_pracownikow:zatwierdz", kwargs={"pk": imp.pk})
    with patch.object(ImportPracownikow, "run", lambda self, p: None):
        resp = admin_client.post(url)
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZATWIERDZONY
    assert resp.status_code in (204, 302)


@pytest.mark.django_db
def test_zatwierdz_zakres_jednostki_ustawia_pole(admin_client, admin_user):
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
    )
    url = reverse("import_pracownikow:zatwierdz", kwargs={"pk": imp.pk})
    with patch.object(ImportPracownikow, "run", lambda self, p: None):
        admin_client.post(url, {"zakres": "jednostki"})
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZATWIERDZONY
    assert imp.zakres_integracji == ImportPracownikow.ZAKRES_JEDNOSTKI


@pytest.mark.django_db
def test_zatwierdz_zakres_nieprawidlowy_degraduje_do_pelny(admin_client, admin_user):
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        zakres_integracji=ImportPracownikow.ZAKRES_STRUKTURA,
    )
    url = reverse("import_pracownikow:zatwierdz", kwargs={"pk": imp.pk})
    with patch.object(ImportPracownikow, "run", lambda self, p: None):
        admin_client.post(url, {"zakres": "cokolwiek-niepoprawnego"})
    imp.refresh_from_db()
    assert imp.zakres_integracji == ImportPracownikow.ZAKRES_PELNY


@pytest.mark.django_db
def test_zatwierdz_bez_zakresu_domyslnie_pelny(admin_client, admin_user):
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
    )
    url = reverse("import_pracownikow:zatwierdz", kwargs={"pk": imp.pk})
    with patch.object(ImportPracownikow, "run", lambda self, p: None):
        admin_client.post(url)
    imp.refresh_from_db()
    assert imp.zakres_integracji == ImportPracownikow.ZAKRES_PELNY


@pytest.mark.django_db
def test_restart_analiza_cofa_stan_i_kasuje_wiersze(admin_client, admin_user):
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
    )
    baker.make(
        "import_pracownikow.ImportPracownikowRow", parent=imp, zmiany_potrzebne=False
    )
    url = reverse("import_pracownikow:restart-analiza", kwargs={"pk": imp.pk})
    with patch.object(ImportPracownikow, "run", lambda self, p: None):
        admin_client.post(url)
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZMAPOWANY
    assert imp.importpracownikowrow_set.count() == 0  # on_restart skasował


@pytest.mark.django_db
def test_importpracownikow_results_renderuje_liste_modyfikacji(
    admin_client, admin_user
):
    """Regresja Task 6 review: szablon importpracownikowrow_list.html
    odwoływał się do zmiennej ``object``, ale ``ImportPracownikowResultsView``
    (ListView, ``context_object_name="object_list"``) przekazuje w kontekście
    ``parent_object``, nie ``object``. Django cicho zwraca falsy dla
    niezdefiniowanej zmiennej, więc ``{% if object.finished_successfully %}``
    było zawsze False i cała tabela "Lista modyfikacji" nigdy się nie
    renderowała. NIE używamy fixture ``import_pracownikow_performed`` — po
    Task 7 działa (analiza+integracja przez ``run()``), ale wymaga
    prawdziwego pliku XLS; tu wystarcza ręcznie zbudowany, minimalny stan
    (``STAN_ZINTEGROWANY`` + jeden wiersz), więc test zostaje szybszy i
    niezależny od danych testowych."""
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        finished_successfully=True,
        stan=ImportPracownikow.STAN_ZINTEGROWANY,
    )
    autor = baker.make(Autor, nazwisko="Testowy", imiona="Jan")
    jednostka = baker.make(Jednostka, nazwa="Testowa Jednostka", skrot="Test. Jedn.")
    baker.make(
        ImportPracownikowRow,
        parent=imp,
        autor=autor,
        jednostka=jednostka,
        zmiany_potrzebne=True,
    )

    url = reverse("import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk})
    resp = admin_client.get(url)

    assert resp.status_code == 200
    content = resp.content.decode()
    assert "Lista modyfikacji" in content
    assert imp.plik_xls.name in content


@pytest.mark.django_db
def test_importpracownikow_results_datatables_init(admin_client, admin_user):
    """Tabela autorów ma id + inicjalizację DataTables (client-side filtr/sort)."""
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        finished_successfully=True,
        stan=ImportPracownikow.STAN_ZINTEGROWANY,
    )
    autor = baker.make(Autor, nazwisko="Testowy", imiona="Jan")
    jednostka = baker.make(Jednostka, nazwa="Testowa Jednostka", skrot="Test. Jedn.")
    baker.make(
        ImportPracownikowRow,
        parent=imp,
        autor=autor,
        jednostka=jednostka,
        zmiany_potrzebne=True,
    )
    url = reverse("import_pracownikow:importpracownikow-results", kwargs={"pk": imp.pk})
    content = admin_client.get(url).content.decode()
    assert 'id="tabela-autorow"' in content
    assert ".DataTable(" in content


def test_importpracownikow_results_bez_pagination_include():
    """Martwy ``{% include "pagination.html" %}`` (widok bez ``paginate_by``)
    usunięty z ``<tbody>`` — nie-``<tr>`` w tbody psuje parsowanie DataTables."""
    from pathlib import Path

    import import_pracownikow

    tpl = (
        Path(import_pracownikow.__file__).parent
        / "templates"
        / "import_pracownikow"
        / "importpracownikowrow_list.html"
    )
    assert "pagination.html" not in tpl.read_text(encoding="utf-8")
