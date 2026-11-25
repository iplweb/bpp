"""Okres ewaluacji: domyślny wg roku, wybór w sesji, pasek wyboru okresu."""

import pytest
from django.urls import reverse

from ewaluacja_common.models import OkresEwaluacji
from ewaluacja_common.okres import KLUCZ_SESJI, okres_domyslny


@pytest.mark.django_db
def test_okresy_z_migracji():
    assert [str(o) for o in OkresEwaluacji.objects.all()][:2] == [
        "2022–2025",
        "2026–2030",
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "rok,oczekiwany",
    [
        (2022, "2022–2025"),
        (2025, "2022–2025"),
        (2026, "2026–2030"),
        (2031, "2026–2030"),
    ],
)
def test_okres_domyslny_wg_roku(rok, oczekiwany):
    assert str(okres_domyslny(rok)) == oczekiwany


@pytest.mark.django_db
def test_okres_domyslny_przed_pierwszym_okresem():
    assert str(okres_domyslny(2000)) == "2022–2025"


@pytest.mark.django_db
def test_wybierz_okres_zapisuje_w_sesji(admin_client):
    okres = OkresEwaluacji.objects.get(rok_od=2022)
    resp = admin_client.post(
        reverse("ewaluacja_common:wybierz_okres"),
        {"okres": okres.pk, "next": "/ewaluacja_metryki/"},
    )
    assert resp.status_code == 302
    assert resp["Location"] == "/ewaluacja_metryki/"
    assert admin_client.session[KLUCZ_SESJI] == okres.pk


@pytest.mark.django_db
def test_wybierz_okres_nie_przekierowuje_poza_serwis(admin_client):
    okres = OkresEwaluacji.objects.first()
    resp = admin_client.post(
        reverse("ewaluacja_common:wybierz_okres"),
        {"okres": okres.pk, "next": "https://zly.example.com/"},
    )
    assert resp["Location"] == "/"


@pytest.mark.django_db
def test_wybierz_okres_wymaga_logowania(client):
    okres = OkresEwaluacji.objects.first()
    resp = client.post(reverse("ewaluacja_common:wybierz_okres"), {"okres": okres.pk})
    assert resp.status_code == 302
    assert KLUCZ_SESJI not in client.session


@pytest.mark.django_db
@pytest.mark.parametrize("wartosc", ["", "abc", "999999"])
def test_wybierz_okres_zla_wartosc_404(admin_client, wartosc):
    resp = admin_client.post(
        reverse("ewaluacja_common:wybierz_okres"), {"okres": wartosc}
    )
    assert resp.status_code == 404


@pytest.mark.django_db
def test_post_migrate_zaklada_okresy_gdy_tabela_pusta():
    """Po ``flush`` (TRUNCATE + post_migrate) okresy wracają."""
    from django.apps import apps

    from ewaluacja_common.okres import zasiej_okresy_po_migracji

    OkresEwaluacji.objects.all().delete()
    zasiej_okresy_po_migracji(apps.get_app_config("ewaluacja_common"))
    assert [str(o) for o in OkresEwaluacji.objects.all()] == [
        "2022–2025",
        "2026–2030",
    ]


@pytest.mark.django_db
def test_post_migrate_nie_rusza_niepustej_tabeli():
    from django.apps import apps

    from ewaluacja_common.okres import zasiej_okresy_po_migracji

    OkresEwaluacji.objects.all().delete()
    OkresEwaluacji.objects.create(rok_od=2026, rok_do=2029)
    zasiej_okresy_po_migracji(apps.get_app_config("ewaluacja_common"))
    assert [str(o) for o in OkresEwaluacji.objects.all()] == ["2026–2029"]


@pytest.mark.django_db(transaction=True)
def test_okresy_przezywaja_flush_testu_transakcyjnego():
    """Test transakcyjny przed nami zrobił flush — okresy muszą być."""
    assert OkresEwaluacji.objects.filter(rok_od=2022).exists()


@pytest.mark.django_db
def test_wybor_okresu_zapamietany_po_ponownym_zalogowaniu(client, admin_user):
    """Ostatnio wybrany okres jest domyślnym także w NOWEJ sesji."""
    from ewaluacja_common.models import WybranyOkresEwaluacji

    stary = OkresEwaluacji.objects.get(rok_od=2022)
    client.force_login(admin_user)
    client.post(reverse("ewaluacja_common:wybierz_okres"), {"okres": stary.pk})
    assert WybranyOkresEwaluacji.objects.get(user=admin_user).okres == stary

    client.logout()
    client.force_login(admin_user)
    assert KLUCZ_SESJI not in client.session
    resp = client.get(reverse("ewaluacja_metryki:lista"))
    assert resp.context["okres_ewaluacji"] == stary
    # ...i przechodząc po kolejnych stronach dalej ten sam:
    resp = client.get(reverse("ewaluacja_dwudyscyplinowcy:index"))
    assert resp.context["okres_ewaluacji"] == stary


@pytest.mark.django_db
def test_zmiana_wyboru_nadpisuje_zapamietany(admin_client, admin_user):
    from ewaluacja_common.models import WybranyOkresEwaluacji

    for rok_od in (2022, 2026):
        admin_client.post(
            reverse("ewaluacja_common:wybierz_okres"),
            {"okres": OkresEwaluacji.objects.get(rok_od=rok_od).pk},
        )
    assert WybranyOkresEwaluacji.objects.get(user=admin_user).okres.rok_od == 2026
    assert WybranyOkresEwaluacji.objects.count() == 1


@pytest.mark.django_db
def test_bez_wyboru_okres_domyslny(admin_client):
    resp = admin_client.get(reverse("ewaluacja_metryki:lista"))
    assert resp.context["okres_ewaluacji"] == okres_domyslny()


@pytest.mark.django_db
def test_admin_okresow_tylko_do_odczytu(admin_client):
    okres = OkresEwaluacji.objects.first()
    base = "admin:ewaluacja_common_okresewaluacji_"
    assert admin_client.get(reverse(base + "changelist")).status_code == 200
    assert admin_client.get(reverse(base + "add")).status_code == 403
    assert (
        admin_client.get(reverse(base + "delete", args=[okres.pk])).status_code == 403
    )
    # Widok zmiany dla superusera bez prawa zmiany = podgląd, POST nic nie zmienia.
    admin_client.post(
        reverse(base + "change", args=[okres.pk]),
        {"rok_od": okres.rok_od, "rok_do": 2099, "uwagi": "x"},
    )
    okres.refresh_from_db()
    assert okres.rok_do != 2099


@pytest.mark.django_db
def test_pasek_okresu_pod_breadcrumbs_a_nie_w_gornej_belce(admin_client):
    """Wybór okresu to pasek na całą szerokość pod breadcrumbs, nie pozycja
    menu górnej belki; okresy to linki do tej samej strony w innym okresie."""
    resp = admin_client.get("/ewaluacja_metryki/2022-2025/")
    html = resp.content.decode()
    assert html.count('class="pasek-okresu"') == 1
    assert html.index('id="breadcrumbs-wrapper"') < html.index('class="pasek-okresu"')
    assert "wybor-okresu" not in html
    assert 'href="/ewaluacja_metryki/2026-2030/"' in html
    assert 'aria-current="page"' in html


@pytest.mark.django_db
def test_pasek_okresu_tylko_na_stronach_ewaluacji(admin_client):
    resp = admin_client.get("/")
    assert 'class="pasek-okresu"' not in resp.content.decode()


@pytest.mark.django_db
def test_okres_z_adresu_url(admin_client, uczelnia):
    """Okres w ścieżce wybiera okres strony i zostaje zapamiętany."""
    resp = admin_client.get("/ewaluacja_liczba_n/2026-2030/")
    assert resp.status_code == 200
    assert str(resp.context["okres_ewaluacji"]) == "2026–2030"
    # zapamiętany: strona bez okresu w adresie bierze ostatni z adresu
    resp = admin_client.get(reverse("ewaluacja_metryki:lista"))
    assert str(resp.context["okres_ewaluacji"]) == "2026–2030"


@pytest.mark.django_db
def test_linki_na_stronie_z_okresem_maja_okres(admin_client, uczelnia):
    """{% url %} na stronie z okresem w adresie daje linki z tym okresem —
    nawigacja nie gubi okresu, a strony innych aplikacji bez zmian."""
    html = admin_client.get("/ewaluacja_liczba_n/2022-2025/").content.decode()
    assert "/ewaluacja_liczba_n/2022-2025/" in html
    assert 'href="/ewaluacja_liczba_n/"' not in html


@pytest.mark.django_db
def test_nieznany_okres_w_adresie_404(admin_client):
    assert admin_client.get("/ewaluacja_liczba_n/2010-2013/").status_code == 404


@pytest.mark.django_db
def test_nawigacja_bez_okresu_przekierowuje_na_adres_z_okresem(admin_client):
    """Wejście z menu (nawigacja przeglądarki) na stronę z paskiem okresu →
    adres z okresem, żeby można go było skopiować i wysłać."""
    resp = admin_client.get(
        "/ewaluacja_metryki/?widok=tabela", HTTP_SEC_FETCH_MODE="navigate"
    )
    assert resp.status_code == 302
    slug = okres_domyslny().slug
    assert resp["Location"] == f"/ewaluacja_metryki/{slug}/?widok=tabela"


@pytest.mark.django_db
def test_htmx_bez_okresu_nie_przekierowuje(admin_client):
    resp = admin_client.get(
        reverse("ewaluacja_metryki:lista"),
        HTTP_SEC_FETCH_MODE="cors",
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200


@pytest.mark.django_db
def test_okres_z_adresu_wygrywa_z_sesja(admin_client):
    """Wyścig z odpytywaniem statusu: sesja ma stary okres, ale adres mówi
    co innego — liczy się adres."""
    stary = OkresEwaluacji.objects.get(rok_od=2022)
    session = admin_client.session
    session[KLUCZ_SESJI] = stary.pk
    session.save()
    resp = admin_client.get("/ewaluacja_metryki/2026-2030/")
    assert str(resp.context["okres_ewaluacji"]) == "2026–2030"


def _link_paska(html, slug):
    """Adres (``href``) linku paska okresu prowadzącego do okresu ``slug``."""
    import html as html_lib
    import re

    pasek = html[html.index('class="pasek-okresu"') :]
    pasek = pasek[: pasek.index("</nav>")]
    for adres in re.findall(r'<a href="([^"]*)"', pasek):
        if f"/{slug}/" in adres:
            return html_lib.unescape(adres)
    raise AssertionError(f"brak linku paska do okresu {slug}")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "adres,lata,reszta",
    [
        (
            "/komparator-zrodel-pbn/2022-2025/",
            {"rok_od": "2023", "rok_do": "2024"},
            {"search": "Acta", "tylko_rozbieznosci": "on"},
        ),
        (
            "/komparator-pbn-udzialy/2022-2025/",
            {"rok_min": "2023", "rok_max": "2024"},
            {"search": "Kowalski", "filter": "bpp_empty"},
        ),
        (
            "/komparator-publikacji-pbn/2022-2025/",
            {"year_min": "2023", "year_max": "2024"},
            {"q": "energia", "type": "ciagle", "fields": "title"},
        ),
    ],
)
def test_pasek_gubi_recznie_wpisane_lata_reszta_parametrow_zostaje(
    admin_client, adres, lata, reszta
):
    """FD#514: przełączenie okresu na pasku nie niesie ręcznie wpisanych lat
    (inaczej pasek pokazywałby inny okres niż dane); inne filtry zostają."""
    from django.http import QueryDict

    html = admin_client.get(adres, {**lata, **reszta}).content.decode()

    link = _link_paska(html, "2026-2030")
    sciezka, _, zapytanie = link.partition("?")
    assert sciezka == adres.replace("2022-2025", "2026-2030")
    assert QueryDict(zapytanie).dict() == reszta


@pytest.mark.django_db
@pytest.mark.parametrize(
    "adres,lata,klucze",
    [
        (
            "/komparator-zrodel-pbn/2022-2025/",
            {"rok_od": "2023", "rok_do": "2024", "search": "x"},
            ("rok_od", "rok_do"),
        ),
        (
            "/komparator-pbn-udzialy/2022-2025/",
            {"rok_min": "2023", "rok_max": "2024", "search": "x"},
            ("rok_min", "rok_max"),
        ),
        (
            "/komparator-publikacji-pbn/2022-2025/",
            {"year_min": "2023", "year_max": "2024", "q": "x"},
            ("year_min", "year_max"),
        ),
    ],
)
def test_po_przelaczeniu_okresu_komparator_pokazuje_lata_nowego_okresu(
    admin_client, adres, lata, klucze
):
    """Klik w drugi okres na pasku: pola „Rok od/do” = lata nowego okresu."""
    html = admin_client.get(adres, lata).content.decode()

    resp = admin_client.get(_link_paska(html, "2026-2030"))

    assert resp.status_code == 200
    assert [int(resp.context[k]) for k in klucze] == [2026, 2030]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "adres",
    [
        "/ewaluacja_liczba_n/2022-2025/?rok=2023&rok_od=2023&rok_min=1&year_min=2",
        "/ewaluacja_metryki/2022-2025/?widok=tabela&rok_od=2023&sort=-nazwisko",
        "/komparator_pbn/2022-2025/?rok_od=2023&x=1",
    ],
)
def test_pasek_na_pozostalych_stronach_nie_rusza_parametrow(
    admin_client, uczelnia, adres
):
    """Strażnik: na stronach ewaluacji i w komparatorze PBN (bez pól lat)
    pasek przenosi cały query string bez zmian."""
    html = admin_client.get(adres).content.decode()

    assert _link_paska(html, "2026-2030") == adres.replace("2022-2025", "2026-2030")


@pytest.mark.django_db
def test_przekierowanie_na_adres_z_okresem_zachowuje_lata(admin_client):
    """Strażnik: link z ręcznym zakresem lat bez okresu w adresie (np.
    z komparatora PBN do „Problemów PBN”) nie gubi lat przy przekierowaniu."""
    resp = admin_client.get(
        "/komparator-pbn-udzialy/?rok_min=2023&rok_max=2024",
        HTTP_SEC_FETCH_MODE="navigate",
    )

    slug = okres_domyslny().slug
    assert resp["Location"] == (
        f"/komparator-pbn-udzialy/{slug}/?rok_min=2023&rok_max=2024"
    )
