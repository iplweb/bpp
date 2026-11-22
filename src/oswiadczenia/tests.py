import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Dyscyplina, Rekord
from oswiadczenia.tasks import sanitize_filename
from oswiadczenia.views import (
    WydrukOswiadczenFilterForm,
    calculate_export_ranges,
    get_autor_dyscyplina_info,
)


class _Okres:
    """Okres ewaluacji bez bazy — formularzowi wystarczą lata."""

    rok_od = 2022
    rok_do = 2025


def test_wydruk_oswiadczen_filter_form_defaults():
    """Bez lat w zapytaniu — cały okres ewaluacji z paska."""
    form = WydrukOswiadczenFilterForm(data={}, okres=_Okres)
    assert form.is_valid()
    assert form.cleaned_data["rok_od"] == 2022
    assert form.cleaned_data["rok_do"] == 2025
    assert form.cleaned_data["szukaj_autor"] == ""
    assert form.cleaned_data["szukaj_tytul"] == ""
    assert form.cleaned_data["przypieta"] == ""


def test_wydruk_oswiadczen_filter_form_with_values():
    """Test that filter form accepts valid values."""
    form = WydrukOswiadczenFilterForm(
        data={
            "rok_od": 2023,
            "rok_do": 2024,
            "szukaj_autor": "Kowalski",
            "szukaj_tytul": "publikacja",
            "przypieta": "tak",
        },
        okres=_Okres,
    )
    assert form.is_valid()
    assert form.cleaned_data["rok_od"] == 2023
    assert form.cleaned_data["rok_do"] == 2024
    assert form.cleaned_data["szukaj_autor"] == "Kowalski"


def test_wydruk_oswiadczen_filter_form_lata_przyciete_do_okresu():
    """Lata spoza okresu (np. po przełączeniu okresu na pasku) są przycinane
    do okresu, a pozostałe filtry zostają."""
    form = WydrukOswiadczenFilterForm(
        data={"rok_od": 2019, "rok_do": 2028, "szukaj_autor": "Kowalski"},
        okres=_Okres,
    )
    assert form.is_valid()
    assert form.cleaned_data["rok_od"] == 2022
    assert form.cleaned_data["rok_do"] == 2025
    assert form.cleaned_data["szukaj_autor"] == "Kowalski"


def test_calculate_export_ranges_small_count():
    """Test calculate_export_ranges returns empty for small counts."""
    result = calculate_export_ranges(100, chunk_size=5000)
    assert result == []


def test_calculate_export_ranges_large_count():
    """Test calculate_export_ranges returns proper ranges for large counts."""
    result = calculate_export_ranges(12000, chunk_size=5000)
    assert len(result) == 3
    assert result[0] == (0, 5000, "1-5000")
    assert result[1] == (5000, 10000, "5001-10000")
    assert result[2] == (10000, 12000, "10001-12000")


def test_sanitize_filename_removes_invalid_chars():
    """Test that sanitize_filename removes invalid characters."""
    result = sanitize_filename('test/file:name*with?invalid"chars<>|')
    assert "/" not in result
    assert ":" not in result
    assert "*" not in result
    assert "?" not in result
    assert '"' not in result


def test_sanitize_filename_truncates():
    """Test that sanitize_filename truncates to max_length."""
    result = sanitize_filename("a" * 100, max_length=30)
    assert len(result) == 30


@pytest.mark.django_db
def test_get_autor_dyscyplina_info_returns_dict(autor_jan_kowalski, dyscyplina1):
    """Test get_autor_dyscyplina_info returns proper dict structure."""
    # Create Autor_Dyscyplina record
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski,
        rok=2023,
        dyscyplina_naukowa=dyscyplina1,
    )

    result = get_autor_dyscyplina_info(autor_jan_kowalski, 2023)

    assert "ma_dwie_dyscypliny" in result
    assert "dyscyplina_naukowa" in result
    assert "subdyscyplina_naukowa" in result
    assert result["dyscyplina_naukowa"] == dyscyplina1


@pytest.mark.django_db
def test_get_autor_dyscyplina_info_missing():
    """Test get_autor_dyscyplina_info returns defaults for missing record."""
    autor = baker.make(Autor)
    result = get_autor_dyscyplina_info(autor, 2099)

    assert result["ma_dwie_dyscypliny"] is False
    assert result["dyscyplina_naukowa"] is None


@pytest.mark.django_db
def test_praca_tabela_oswiadczenia_drukuj(
    zwarte_z_dyscyplinami,
    admin_client,
    uczelnia,  # noqa
):  # noqa
    uczelnia.drukuj_oswiadczenia = True
    uczelnia.save()

    res = admin_client.get(
        reverse(
            "bpp:browse_rekord",
            args=Rekord.objects.get_for_model(zwarte_z_dyscyplinami).pk,
        ),
        follow=True,
    )
    assert (
        b"Wydruk dyscypliny zg" in res.content
        and b"oszonej dla publikacji" in res.content
    )


@pytest.mark.django_db
def test_praca_tabela_oswiadczenia_NIE_drukuj(
    zwarte_z_dyscyplinami,
    admin_client,
    uczelnia,  # noqa
):  # noqa
    uczelnia.drukuj_oswiadczenia = False
    uczelnia.save()

    res = admin_client.get(
        reverse(
            "bpp:browse_rekord",
            args=Rekord.objects.get_for_model(zwarte_z_dyscyplinami).pk,
        ),
        follow=True,
    )
    assert (
        b"Wydruk dyscypliny zg" not in res.content
        or b"oszonej dla publikacji" not in res.content
    )


@pytest.mark.django_db
def test_praca_tabela_oswiadczenia_nie_drukuj(
    zwarte_z_dyscyplinami,
    admin_client,
    uczelnia,  # noqa
):  # noqa
    uczelnia.drukuj_oswiadczenia = False
    uczelnia.save()

    res = admin_client.get(
        reverse(
            "bpp:browse_rekord",
            args=Rekord.objects.get_for_model(zwarte_z_dyscyplinami).pk,
        ),
        follow=True,
    )
    assert b"<!-- wydruk oswiadczenia -->" not in res.content


@pytest.mark.django_db
def test_oswiadczenie_jedno(zwarte_z_dyscyplinami, admin_client):  # noqa
    rekord = Rekord.objects.get_for_model(zwarte_z_dyscyplinami)

    autor = rekord.autorzy_set.first()
    dyscyplina_pracy = rekord.autorzy_set.first().dyscyplina_naukowa
    url = reverse(
        "oswiadczenia:jedno-oswiadczenie",
        args=(rekord.pk[0], rekord.pk[1], autor.autor.pk, dyscyplina_pracy.pk),
    )
    res = admin_client.get(url)
    assert res.status_code == 200
    assert b"window.print" in res.content


@pytest.mark.django_db
def test_oswiadczenie_druga_dyscyplina(zwarte_z_dyscyplinami, admin_client):  # noqa
    rekord = Rekord.objects.get_for_model(zwarte_z_dyscyplinami)

    autor = rekord.autorzy_set.first()
    dyscyplina_pracy = rekord.autorzy_set.first().dyscyplina_naukowa
    url = reverse(
        "oswiadczenia:jedno-oswiadczenie-druga-dyscyplina",
        args=(rekord.pk[0], rekord.pk[1], autor.autor.pk, dyscyplina_pracy.pk),
    )
    res = admin_client.get(url)
    assert res.status_code == 200
    assert b"window.print" in res.content


@pytest.mark.django_db
def test_oswiadczenie_wiele(zwarte_z_dyscyplinami, admin_client):  # noqa
    rekord = Rekord.objects.get_for_model(zwarte_z_dyscyplinami)

    url = reverse(
        "oswiadczenia:wiele-oswiadczen",
        args=(rekord.pk[0], rekord.pk[1]),
    )
    res = admin_client.get(url)
    assert res.status_code == 200
    assert b"window.print" in res.content


@pytest.mark.django_db
def test_oswiadczenia_publikacji_kontekst_filtruje_po_uczelni(
    zwarte_dwie_uczelnie,
    jednostka,
    druga_uczelnia,
    rf,
    django_user_model,
):
    """OswiadczeniaPublikacji.get_context_data zwraca tylko punktacje dla
    uczelni odczytu — rzedy z drugiej uczelni sa wykluczone."""
    from oswiadczenia.views import OswiadczeniaPublikacji

    zwarte_dwie_uczelnie.przelicz_punkty_dyscyplin()

    from bpp.models import Cache_Punktacja_Autora, Rekord

    rekord = Rekord.objects.get_for_model(zwarte_dwie_uczelnie)

    # Upewnij sie, ze obie uczelnie maja wiersze w cache
    wszystkie = Cache_Punktacja_Autora.objects.filter(rekord_id=rekord.pk)
    uczelnie_w_cache = set(wszystkie.values_list("jednostka__uczelnia_id", flat=True))
    assert jednostka.uczelnia_id in uczelnie_w_cache, (
        "U1 nie ma wierszy w Cache_Punktacja_Autora — test bylby pusty"
    )
    assert druga_uczelnia.pk in uczelnie_w_cache, (
        "U2 nie ma wierszy w Cache_Punktacja_Autora — test bylby nie-wykluczajacy"
    )

    # Superuser z _uczelnia = U1
    user = django_user_model.objects.create_superuser(
        username="test_multi_uczelnia", password="pass"
    )
    request = rf.get("/")
    request.user = user
    request._uczelnia = jednostka.uczelnia

    view = OswiadczeniaPublikacji()
    view.request = request
    view.kwargs = {
        "content_type_id": rekord.pk[0],
        "object_id": rekord.pk[1],
    }
    view.object = view.get_object()

    ctx = view.get_context_data()
    punktacje_ids = set(
        ctx["punktacje"].values_list("jednostka__uczelnia_id", flat=True)
    )

    assert punktacje_ids == {jednostka.uczelnia_id}, (
        f"Oczekiwano tylko U1 ({jednostka.uczelnia_id}), otrzymano: {punktacje_ids}"
    )
    assert druga_uczelnia.pk not in punktacje_ids


@pytest.mark.django_db
def test_remove_old_oswiadczenia_export_files():
    from datetime import timedelta

    from django.utils import timezone
    from model_bakery import baker

    from oswiadczenia.models import OswiadczeniaExportTask
    from oswiadczenia.tasks import remove_old_oswiadczenia_export_files

    # Create a recent task (should NOT be deleted)
    baker.make(OswiadczeniaExportTask)

    # Create an old task (should be deleted)
    old_task = baker.make(OswiadczeniaExportTask)
    old_task.created_at = timezone.now() - timedelta(days=20)
    old_task.save()

    assert OswiadczeniaExportTask.objects.count() == 2

    remove_old_oswiadczenia_export_files()

    assert OswiadczeniaExportTask.objects.count() == 1


# --- Ścieżki PDF (xhtml2pdf importowany leniwie przez ``tasks._pisa``) -----
# Bez tych testów zepsuty leniwy import (literówka, brak pakietu w obrazie)
# wyszedłby dopiero przy pierwszym eksporcie PDF na produkcji.


def _fake_decl():
    from types import SimpleNamespace

    return {
        "autor": SimpleNamespace(nazwisko="Kowalski", imiona="Jan"),
        "rekord": SimpleNamespace(pk=(1, 2), tytul_oryginalny="Tytuł pracy"),
        "dyscyplina_pracy": "nauki medyczne",
    }


def test_pisa_import_leniwy():
    from oswiadczenia.tasks import _pisa

    pisa = _pisa()
    assert pisa is not None
    assert hasattr(pisa, "CreatePDF")


def test_generate_declaration_content_pdf(monkeypatch):
    from oswiadczenia import tasks

    monkeypatch.setattr(
        tasks, "render_declaration_html", lambda decl, uczelnia: "<p>Zażółć</p>"
    )
    filename, content = tasks.generate_declaration_content(
        _fake_decl(), uczelnia=None, export_format="pdf"
    )
    assert filename.endswith(".pdf")
    assert content.startswith(b"%PDF")


def test_generate_combined_pdf(monkeypatch):
    from types import SimpleNamespace

    from oswiadczenia import tasks

    monkeypatch.setattr(
        tasks,
        "render_declaration_content_only",
        lambda decl, uczelnia: "<p>Oświadczenie</p>",
    )
    task = SimpleNamespace(processed_items=0, current_item="", save=lambda: None)
    content = tasks.generate_combined_pdf(
        [_fake_decl(), _fake_decl()], uczelnia=None, task=task
    )
    assert content.startswith(b"%PDF")
    assert task.processed_items == 2


@pytest.mark.django_db
@pytest.mark.parametrize("rok_pracy,lata", [(2023, "2022-2025"), (2027, "2026-2030")])
def test_oswiadczenie_lata_z_okresu_pracy(
    zwarte_z_dyscyplinami, admin_client, rok_pracy, lata
):  # noqa
    """Treść oświadczenia: „za lata ...” wg okresu, do którego należy praca —
    nie na sztywno 2022-2025."""
    # update() z pominięciem walidacji przypisań autorów do dyscyplin na rok
    type(zwarte_z_dyscyplinami).objects.filter(pk=zwarte_z_dyscyplinami.pk).update(
        rok=rok_pracy
    )
    rekord = Rekord.objects.get_for_model(zwarte_z_dyscyplinami)
    autor = rekord.autorzy_set.first()
    url = reverse(
        "oswiadczenia:jedno-oswiadczenie",
        args=(rekord.pk[0], rekord.pk[1], autor.autor.pk, autor.dyscyplina_naukowa.pk),
    )
    res = admin_client.get(url)
    assert f"za lata <strong>{lata}</strong>" in res.content.decode()


@pytest.mark.django_db
def test_wydruk_stary_adres_przekierowuje(admin_client):
    res = admin_client.get("/oswiadczenia/wydruk-2022-25/?szukaj_autor=X")
    assert res.status_code == 302
    assert res["Location"] == reverse("oswiadczenia:wydruk") + "?szukaj_autor=X"


@pytest.mark.django_db
def test_wydruk_lata_i_pasek_wg_wybranego_okresu(admin_client):
    """Lista oświadczeń bierze lata z okresu wybranego na pasku i ten pasek
    pokazuje; tytuł bez lat."""
    from ewaluacja_common.models import OkresEwaluacji

    okres = OkresEwaluacji.objects.get(rok_od=2026)
    admin_client.post(reverse("ewaluacja_common:wybierz_okres"), {"okres": okres.pk})
    res = admin_client.get(reverse("oswiadczenia:wydruk"))
    html = res.content.decode()
    assert res.context["rok_od"] == 2026
    assert res.context["rok_do"] == 2030
    assert 'class="pasek-okresu"' in html
    assert "<h1>Wydruk oświadczeń</h1>" in html


@pytest.mark.django_db
@pytest.mark.parametrize(
    "rok_pracy,szablon",
    [
        (2023, "oswiadczenia/tresc_jednego_oswiadczenia.html"),
        (2027, "oswiadczenia/tresc_jednego_oswiadczenia_2026_2030.html"),
    ],
)
def test_oswiadczenie_szablon_okresu(
    zwarte_z_dyscyplinami, admin_client, rok_pracy, szablon
):  # noqa
    """Praca z okresu 2026–2030 dostaje osobny szablon treści oświadczenia;
    okres bez własnego szablonu — wspólny."""
    type(zwarte_z_dyscyplinami).objects.filter(pk=zwarte_z_dyscyplinami.pk).update(
        rok=rok_pracy
    )
    rekord = Rekord.objects.get_for_model(zwarte_z_dyscyplinami)
    autor = rekord.autorzy_set.first()
    url = reverse(
        "oswiadczenia:jedno-oswiadczenie",
        args=(rekord.pk[0], rekord.pk[1], autor.autor.pk, autor.dyscyplina_naukowa.pk),
    )
    res = admin_client.get(url)
    assert szablon in [t.name for t in res.templates]


def test_szablony_oswiadczenia_task(db):
    from oswiadczenia.templatetags.oswiadczenia_tags import szablony_oswiadczenia

    assert szablony_oswiadczenia(2028)[0].endswith("_2026_2030.html")
    assert szablony_oswiadczenia(None) == [
        "oswiadczenia/tresc_jednego_oswiadczenia.html"
    ]


@pytest.mark.django_db
def test_szablon_2026_2030_w_bazie_z_adnotacja(zwarte_z_dyscyplinami, admin_client):
    """Migracja zakłada szablon 2026–2030 w bazie (edytowalny w panelu):
    lata nowego okresu i adnotacja o starej podstawie prawnej.

    Funkcję migracji wołamy wprost: dane z migracji mogą zniknąć po flushu
    testu transakcyjnego na tym samym workerze."""
    import importlib

    from dbtemplates.models import Template
    from django.apps import apps

    migracja = importlib.import_module(
        "oswiadczenia.migrations.0007_szablon_oswiadczenia_2026_2030"
    )
    Template.objects.filter(name=migracja.TEMPLATE_NAME).delete()
    migracja.forward(apps, None)
    # druga migracja nie dubluje ani nie nadpisuje istniejącego szablonu
    migracja.forward(apps, None)

    t = Template.objects.get(name=migracja.TEMPLATE_NAME)
    assert "za lata <strong>2026-2030</strong>" in t.content
    assert "[stara podstawa prawna]" in t.content

    type(zwarte_z_dyscyplinami).objects.filter(pk=zwarte_z_dyscyplinami.pk).update(
        rok=2027
    )
    rekord = Rekord.objects.get_for_model(zwarte_z_dyscyplinami)
    autor = rekord.autorzy_set.first()
    url = reverse(
        "oswiadczenia:jedno-oswiadczenie",
        args=(rekord.pk[0], rekord.pk[1], autor.autor.pk, autor.dyscyplina_naukowa.pk),
    )
    html = admin_client.get(url).content.decode()
    assert "[stara podstawa prawna]" in html
    assert "za lata <strong>2026-2030</strong>" in html
