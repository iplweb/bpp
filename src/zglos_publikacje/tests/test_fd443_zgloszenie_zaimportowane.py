"""FD#443 — domknięcie pętli zgłoszenie publikacji ↔ importer prac.

Zakres tego pliku (spec §10, grupy „Prezentacja" oraz część „Wiązanie —
ścieżka A" dotycząca URL-a przycisku):

* ``importer_url`` — kontekst zgłoszenia (``zgloszenie=<pk>``) w adresie
  przycisku „Użyj importera" oraz brak przycisku dla zgłoszeń już
  zaimportowanych (ochrona przed podwójnym importem, §7);
* filtr „Do obsługi / Załatwione / Wszystkie" (§9);
* panel audytu „📥 Zaimportowane …" na stronie zgłoszenia (§8);
* nowy status ``ZAIMPORTOWANY = 6`` i ``czy_zaimportowane`` (§4.1).
"""

import re
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib import admin as django_admin
from django.urls import reverse
from django.utils import timezone
from django.utils.dateformat import format as format_date
from model_bakery import baker

from zglos_publikacje.admin.filters import StanObslugiFilter
from zglos_publikacje.models import Zgloszenie_Publikacji

Statusy = Zgloszenie_Publikacji.Statusy


def _admin():
    """Zarejestrowana instancja ``ModelAdmin`` dla zgłoszeń."""
    return django_admin.site._registry[Zgloszenie_Publikacji]


def _params(importer_url):
    """Rozbierz query string adresu importera na słownik list."""
    assert importer_url is not None
    return parse_qs(urlparse(importer_url).query)


def _change_html(admin_client, zgloszenie):
    response = admin_client.get(
        reverse(
            "admin:zglos_publikacje_zgloszenie_publikacji_change",
            args=[zgloszenie.pk],
        )
    )
    assert response.status_code == 200
    return response.content.decode()


def _object_tools_fragment(html):
    """Zawartość paska akcji ``<ul class="…object-tools">…</ul>``."""
    match = re.search(
        r'<ul class="[^"]*object-tools">(.*?)</ul>', html, flags=re.DOTALL
    )
    assert match, "Brak paska object-tools na stronie edycji"
    return match.group(1)


# --------------------------------------------------------------------------
# Model: nowy status i ``czy_zaimportowane``
# --------------------------------------------------------------------------


def test_fd443_status_zaimportowany_ma_wartosc_6():
    assert Statusy.ZAIMPORTOWANY == 6


def test_fd443_wartosc_6_nie_koliduje_z_istniejacymi_statusami():
    """Wartość 6 była wolna (poprzednio ``Statusy`` kończyło się na SPAM=5)."""
    wartosci = [s.value for s in Statusy]
    assert len(wartosci) == len(set(wartosci)), "Zdublowane wartości w Statusy"

    o_wartosci_6 = [s for s in Statusy if s.value == 6]
    assert o_wartosci_6 == [Statusy.ZAIMPORTOWANY]

    # Stare wartości nie zmieniły znaczenia (dane produkcyjne trzymają liczby).
    assert Statusy.NOWY == 0
    assert Statusy.ZAAKCEPTOWANY == 1
    assert Statusy.WYMAGA_ZMIAN == 2
    assert Statusy.PO_ZMIANACH == 3
    assert Statusy.ODRZUCONO == 4
    assert Statusy.SPAM == 5


@pytest.mark.parametrize("status", list(Statusy))
def test_fd443_czy_zaimportowane_tylko_dla_statusu_6(status):
    zgloszenie = Zgloszenie_Publikacji(status=status)
    assert zgloszenie.czy_zaimportowane == (status == Statusy.ZAIMPORTOWANY)


# --------------------------------------------------------------------------
# Ścieżka A — URL przycisku „Użyj importera"
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_fd443_importer_url_z_doi_niesie_kontekst_zgloszenia():
    zgloszenie = baker.make(
        Zgloszenie_Publikacji,
        tytul_oryginalny="Praca z DOI",
        strona_www="https://doi.org/10.1234/abc.def",
    )

    params = _params(_admin().importer_url(zgloszenie))

    assert params["zgloszenie"] == [str(zgloszenie.pk)]
    assert params["provider"] == ["CrossRef"]
    assert params["identifier"] == ["10.1234/abc.def"]


@pytest.mark.django_db
def test_fd443_importer_url_z_pola_doi_niesie_kontekst_zgloszenia():
    """DOI bywa w polu ``doi``, nie w ``strona_www`` — kontekst też ma być."""
    zgloszenie = baker.make(
        Zgloszenie_Publikacji,
        tytul_oryginalny="Praca z DOI w polu doi",
        strona_www="",
        doi="10.5555/xyz.987",
    )

    params = _params(_admin().importer_url(zgloszenie))

    assert params["zgloszenie"] == [str(zgloszenie.pk)]
    assert params["provider"] == ["CrossRef"]
    assert params["identifier"] == ["10.5555/xyz.987"]


@pytest.mark.django_db
def test_fd443_importer_url_bez_doi_ze_strona_www_niesie_kontekst_zgloszenia():
    zgloszenie = baker.make(
        Zgloszenie_Publikacji,
        tytul_oryginalny="Praca bez DOI, ze stroną WWW",
        strona_www="https://example.com/papers/123",
    )

    params = _params(_admin().importer_url(zgloszenie))

    assert params["zgloszenie"] == [str(zgloszenie.pk)]
    assert params["provider"] == ["Pozostałe strony WWW"]
    assert params["identifier"] == ["https://example.com/papers/123"]


@pytest.mark.django_db
def test_fd443_importer_url_bez_doi_i_bez_strony_www_to_none():
    zgloszenie = baker.make(
        Zgloszenie_Publikacji,
        tytul_oryginalny="Praca bez adresu",
        strona_www="",
    )

    assert _admin().importer_url(zgloszenie) is None


@pytest.mark.django_db
def test_fd443_importer_url_dla_zaimportowanego_to_none_mimo_doi():
    """Ochrona przed podwójnym importem (§7): przycisk znika, choć DOI jest."""
    zgloszenie = baker.make(
        Zgloszenie_Publikacji,
        tytul_oryginalny="Praca już zaimportowana",
        strona_www="https://doi.org/10.1234/abc.def",
        doi="10.1234/abc.def",
        status=Statusy.ZAIMPORTOWANY,
    )

    assert _admin().importer_url(zgloszenie) is None


@pytest.mark.django_db
def test_fd443_importer_url_dla_zaimportowanego_ze_strona_www_to_none():
    zgloszenie = baker.make(
        Zgloszenie_Publikacji,
        tytul_oryginalny="Praca już zaimportowana, bez DOI",
        strona_www="https://example.com/papers/123",
        status=Statusy.ZAIMPORTOWANY,
    )

    assert _admin().importer_url(zgloszenie) is None


# --------------------------------------------------------------------------
# Filtr „Do obsługi / Załatwione / Wszystkie"
# --------------------------------------------------------------------------


def _zgloszenia_wszystkich_statusow():
    return {
        status: baker.make(
            Zgloszenie_Publikacji,
            tytul_oryginalny=f"Zgłoszenie o statusie {status.label}",
            status=status,
        )
        for status in Statusy
    }


def _statusy_po_filtrze(rf, wartosc):
    """Statusy widoczne po zastosowaniu filtra o zadanej wartości."""
    if wartosc is None:
        request = rf.get("/")
        params = {}
    else:
        request = rf.get("/", {StanObslugiFilter.parameter_name: wartosc})
        params = {StanObslugiFilter.parameter_name: [wartosc]}

    filtr = StanObslugiFilter(request, params, Zgloszenie_Publikacji, _admin())
    qs = filtr.queryset(request, Zgloszenie_Publikacji.objects.all())
    return set(qs.values_list("status", flat=True))


@pytest.mark.django_db
def test_fd443_filtr_stan_obslugi_ma_trzy_pozycje(rf):
    request = rf.get("/")
    filtr = StanObslugiFilter(request, {}, Zgloszenie_Publikacji, _admin())

    assert filtr.lookup_choices == [
        ("do_obslugi", "Do obsługi"),
        ("zalatwione", "Załatwione"),
        ("wszystkie", "Wszystkie"),
    ]


@pytest.mark.django_db
def test_fd443_filtr_stan_obslugi_domyslnie_tylko_do_obslugi(rf):
    _zgloszenia_wszystkich_statusow()

    assert _statusy_po_filtrze(rf, None) == {Statusy.NOWY, Statusy.PO_ZMIANACH}


@pytest.mark.django_db
def test_fd443_filtr_stan_obslugi_do_obslugi_jawnie(rf):
    _zgloszenia_wszystkich_statusow()

    assert _statusy_po_filtrze(rf, StanObslugiFilter.DO_OBSLUGI) == {
        Statusy.NOWY,
        Statusy.PO_ZMIANACH,
    }


@pytest.mark.django_db
def test_fd443_filtr_stan_obslugi_zalatwione(rf):
    _zgloszenia_wszystkich_statusow()

    assert _statusy_po_filtrze(rf, StanObslugiFilter.ZALATWIONE) == {
        Statusy.ZAIMPORTOWANY,
        Statusy.ZAAKCEPTOWANY,
        Statusy.ODRZUCONO,
        Statusy.SPAM,
    }


@pytest.mark.django_db
def test_fd443_filtr_stan_obslugi_wszystkie(rf):
    _zgloszenia_wszystkich_statusow()

    assert _statusy_po_filtrze(rf, StanObslugiFilter.WSZYSTKIE) == {
        status.value for status in Statusy
    }


@pytest.mark.django_db
def test_fd443_filtr_stan_obslugi_domyslnie_zaznacza_do_obslugi(rf):
    """Brak parametru w URL-u = zaznaczona pozycja „Do obsługi"."""

    class _Changelist:
        def get_query_string(self, params):
            return "?" + "&".join(f"{k}={v}" for k, v in params.items())

    request = rf.get("/")
    filtr = StanObslugiFilter(request, {}, Zgloszenie_Publikacji, _admin())

    zaznaczone = [c["display"] for c in filtr.choices(_Changelist()) if c["selected"]]
    assert zaznaczone == ["Do obsługi"]


@pytest.mark.django_db
def test_fd443_filtr_stan_obslugi_dziala_na_liscie_w_adminie(admin_client):
    """Domyślna lista w adminie nie pokazuje zgłoszeń załatwionych."""
    zgloszenia = _zgloszenia_wszystkich_statusow()
    url = reverse("admin:zglos_publikacje_zgloszenie_publikacji_changelist")

    response = admin_client.get(url)
    assert response.status_code == 200
    widoczne = {obj.pk for obj in response.context["cl"].result_list}
    assert widoczne == {
        zgloszenia[Statusy.NOWY].pk,
        zgloszenia[Statusy.PO_ZMIANACH].pk,
    }

    response = admin_client.get(
        url, {StanObslugiFilter.parameter_name: StanObslugiFilter.ZALATWIONE}
    )
    assert response.status_code == 200
    widoczne = {obj.pk for obj in response.context["cl"].result_list}
    assert widoczne == {
        zgloszenia[Statusy.ZAIMPORTOWANY].pk,
        zgloszenia[Statusy.ZAAKCEPTOWANY].pk,
        zgloszenia[Statusy.ODRZUCONO].pk,
        zgloszenia[Statusy.SPAM].pk,
    }

    response = admin_client.get(
        url, {StanObslugiFilter.parameter_name: StanObslugiFilter.WSZYSTKIE}
    )
    assert response.status_code == 200
    widoczne = {obj.pk for obj in response.context["cl"].result_list}
    assert widoczne == {z.pk for z in zgloszenia.values()}


# --------------------------------------------------------------------------
# Panel audytu na formularzu zgłoszenia
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_fd443_panel_audytu_pokazuje_date_uzytkownika_i_link_do_rekordu(
    admin_client, wydawnictwo_ciagle
):
    operator = baker.make("bpp.BppUser", username="operator_fd443")
    kiedy = timezone.now()

    zgloszenie = baker.make(
        Zgloszenie_Publikacji,
        tytul_oryginalny="Praca domknięta importerem",
        strona_www="https://doi.org/10.1234/abc.def",
        status=Statusy.ZAIMPORTOWANY,
        zaimportowano=kiedy,
        zaimportowal=operator,
    )
    zgloszenie.odpowiednik_w_bpp = wydawnictwo_ciagle
    zgloszenie.save()

    html = _change_html(admin_client, zgloszenie)

    assert 'id="panel-zgloszenie-zaimportowane"' in html
    assert "Zaimportowane" in html

    oczekiwana_data = format_date(timezone.localtime(kiedy), "d.m.Y H:i")
    assert oczekiwana_data in html

    assert "operator_fd443" in html

    url_rekordu = reverse(
        "admin:bpp_wydawnictwo_ciagle_change", args=[wydawnictwo_ciagle.pk]
    )
    assert url_rekordu in html
    assert str(wydawnictwo_ciagle) in html


@pytest.mark.django_db
def test_fd443_zaimportowane_nie_pokazuje_przycisku_uzyj_importera(
    admin_client,
):
    """Ochrona przed podwójnym importem — przycisku nie ma w HTML-u (§7)."""
    zgloszenie = baker.make(
        Zgloszenie_Publikacji,
        tytul_oryginalny="Praca już zaimportowana",
        strona_www="https://doi.org/10.1234/abc.def",
        status=Statusy.ZAIMPORTOWANY,
        zaimportowano=timezone.now(),
    )

    html = _change_html(admin_client, zgloszenie)

    assert "Użyj importera" not in html
    # Przy okazji: gate statusowy chowa też pozostałe przyciski akcji.
    tools = _object_tools_fragment(html)
    assert "Zwróć do autora" not in tools
    assert "Dodaj wyd." not in tools


@pytest.mark.django_db
def test_fd443_niezaimportowane_bez_panelu_ale_z_przyciskiem_importera(
    admin_client,
):
    zgloszenie = baker.make(
        Zgloszenie_Publikacji,
        tytul_oryginalny="Praca do zaimportowania",
        strona_www="https://doi.org/10.1234/abc.def",
        status=Statusy.NOWY,
    )

    html = _change_html(admin_client, zgloszenie)

    assert 'id="panel-zgloszenie-zaimportowane"' not in html
    assert "Zaimportowane" not in html

    tools = _object_tools_fragment(html)
    assert "Użyj importera" in tools
    assert f"zgloszenie={zgloszenie.pk}" in tools
