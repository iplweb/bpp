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
    assert imp.stan == ImportPracownikow.STAN_UTWORZONY
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
    renderowała. NIE używamy fixture ``import_pracownikow_performed`` — woła
    usunięte ``.perform()`` (dług Task 7)."""
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
