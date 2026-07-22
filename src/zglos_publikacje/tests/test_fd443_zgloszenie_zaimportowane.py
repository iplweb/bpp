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

import logging
import re
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib import admin as django_admin
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone
from django.utils.dateformat import format as format_date
from model_bakery import baker

from importer_publikacji.models import ImportSession
from zglos_publikacje.admin.filters import StanObslugiFilter
from zglos_publikacje.models import (
    Zgloszenie_Publikacji,
    Zgloszenie_Publikacji_Zalacznik,
)

Statusy = Zgloszenie_Publikacji.Statusy

CHANGELIST = "admin:zglos_publikacje_zgloszenie_publikacji_changelist"

#: Logger, na który admin zgłoszeń wypuszcza połknięte wyjątki.
LOGGER_ADMINA = "zglos_publikacje.admin.zgloszenie_publikacji"


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


def _panel_fragment(html):
    """Zawartość panelu „📥 Zaimportowane …" nad formularzem (FD#443, §8)."""
    match = re.search(
        r'<div[^>]*id="panel-zgloszenie-zaimportowane"[^>]*>(.*?)</div>',
        html,
        flags=re.DOTALL,
    )
    assert match, "Brak panelu id=panel-zgloszenie-zaimportowane na stronie edycji"
    return match.group(1)


def _changelist(admin_client, **params):
    response = admin_client.get(reverse(CHANGELIST), params)
    assert response.status_code == 200
    return response


def _spec(response, warunek, opis):
    """Pojedynczy ``FieldListFilter`` changelisty spełniający ``warunek``."""
    znalezione = [spec for spec in response.context["cl"].filter_specs if warunek(spec)]
    assert len(znalezione) == 1, f"Oczekiwano dokładnie jednego filtra: {opis}"
    return znalezione[0]


def _spec_stanu_obslugi(response):
    return _spec(
        response,
        lambda spec: isinstance(spec, StanObslugiFilter),
        "StanObslugiFilter",
    )


def _spec_statusu(response):
    return _spec(
        response,
        lambda spec: getattr(spec, "field_path", None) == "status",
        "filtr po polu „status”",
    )


def _spec_zaimportowal(response):
    return _spec(
        response,
        lambda spec: getattr(spec, "field_path", None) == "zaimportowal",
        "filtr po polu „zaimportował”",
    )


def _zaznaczone(spec, changelist):
    """Etykiety pozycji filtra oznaczonych w interfejsie jako wybrane."""
    return [wybor["display"] for wybor in spec.choices(changelist) if wybor["selected"]]


def _sesja_importu(zgloszenie, **kwargs):
    """Realna ``ImportSession`` związana ze zgłoszeniem (FD#443, ścieżka A)."""
    kwargs.setdefault("identifier", "10.1234/abc.def")
    return baker.make(
        ImportSession,
        zgloszenie=zgloszenie,
        provider_name="CrossRef",
        raw_data={},
        normalized_data={},
        **kwargs,
    )


def _zaimportowane_zgloszenie(**kwargs):
    kwargs.setdefault("tytul_oryginalny", "Praca domknięta importerem")
    kwargs.setdefault("zaimportowano", timezone.now())
    return baker.make(
        Zgloszenie_Publikacji,
        status=Statusy.ZAIMPORTOWANY,
        **kwargs,
    )


def _zgloszenia_wszystkich_statusow(**kwargs):
    """Po jednym zgłoszeniu w każdym statusie, indeksowane statusem."""
    return {
        status: baker.make(
            Zgloszenie_Publikacji,
            tytul_oryginalny=f"Zgłoszenie o statusie {status.label}",
            status=status,
            **kwargs,
        )
        for status in Statusy
    }


# --------------------------------------------------------------------------
# Model: nowy status i ``czy_zaimportowane``
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_fd443_status_zaimportowany_zapisuje_w_bazie_wartosc_6():
    """Liczba, nie nazwa, jedzie do bazy — a dane produkcyjne trzymają liczby.

    Test asertuje na wartości ODCZYTANEJ Z BAZY (nie na literale enuma), więc
    broni zgodności kolumny ``status`` między kodem a istniejącymi wierszami.
    """
    zgloszenie = _zaimportowane_zgloszenie()

    z_bazy = Zgloszenie_Publikacji.objects.filter(pk=zgloszenie.pk)
    assert list(z_bazy.values_list("status", flat=True)) == [6]
    assert z_bazy.get().czy_zaimportowane is True


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


@pytest.mark.django_db
def test_fd443_czy_zaimportowane_zgadza_sie_z_gate_em_przycisku_importera():
    """Dokładnie jeden status znaczy „domknięte importerem" — i ten sam status
    (i tylko on) chowa przycisk „Użyj importera".

    Cross-check dwóch niezależnych implementacji tej samej reguły
    (``Zgloszenie_Publikacji.czy_zaimportowane`` vs gate w ``importer_url``),
    zamiast powtarzania literału ``status == 6`` po stronie testu.
    """
    zgloszenia = _zgloszenia_wszystkich_statusow(
        strona_www="https://doi.org/10.1234/abc.def"
    )
    z_bazy = {
        status: Zgloszenie_Publikacji.objects.get(pk=zgloszenie.pk)
        for status, zgloszenie in zgloszenia.items()
    }

    zaimportowane = {status for status, obj in z_bazy.items() if obj.czy_zaimportowane}
    assert len(zaimportowane) == 1

    bez_przycisku = {
        status for status, obj in z_bazy.items() if _admin().importer_url(obj) is None
    }
    assert bez_przycisku == zaimportowane


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


#: Zgłoszenia „w toku" — te, które operator ma na biurku. ``WYMAGA_ZMIAN``
#: należy do tej grupy: praca siedzi wprawdzie u autora, ale to nadal sprawa
#: otwarta (trzeba przypomnieć, po czasie odrzucić). Wyrzucenie jej poza obie
#: grupy chowało takie zgłoszenia wszędzie poza „Wszystkie".
STATUSY_DO_OBSLUGI = {
    Statusy.NOWY,
    Statusy.WYMAGA_ZMIAN,
    Statusy.PO_ZMIANACH,
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

    assert _statusy_po_filtrze(rf, None) == STATUSY_DO_OBSLUGI


@pytest.mark.django_db
def test_fd443_filtr_stan_obslugi_do_obslugi_jawnie(rf):
    _zgloszenia_wszystkich_statusow()

    assert _statusy_po_filtrze(rf, StanObslugiFilter.DO_OBSLUGI) == STATUSY_DO_OBSLUGI


@pytest.mark.django_db
def test_fd443_filtr_stan_obslugi_grupy_dziela_statusy_bez_reszty(rf):
    """Każdy status należy do dokładnie jednej grupy — żaden nie wypada poza.

    To jest test, który złapałby regres widoczności: gdy status nie należy do
    żadnej grupy, zgłoszenia w nim znikają wszędzie poza „Wszystkie".
    """
    _zgloszenia_wszystkich_statusow()

    do_obslugi = _statusy_po_filtrze(rf, StanObslugiFilter.DO_OBSLUGI)
    zalatwione = _statusy_po_filtrze(rf, StanObslugiFilter.ZALATWIONE)
    wszystkie = _statusy_po_filtrze(rf, StanObslugiFilter.WSZYSTKIE)

    assert do_obslugi & zalatwione == set()
    assert do_obslugi | zalatwione == wszystkie == {status.value for status in Statusy}


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

    response = _changelist(admin_client)
    widoczne = {obj.pk for obj in response.context["cl"].result_list}
    assert widoczne == {zgloszenia[status].pk for status in STATUSY_DO_OBSLUGI}

    response = _changelist(
        admin_client,
        **{StanObslugiFilter.parameter_name: StanObslugiFilter.ZALATWIONE},
    )
    widoczne = {obj.pk for obj in response.context["cl"].result_list}
    assert widoczne == {
        zgloszenia[Statusy.ZAIMPORTOWANY].pk,
        zgloszenia[Statusy.ZAAKCEPTOWANY].pk,
        zgloszenia[Statusy.ODRZUCONO].pk,
        zgloszenia[Statusy.SPAM].pk,
    }

    response = _changelist(
        admin_client,
        **{StanObslugiFilter.parameter_name: StanObslugiFilter.WSZYSTKIE},
    )
    widoczne = {obj.pk for obj in response.context["cl"].result_list}
    assert widoczne == {z.pk for z in zgloszenia.values()}


# --------------------------------------------------------------------------
# Konflikt „stan obsługi" × „status" — dane nieosiągalne z interfejsu
# --------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("status", list(Statusy), ids=lambda s: s.name)
def test_fd443_wybor_statusu_na_liscie_pokazuje_zgloszenie_w_tym_statusie(
    admin_client, status
):
    """Kliknięcie „status → X" w sidebarze MUSI pokazać zgłoszenia w statusie X.

    Regres: ``StanObslugiFilter`` przy braku własnego parametru dokładał twarde
    ``status__in=(…)``, które składało się koniunkcją z sąsiednim filtrem
    „status". Kliknięcie „spam" / „odrzucono" / „zaimportowany" dawało pustą
    listę bez żadnego wyjaśnienia — dane były nieosiągalne z interfejsu.
    """
    zgloszenia = _zgloszenia_wszystkich_statusow()

    response = _changelist(admin_client, status__exact=status.value)

    widoczne = {obj.pk for obj in response.context["cl"].result_list}
    assert widoczne == {zgloszenia[status].pk}


@pytest.mark.django_db
def test_fd443_wybor_statusu_nie_zaznacza_stanu_obslugi(admin_client):
    """Skoro „Do obsługi" nie zawęża listy, to nie może być podświetlone.

    Inaczej interfejs kłamie o tym, co realnie ogranicza wyniki.
    """
    _zgloszenia_wszystkich_statusow()

    response = _changelist(admin_client, status__exact=Statusy.SPAM.value)
    changelist = response.context["cl"]

    assert _zaznaczone(_spec_stanu_obslugi(response), changelist) == []


@pytest.mark.django_db
def test_fd443_jawny_stan_obslugi_i_status_daja_koniunkcje(admin_client):
    """Gdy OBA filtry wybrano ręcznie, zawężenia się składają — i widać to.

    Pusty wynik jest wtedy wyjaśniony: w sidebarze świecą obie wybrane
    pozycje, więc operator widzi, dlaczego nic nie ma.
    """
    _zgloszenia_wszystkich_statusow()

    response = _changelist(
        admin_client,
        **{
            StanObslugiFilter.parameter_name: StanObslugiFilter.DO_OBSLUGI,
            "status__exact": Statusy.SPAM.value,
        },
    )
    changelist = response.context["cl"]

    assert list(changelist.result_list) == []
    assert _zaznaczone(_spec_stanu_obslugi(response), changelist) == ["Do obsługi"]
    assert _zaznaczone(_spec_statusu(response), changelist) == [Statusy.SPAM.label]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "parametr", ["status", "status__exact", "status__in", "status__gte"]
)
def test_fd443_kazdy_lookup_statusu_wylacza_domyslne_zawezenie(rf, parametr):
    """Detekcja obejmuje ``status`` ORAZ ``status__<lookup>``, nie tylko
    ``status__exact`` (DjangoQL i ręcznie sklejane adresy używają innych)."""
    _zgloszenia_wszystkich_statusow()

    request = rf.get("/", {parametr: str(Statusy.WYMAGA_ZMIAN.value)})
    filtr = StanObslugiFilter(request, {}, Zgloszenie_Publikacji, _admin())

    assert filtr.czy_domyslne_zawezenie() is False

    qs = filtr.queryset(request, Zgloszenie_Publikacji.objects.all())
    assert set(qs.values_list("status", flat=True)) == {
        status.value for status in Statusy
    }


@pytest.mark.django_db
def test_fd443_zapytanie_djangoql_wylacza_domyslne_zawezenie(rf):
    """Zapytanie DjangoQL ląduje w ``q``, poza detekcją po polu ``status``.

    Bez tego ``status = 5`` wpisane w DjangoQL wpadało w koniunkcję
    z domyślnym ``status__in=(0, 2, 3)`` i ZAWSZE zwracało pustą listę —
    operator szukający spamu dostawał zero wyników bez wyjaśnienia.
    """
    _zgloszenia_wszystkich_statusow()

    request = rf.get("/", {"q": f"status = {Statusy.SPAM.value}", "q-l": "on"})
    filtr = StanObslugiFilter(request, {}, Zgloszenie_Publikacji, _admin())

    assert filtr.czy_domyslne_zawezenie() is False

    qs = filtr.queryset(request, Zgloszenie_Publikacji.objects.all())
    assert set(qs.values_list("status", flat=True)) == {
        status.value for status in Statusy
    }


@pytest.mark.django_db
def test_fd443_zwykle_wyszukiwanie_nie_wylacza_zawezenia(rf):
    """Bez markera ``q-l=on`` to zwykłe wyszukiwanie — zawężenie zostaje."""
    _zgloszenia_wszystkich_statusow()

    request = rf.get("/", {"q": "cokolwiek"})
    filtr = StanObslugiFilter(request, {}, Zgloszenie_Publikacji, _admin())

    assert filtr.czy_domyslne_zawezenie() is True


@pytest.mark.django_db
def test_fd443_parametr_tylko_podobny_do_statusu_nie_wylacza_zawezenia(rf):
    """``status_wewnetrzny=…`` to nie jest lookup po ``status`` — filtr działa."""
    _zgloszenia_wszystkich_statusow()

    request = rf.get("/", {"status_wewnetrzny": "2"})
    filtr = StanObslugiFilter(request, {}, Zgloszenie_Publikacji, _admin())

    assert filtr.czy_domyslne_zawezenie() is True

    qs = filtr.queryset(request, Zgloszenie_Publikacji.objects.all())
    assert set(qs.values_list("status", flat=True)) == STATUSY_DO_OBSLUGI


# --------------------------------------------------------------------------
# Filtr „zaimportował" — tylko użytkownicy obecni w danych
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_fd443_filtr_zaimportowal_listuje_tylko_uzytkownikow_z_danych(admin_client):
    """``RelatedOnlyFieldListFilter``, nie gołe pole.

    Bez tego sidebar dostaje ``<li>`` dla KAŻDEGO użytkownika w bazie (plus
    HTMX-owy licznik do każdej pozycji) — na produkcji to setki wierszy i
    setek zapytań na render listy.
    """
    importujacy = baker.make("bpp.BppUser", username="fd443_importujacy")
    baker.make("bpp.BppUser", username="fd443_postronny")
    _zaimportowane_zgloszenie(zaimportowal=importujacy)

    response = _changelist(admin_client)
    spec = _spec_zaimportowal(response)

    assert isinstance(spec, django_admin.RelatedOnlyFieldListFilter)
    assert {pk for pk, _etykieta in spec.lookup_choices} == {importujacy.pk}


# --------------------------------------------------------------------------
# Panel audytu na formularzu zgłoszenia
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_fd443_panel_audytu_pokazuje_date_uzytkownika_i_link_do_rekordu(
    admin_client, wydawnictwo_ciagle
):
    operator = baker.make("bpp.BppUser", username="operator_fd443")
    kiedy = timezone.now()

    zgloszenie = _zaimportowane_zgloszenie(
        strona_www="https://doi.org/10.1234/abc.def",
        zaimportowano=kiedy,
        zaimportowal=operator,
    )
    zgloszenie.odpowiednik_w_bpp = wydawnictwo_ciagle
    zgloszenie.save()

    html = _change_html(admin_client, zgloszenie)
    panel = _panel_fragment(html)

    assert "Zaimportowane" in panel

    oczekiwana_data = format_date(timezone.localtime(kiedy), "d.m.Y H:i")
    assert oczekiwana_data in panel

    assert "operator_fd443" in panel

    url_rekordu = reverse(
        "admin:bpp_wydawnictwo_ciagle_change", args=[wydawnictwo_ciagle.pk]
    )
    assert url_rekordu in panel
    assert str(wydawnictwo_ciagle) in panel


@pytest.mark.django_db
def test_fd443_link_do_utworzonego_rekordu_dokladnie_raz_na_stronie(
    admin_client, wydawnictwo_ciagle
):
    """Jedno źródło prawdy: link do rekordu jest WYŁĄCZNIE w panelu.

    Wcześniej to samo dublowało się w ``readonly_fields`` — dwa identyczne
    linki na stronie i dwa komplety zapytań na render.
    """
    zgloszenie = _zaimportowane_zgloszenie()
    zgloszenie.odpowiednik_w_bpp = wydawnictwo_ciagle
    zgloszenie.save()

    html = _change_html(admin_client, zgloszenie)
    url_rekordu = reverse(
        "admin:bpp_wydawnictwo_ciagle_change", args=[wydawnictwo_ciagle.pk]
    )

    assert html.count(f'href="{url_rekordu}"') == 1
    assert html.count(url_rekordu) == 1


@pytest.mark.django_db
def test_fd443_panel_linkuje_do_realnej_sesji_importu(admin_client):
    """Link „sesja importu" liczony z REALNEJ ``ImportSession``.

    Poprzednia wersja testu nie tworzyła żadnej sesji, więc gałąź budująca
    ``admin:importer_publikacji_importsession_change`` nie była wykonywana
    ani razu — działała przez przypadek.
    """
    zgloszenie = _zaimportowane_zgloszenie()
    sesja = _sesja_importu(zgloszenie)

    # Stan z bazy, nie z atrybutu w pamięci.
    assert list(
        Zgloszenie_Publikacji.objects.get(pk=zgloszenie.pk).sesje_importu.values_list(
            "pk", flat=True
        )
    ) == [sesja.pk]

    panel = _panel_fragment(_change_html(admin_client, zgloszenie))

    url_sesji = reverse(
        "admin:importer_publikacji_importsession_change", args=[sesja.pk]
    )
    assert f'href="{url_sesji}"' in panel
    assert "sesja importu" in panel


@pytest.mark.django_db
def test_fd443_panel_bez_sesji_importu_nie_pokazuje_linku_do_sesji(admin_client):
    zgloszenie = _zaimportowane_zgloszenie()

    panel = _panel_fragment(_change_html(admin_client, zgloszenie))

    assert "sesja importu" not in panel


@pytest.mark.django_db
def test_fd443_panel_przy_wielu_sesjach_importu_linkuje_dokladnie_jedna(admin_client):
    """Wiele sesji na jednym zgłoszeniu (ponowiony import) nie mnoży linków."""
    zgloszenie = _zaimportowane_zgloszenie()
    sesje = [
        _sesja_importu(zgloszenie, identifier=f"10.1234/abc.{numer}")
        for numer in range(3)
    ]

    assert (
        Zgloszenie_Publikacji.objects.get(pk=zgloszenie.pk).sesje_importu.count() == 3
    )

    panel = _panel_fragment(_change_html(admin_client, zgloszenie))

    trafione = [
        sesja
        for sesja in sesje
        if reverse("admin:importer_publikacji_importsession_change", args=[sesja.pk])
        in panel
    ]
    assert len(trafione) == 1
    assert panel.count("sesja importu") == 1


@pytest.mark.django_db
def test_fd443_panel_przezywa_wskazanie_na_nieistniejacy_rekord(
    admin_client, wydawnictwo_ciagle
):
    """Zerwany GenericFK (rekord skasowany) to brak danych, nie HTTP 500."""
    zgloszenie = _zaimportowane_zgloszenie()
    zgloszenie.odpowiednik_w_bpp = wydawnictwo_ciagle
    zgloszenie.save()

    Zgloszenie_Publikacji.objects.filter(pk=zgloszenie.pk).update(
        object_id=wydawnictwo_ciagle.pk + 10**7
    )

    panel = _panel_fragment(_change_html(admin_client, zgloszenie))

    assert "Zaimportowane" in panel
    url_rekordu = reverse(
        "admin:bpp_wydawnictwo_ciagle_change", args=[wydawnictwo_ciagle.pk]
    )
    assert url_rekordu not in panel


@pytest.mark.django_db
def test_fd443_panel_przezywa_rekord_bez_zarejestrowanego_admina(admin_client, caplog):
    """GenericFK wskazuje na model bez admina → ``NoReverseMatch``, nie 500."""
    zgloszenie = _zaimportowane_zgloszenie()
    zalacznik = baker.make(Zgloszenie_Publikacji_Zalacznik, zgloszenie=zgloszenie)

    assert Zgloszenie_Publikacji_Zalacznik not in django_admin.site._registry, (
        "Test zakłada model bez zarejestrowanego ModelAdmin-a"
    )

    Zgloszenie_Publikacji.objects.filter(pk=zgloszenie.pk).update(
        content_type=ContentType.objects.get_for_model(Zgloszenie_Publikacji_Zalacznik),
        object_id=zalacznik.pk,
    )

    with caplog.at_level(logging.ERROR, logger=LOGGER_ADMINA):
        panel = _panel_fragment(_change_html(admin_client, zgloszenie))

    assert "Zaimportowane" in panel
    assert "&#8599;" not in panel

    # Wyjątek został połknięty ŚWIADOMIE — z tracebackiem w logach, nie po cichu.
    polkniete = [rekord for rekord in caplog.records if rekord.name == LOGGER_ADMINA]
    assert len(polkniete) == 1
    assert polkniete[0].exc_info is not None
    assert str(zgloszenie.pk) in polkniete[0].getMessage()


@pytest.mark.django_db
def test_fd443_zaimportowane_nie_pokazuje_przycisku_uzyj_importera(
    admin_client,
):
    """Ochrona przed podwójnym importem — przycisku nie ma w HTML-u (§7)."""
    zgloszenie = _zaimportowane_zgloszenie(
        tytul_oryginalny="Praca już zaimportowana",
        strona_www="https://doi.org/10.1234/abc.def",
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

    # Asercja na stabilnym identyfikatorze panelu, nie na słowie
    # „Zaimportowane" — to ostatnie pojawia się też np. w etykiecie kolumny
    # „Zaimportowano" czy w nazwie filtra i dawało fałszywe alarmy.
    assert 'id="panel-zgloszenie-zaimportowane"' not in html

    tools = _object_tools_fragment(html)
    assert "Użyj importera" in tools
    assert f"zgloszenie={zgloszenie.pk}" in tools
