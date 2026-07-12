from unittest.mock import patch

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Jednostka
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowRow,
    ImportPracownikowTytul,
)


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
def test_panel_wyniku_analiza_przekierowuje_na_przeglad(admin_user):
    """Po analizie (dry-run) panel wyniku NIE pokazuje komunikatu-podglądu ani
    przycisku zatwierdzenia — kieruje na hub szczegółów. Auto-przejście robi
    liveops przez ``get_success_url()`` (inline ``<script>`` nie działał przy
    OOB-swapie — DOMParser+replaceWith nie odpala „already started" skryptu);
    w panelu zostaje link-fallback. Render BEZ requestu (jak worker)."""
    from django.template.loader import render_to_string

    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
    )
    przeglad = reverse("import_pracownikow:przeglad", kwargs={"pk": imp.pk})
    # Auto-przejście: liveops czyta get_success_url() po zakończonym dry-runie.
    assert imp.get_success_url() == przeglad
    html = render_to_string(
        "import_pracownikow/import_pracownikow_result.html",
        {"operation": imp, "byl_dry_run": True, "total": 5, "zmiany_potrzebne": 3},
    )
    # Link-fallback (no-JS / gdyby push „finished" nie dotarł) nadal jest.
    assert przeglad in html
    # stary komunikat-podgląd i in-panel „Zapisz" zniknęły
    assert "To był" not in html
    assert "Zapisz zmiany do bazy" not in html


@pytest.mark.django_db
def test_get_success_url_po_analizie_i_po_strukturze(admin_user):
    """``get_success_url()`` auto-przenosi na hub po analizie (dry-run) ORAZ po
    zapisaniu struktury (Krok 1 → Krok 2). Po strukturze dokleja
    ``?zapisano=struktura`` (item 4 — wyzwala flash na hubie). Po PEŁNEJ
    integracji osób i w stanie wyjściowym zwraca ``None`` (zostajemy na panelu
    wyniku liveops z podsumowaniem)."""
    imp = baker.make(ImportPracownikow, owner=admin_user)
    przeglad = reverse("import_pracownikow:przeglad", kwargs={"pk": imp.pk})
    imp.stan = ImportPracownikow.STAN_PRZEANALIZOWANY
    assert imp.get_success_url() == przeglad
    # Item 4: po zapisaniu struktury auto-przejście na Krok 2 z flag-paramem.
    imp.stan = ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA
    assert imp.get_success_url() == przeglad + "?zapisano=struktura"
    for stan in (
        ImportPracownikow.STAN_ZINTEGROWANY,
        ImportPracownikow.STAN_UTWORZONY,
    ):
        imp.stan = stan
        assert imp.get_success_url() is None


@pytest.mark.django_db
def test_hub_flash_po_zapisie_struktury(admin_client, admin_user):
    """Item 4: fresh-GET na hub z ``?zapisano=struktura`` (dokłada je
    ``get_success_url`` po redircie liveops) pokazuje jednorazowy flash
    „Struktura zapisana…". Bez paramu — brak flasha."""
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA,
    )
    url = reverse("import_pracownikow:przeglad", kwargs={"pk": imp.pk})
    resp = admin_client.get(url + "?zapisano=struktura")
    komunikaty = [m.message for m in list(resp.context["messages"])]
    assert any("Struktura zapisana" in k for k in komunikaty)
    # Bez paramu flash się nie pojawia.
    resp2 = admin_client.get(url)
    assert list(resp2.context["messages"]) == []


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
    # Z podglądu (Krok 1) wolno zapisać strukturę → stan „zatwierdzony".
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
    )
    url = reverse("import_pracownikow:zatwierdz", kwargs={"pk": imp.pk})
    with patch.object(ImportPracownikow, "run", lambda self, p: None):
        resp = admin_client.post(url, {"zakres": "jednostki"})
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZATWIERDZONY
    assert resp.status_code in (204, 302)


@pytest.mark.django_db
def test_zatwierdz_osoby_blokowane_w_przeanalizowany(admin_client, admin_user):
    """Bramka: import osób (pelny) z podglądu jest ZABLOKOWANY — najpierw
    struktura. Stan nie rusza."""
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
    )
    url = reverse("import_pracownikow:zatwierdz", kwargs={"pk": imp.pk})
    with patch.object(ImportPracownikow, "run", lambda self, p: None):
        resp = admin_client.post(url, {"zakres": "pelny"})
    assert resp.status_code == 400
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_PRZEANALIZOWANY


@pytest.mark.django_db
def test_zatwierdz_jednostki_blokowane_po_strukturze(admin_client, admin_user):
    """Bramka: zakres „same jednostki" wolno odpalić tylko z podglądu — po
    zapisaniu struktury (struktura_zintegrowana) jest odrzucany (bez sensu
    tworzyć jednostki drugi raz)."""
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA,
    )
    url = reverse("import_pracownikow:zatwierdz", kwargs={"pk": imp.pk})
    with patch.object(ImportPracownikow, "run", lambda self, p: None):
        resp = admin_client.post(url, {"zakres": "jednostki"})
    assert resp.status_code == 400
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA


@pytest.mark.django_db
def test_zatwierdz_osoby_blokowane_gdy_nierozstrzygniete_tytuly(
    admin_client, admin_user
):
    """Item 3: import osób (pelny) z fazy osób jest ZABLOKOWANY, dopóki są
    tytuły z pliku do utworzenia (nierozstrzygnięte) — import osób nie tworzy
    ich po cichu. Stan nie rusza."""
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA,
    )
    baker.make(
        ImportPracownikowTytul,
        parent=imp,
        nazwa_zrodlowa="prof. x",
        tryb=ImportPracownikowTytul.TRYB_BRAK,
        utworzony=None,
        decyzja=ImportPracownikowTytul.DECYZJA_AKCEPTUJ,
    )
    url = reverse("import_pracownikow:zatwierdz", kwargs={"pk": imp.pk})
    with patch.object(ImportPracownikow, "run", lambda self, p: None):
        resp = admin_client.post(url, {"zakres": "pelny"})
    assert resp.status_code == 400
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA


@pytest.mark.django_db
def test_zatwierdz_struktura_dotworzenie_tytulow_z_fazy_osob(admin_client, admin_user):
    """Item 3: zakres „struktura" (jednostki + tytuły) JEST dopuszczony z fazy
    osób — to ścieżka „Utwórz brakujące tytuły" (dotworzenie odłożonych tytułów
    przed importem osób)."""
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA,
    )
    url = reverse("import_pracownikow:zatwierdz", kwargs={"pk": imp.pk})
    with patch.object(ImportPracownikow, "run", lambda self, p: None):
        resp = admin_client.post(url, {"zakres": "struktura"})
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZATWIERDZONY
    assert imp.zakres_integracji == ImportPracownikow.ZAKRES_STRUKTURA
    assert resp.status_code in (204, 302)


@pytest.mark.django_db
def test_zatwierdz_osoby_po_strukturze_przechodzi(admin_client, admin_user):
    """Import osób (pelny) po zapisaniu struktury (Krok 2) → stan „zatwierdzony"."""
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA,
    )
    url = reverse("import_pracownikow:zatwierdz", kwargs={"pk": imp.pk})
    with patch.object(ImportPracownikow, "run", lambda self, p: None):
        resp = admin_client.post(url, {"zakres": "pelny"})
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZATWIERDZONY
    assert imp.zakres_integracji == ImportPracownikow.ZAKRES_PELNY
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
    # Degradacja do PELNY testowalna w fazie osób (gdzie pelny jest dozwolony).
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA,
        zakres_integracji=ImportPracownikow.ZAKRES_STRUKTURA,
    )
    url = reverse("import_pracownikow:zatwierdz", kwargs={"pk": imp.pk})
    with patch.object(ImportPracownikow, "run", lambda self, p: None):
        admin_client.post(url, {"zakres": "cokolwiek-niepoprawnego"})
    imp.refresh_from_db()
    assert imp.zakres_integracji == ImportPracownikow.ZAKRES_PELNY


@pytest.mark.django_db
def test_zatwierdz_bez_zakresu_domyslnie_pelny(admin_client, admin_user):
    # Domyślny zakres = PELNY (osoby) — dozwolony po zapisaniu struktury.
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA,
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


@pytest.mark.django_db(transaction=True)
def test_zatwierdz_wyscig_nie_dubluje_integracji(admin_user):
    """Dwa równoległe zatwierdzenia (celery z >1 workerem) NIE mogą oba przejść
    bramki na stanie odczytanym na starcie i wyzwolić integracji dwa razy
    (duplikaty autorów/jednostek/przepięć). Atomowy compare-and-set na ``stan``
    przepuszcza dokładnie JEDNO — drugie dostaje 400 i nie kolejkuje.

    Determinizm: barierą wymuszamy, że OBA żądania odczytają stan
    ``przeanalizowany`` ZANIM którekolwiek zapisze; dopiero wtedy oba próbują
    warunkowego UPDATE-a — baza serializuje je i tylko jeden trafia 1 wiersz."""
    import threading

    from django.db import connection
    from django.test import Client

    from import_pracownikow.views import ZatwierdzImportView

    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
    )
    url = reverse("import_pracownikow:zatwierdz", kwargs={"pk": imp.pk})

    barrier = threading.Barrier(2, timeout=10)
    tls = threading.local()
    enqueue_calls = []
    enqueue_lock = threading.Lock()
    orig_get_object = ZatwierdzImportView.get_object

    def synced_get_object(self, queryset=None):
        obj = orig_get_object(self, queryset)
        # Tylko PIERWSZY get_object w wątku trafia na barierę (RestartView woła
        # go drugi raz w zwycięzcy — bez guardu przegrany by nie doszedł i
        # zwycięzca deadlockowałby na barierze).
        if not getattr(tls, "waited", False):
            tls.waited = True
            try:
                barrier.wait()
            except threading.BrokenBarrierError:
                pass
        return obj

    def rec_enqueue(self):
        with enqueue_lock:
            enqueue_calls.append(self.pk)

    statuses = {}

    def worker(name):
        try:
            c = Client()
            c.force_login(admin_user)
            statuses[name] = c.post(url, {"zakres": "jednostki"}).status_code
        finally:
            connection.close()

    with (
        patch.object(ZatwierdzImportView, "get_object", synced_get_object),
        patch.object(ImportPracownikow, "enqueue", rec_enqueue),
    ):
        watki = [threading.Thread(target=worker, args=(n,)) for n in ("a", "b")]
        for w in watki:
            w.start()
        for w in watki:
            w.join(15)

    vals = list(statuses.values())
    assert len(vals) == 2, statuses
    assert [v for v in vals if v in (204, 302)], statuses  # dokładnie jeden sukces
    assert len([v for v in vals if v in (204, 302)]) == 1, statuses
    assert len([v for v in vals if v == 400]) == 1, statuses
    # Sedno: dokładnie jedna integracja zakolejkowana (bez duplikatu).
    assert len(enqueue_calls) == 1, enqueue_calls
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_ZATWIERDZONY


@pytest.mark.django_db
def test_panel_wyniku_czesciowy_import_nie_udaje_sukcesu(admin_user):
    """Gdy integracja pominęła wiersze (``wymaga_uwagi``), panel wyniku NIE jest
    zielony i pokazuje liczniki pominiętych — inaczej operator dostaje „Import
    zakończony" mimo że część osób nie weszła (uwaga reviewera #3)."""
    from django.template.loader import render_to_string

    imp = baker.make(
        ImportPracownikow, owner=admin_user, stan=ImportPracownikow.STAN_ZINTEGROWANY
    )
    html = render_to_string(
        "import_pracownikow/import_pracownikow_result.html",
        {
            "operation": imp,
            "byl_dry_run": False,
            "zakres": "pelny",
            "zintegrowano": 3,
            "pominieto_niedopasowane": 2,
            "pominieto_bez_jednostki": 1,
            "wymaga_uwagi": True,
        },
    )
    assert "panel callout warning" in html
    assert "panel callout success" not in html
    assert "częściowo" in html
    assert "<strong>2</strong>" in html  # pominięci niedopasowani
    assert "<strong>1</strong>" in html  # pominięci bez jednostki


@pytest.mark.django_db
def test_panel_wyniku_pelny_sukces_jest_zielony(admin_user):
    """Pełny import bez pominięć (``wymaga_uwagi=False``) → zielony panel."""
    from django.template.loader import render_to_string

    imp = baker.make(
        ImportPracownikow, owner=admin_user, stan=ImportPracownikow.STAN_ZINTEGROWANY
    )
    html = render_to_string(
        "import_pracownikow/import_pracownikow_result.html",
        {
            "operation": imp,
            "byl_dry_run": False,
            "zakres": "pelny",
            "zintegrowano": 5,
            "pominieto_niedopasowane": 0,
            "pominieto_bez_jednostki": 0,
            "wymaga_uwagi": False,
        },
    )
    assert "panel callout success" in html
    assert "częściowo" not in html
