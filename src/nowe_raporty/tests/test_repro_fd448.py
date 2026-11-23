"""FD#448: edycja źródła danych z poziomu otwartego raportu.

Otwarty raport pokazuje osobom uprawnionym listę „Źródła danych tego raportu”
z odnośnikami „edytuj źródło danych”. Formularz źródła danych otwarty w ten
sposób po zapisaniu wraca do raportu (z tymi samymi parametrami).
"""

from urllib.parse import parse_qs, urlsplit

import pytest
from django.contrib.auth.models import Group, Permission
from django.urls import reverse
from flexible_reports.models import Datasource, Report, ReportElement
from flexible_reports.query_backends import DJANGOQL
from lxml import html as lxml_html
from model_bakery import baker

from bpp.models import Autor
from nowe_raporty.seeding import seed_default_reports


@pytest.fixture
def url_raportu(db, uczelnia, typy_odpowiedzialnosci):
    seed_default_reports()
    autor = baker.make(Autor)
    return reverse(
        "nowe_raporty:raport_generuj", args=["raport-autorow", autor.pk, 2020, 2020]
    )


def _odnosniki(res):
    drzewo = lxml_html.fromstring(res.content.decode())
    return drzewo.xpath("//*[@data-zrodla-danych]//a")


def _dane_formularza(zrodlo, **zmiany):
    return {
        "label": zrodlo.label,
        "base_model": zrodlo.base_model_id,
        "query_language": zrodlo.query_language,
        "dsl_query": zrodlo.dsl_query,
        "sample_context": "{}",
        "distinct": "on",
        **zmiany,
    }


def test_fd448_raport_ma_odnosniki_do_wszystkich_zrodel_danych(
    admin_client, url_raportu
):
    res = admin_client.get(url_raportu + "?_tzju=True&sortowanie=autorzy")

    assert res.status_code == 200
    assert "Źródła danych tego raportu" in res.content.decode()
    odnosniki = _odnosniki(res)
    elementy = ReportElement.objects.filter(
        parent__slug="raport-autorow", datasource__isnull=False
    ).order_by("position")
    assert len(odnosniki) == elementy.count() > 0
    for odnosnik, element in zip(odnosniki, elementy, strict=True):
        adres = urlsplit(odnosnik.get("href"))
        assert adres.path == reverse(
            "admin:flexible_reports_datasource_change", args=(element.datasource_id,)
        )
        # powrót niesie parametry, z którymi raport był otwarty
        assert parse_qs(adres.query)["powrot"] == [
            url_raportu + "?_tzju=True&sortowanie=autorzy"
        ]
        assert "edytuj źródło danych" in odnosnik.text_content()
        assert element.datasource.label in odnosnik.text_content()


def test_fd448_zapis_zrodla_danych_wraca_do_raportu(admin_client, url_raportu):
    powrot = url_raportu + "?_tzju=True"
    res = admin_client.get(powrot)
    url_edycji = _odnosniki(res)[0].get("href")
    pk = int(urlsplit(url_edycji).path.rstrip("/").split("/")[-2])
    zrodlo = Datasource.objects.get(pk=pk)

    formularz = admin_client.get(url_edycji)
    assert formularz.status_code == 200
    assert "Wróć do raportu" in formularz.content.decode()

    res = admin_client.post(
        url_edycji, _dane_formularza(zrodlo, dsl_query="rok = 1999")
    )

    assert res.status_code == 302, res.content.decode()[:2000]
    assert res.url == powrot
    zrodlo.refresh_from_db()
    assert zrodlo.dsl_query == "rok = 1999"
    # raport generuje się po powrocie (już na nowym zapytaniu)
    assert admin_client.get(res.url).status_code == 200


def test_fd448_zapisz_i_kontynuuj_nie_gubi_powrotu(admin_client, url_raportu):
    zrodlo = Datasource.objects.first()
    url_edycji = (
        reverse("admin:flexible_reports_datasource_change", args=(zrodlo.pk,))
        + f"?powrot={url_raportu}"
    )

    res = admin_client.post(url_edycji, _dane_formularza(zrodlo, _continue="1"))

    assert res.status_code == 302
    adres = urlsplit(res.url)
    assert adres.path == urlsplit(url_edycji).path
    assert parse_qs(adres.query)["powrot"] == [url_raportu]


def test_fd448_strona_bledu_zrodla_danych_ma_odnosniki(admin_client, url_raportu):
    """Najbardziej potrzebne miejsce: raport, który się NIE generuje (FD#523)."""
    zrodlo = Datasource.objects.exclude(dsl_query="").first()
    Datasource.objects.filter(pk=zrodlo.pk).update(
        query_language=DJANGOQL, dsl_query='nie_ma_takiego_pola = "x"'
    )

    for eksport in ("", "?_export=xlsx"):
        res = admin_client.get(url_raportu + eksport)
        assert "Nie udało się wygenerować raportu" in res.content.decode()
        odnosniki = _odnosniki(res)
        assert odnosniki
        # powrót prowadzi do raportu na ekranie, nie do pobierania pliku
        for odnosnik in odnosniki:
            powrot = parse_qs(urlsplit(odnosnik.get("href")).query)["powrot"]
            assert powrot == [url_raportu]


# --- strażnicy: co ma się NIE zmienić ---------------------------------------


def test_fd448_niezalogowany_nie_widzi_odnosnikow(client, url_raportu):
    res = client.get(url_raportu)

    assert res.status_code == 200
    assert not _odnosniki(res)
    assert "Źródła danych tego raportu" not in res.content.decode()


def test_fd448_redaktor_bez_prawa_do_zrodel_danych_nie_widzi_odnosnikow(
    client, normal_django_user, url_raportu
):
    normal_django_user.is_staff = True
    normal_django_user.save()
    client.force_login(normal_django_user)

    res = client.get(url_raportu)

    assert res.status_code == 200
    assert not _odnosniki(res)


def test_fd448_redaktor_z_prawem_zmiany_zrodel_danych_widzi_odnosniki(
    client, normal_django_user, url_raportu
):
    normal_django_user.is_staff = True
    normal_django_user.save()
    normal_django_user.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="flexible_reports", codename="change_datasource"
        )
    )
    client.force_login(normal_django_user)

    assert _odnosniki(client.get(url_raportu))


def test_fd448_bez_parametru_powrotu_formularz_dziala_jak_dotad(
    admin_client, url_raportu
):
    zrodlo = Datasource.objects.first()
    url_edycji = reverse("admin:flexible_reports_datasource_change", args=(zrodlo.pk,))

    assert "Wróć do raportu" not in admin_client.get(url_edycji).content.decode()
    res = admin_client.post(url_edycji, _dane_formularza(zrodlo))

    assert res.status_code == 302
    assert res.url == reverse("admin:flexible_reports_datasource_changelist")


@pytest.mark.parametrize(
    "zly_adres",
    ["https://example.com/przejecie", "//example.com/przejecie", "javascript:alert(1)"],
)
def test_fd448_powrot_poza_serwis_jest_ignorowany(admin_client, url_raportu, zly_adres):
    zrodlo = Datasource.objects.first()
    url_edycji = reverse("admin:flexible_reports_datasource_change", args=(zrodlo.pk,))

    strona = admin_client.get(url_edycji, {"powrot": zly_adres})
    assert "Wróć do raportu" not in strona.content.decode()
    res = admin_client.post(
        url_edycji + f"?powrot={zly_adres}", _dane_formularza(zrodlo)
    )

    assert res.status_code == 302
    assert res.url == reverse("admin:flexible_reports_datasource_changelist")


def test_fd448_blad_walidacji_zapytania_zostawia_w_formularzu(
    admin_client, url_raportu
):
    """Niepoprawne zapytanie nie wraca do raportu — zostaje z komunikatem."""
    zrodlo = Datasource.objects.first()
    url_edycji = (
        reverse("admin:flexible_reports_datasource_change", args=(zrodlo.pk,))
        + f"?powrot={url_raportu}"
    )
    stare = zrodlo.dsl_query

    res = admin_client.post(
        url_edycji, _dane_formularza(zrodlo, dsl_query="nie_ma_takiego_pola = 1")
    )

    assert res.status_code == 200
    assert "Wróć do raportu" in res.content.decode()
    zrodlo.refresh_from_db()
    assert zrodlo.dsl_query == stare


def test_fd448_raport_bez_zrodel_danych_nie_pokazuje_listy(admin_client, url_raportu):
    ReportElement.objects.filter(parent__slug="raport-autorow").delete()
    assert Report.objects.filter(slug="raport-autorow").exists()

    res = admin_client.get(url_raportu)

    assert res.status_code == 200
    assert "Źródła danych tego raportu" not in res.content.decode()


def test_fd448_grupa_raporty_ma_prawo_zmiany_zrodel_danych(db):
    """Odnośniki pokazujemy wg uprawnienia, które niesie grupa „raporty”."""
    grupa = Group.objects.filter(name="raporty").first()
    if grupa is None:
        pytest.skip("grupa „raporty” nie istnieje w bazie testowej")
    assert grupa.permissions.filter(
        content_type__app_label="flexible_reports", codename="change_datasource"
    ).exists()
