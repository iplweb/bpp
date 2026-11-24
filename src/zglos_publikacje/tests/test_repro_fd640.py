"""FD#640: dyscypliny przy obcych autorach w zgłoszeniach prac.

Formularz zgłaszania pozwalał podać (i podpowiadał) dyscyplinę autorowi
spoza uczelni, a zapis zgłoszenia dopisywał mu ją na rok pracy (widać ją
było potem w profilu autora). Do tego wybranie przy obcym autorze jednostki
uczelni dopisywało go do niej — stawała się jego „aktualną jednostką”.

Teraz dyscyplinę określa się tylko autorom uczelni (zatrudnionym obecnie lub
kiedyś w realnej jednostce uczelni), a zgłoszenie nie zakłada autorowi
powiązania z jednostką.
"""

import datetime
import json

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Dyscyplina, Autor_Jednostka
from zglos_publikacje.dyscypliny import przypisz_dyscypline_jesli_brak
from zglos_publikacje.forms import Zgloszenie_Publikacji_AutorForm
from zglos_publikacje.models import Zgloszenie_Publikacji, Zgloszenie_Publikacji_Autor
from zglos_publikacje.tests.tests_zglos_publikacje import (
    _krok2_dane,
    _przejdz_do_kroku_danych,
)

ROK = 2020  # rok z _krok2_dane
KOMUNIKAT_OBCY = "nie jest autorem uczelni"


@pytest.fixture
def autor_obcy(obca_jednostka):
    """Autor powiązany wyłącznie z jednostką obcą."""
    autor = baker.make(Autor, nazwisko="Yilmaz", imiona="Oktay")
    Autor_Jednostka.objects.create(autor=autor, jednostka=obca_jednostka)
    return autor


@pytest.fixture
def autor_uczelni(jednostka):
    autor = baker.make(Autor, nazwisko="Burmańczuk", imiona="Artur")
    Autor_Jednostka.objects.create(autor=autor, jednostka=jednostka)
    return autor


def _form(autor, jednostka, dyscyplina, rok=ROK, **kw):
    return Zgloszenie_Publikacji_AutorForm(
        data={
            "autor": autor.pk,
            "jednostka": jednostka.pk,
            "dyscyplina_naukowa": dyscyplina.pk if dyscyplina else "",
            "rok": rok,
        },
        **kw,
    )


# --- definicja „autora uczelni” --------------------------------------------


@pytest.mark.django_db
def test_jest_autorem_uczelni(
    uczelnia, jednostka, obca_jednostka, autor_obcy, autor_uczelni
):
    assert autor_uczelni.jest_autorem_uczelni(uczelnia)
    assert not autor_obcy.jest_autorem_uczelni(uczelnia)
    assert not baker.make(Autor).jest_autorem_uczelni(uczelnia)
    assert not autor_uczelni.jest_autorem_uczelni(None)  # fail-closed

    # Były pracownik (zakończone zatrudnienie) to nadal autor uczelni.
    byly = baker.make(Autor)
    Autor_Jednostka.objects.create(
        autor=byly,
        jednostka=jednostka,
        rozpoczal_prace=datetime.date(2010, 1, 1),
        zakonczyl_prace=datetime.date(2015, 1, 1),
    )
    Autor_Jednostka.objects.create(autor=byly, jednostka=obca_jednostka)
    assert byly.jest_autorem_uczelni(uczelnia)


@pytest.mark.django_db
def test_jest_autorem_uczelni_innej_uczelni(uczelnia, jednostka, autor_uczelni):
    from bpp.models import Jednostka, Uczelnia

    inna = baker.make(Uczelnia, skrot="IN", nazwa="Inna uczelnia")
    assert not autor_uczelni.jest_autorem_uczelni(inna)
    jednostka_innej = baker.make(
        Jednostka, uczelnia=inna, skupia_pracownikow=True, parent=None
    )
    Autor_Jednostka.objects.create(autor=autor_uczelni, jednostka=jednostka_innej)
    assert autor_uczelni.jest_autorem_uczelni(inna)


# --- walidacja (serwer) ----------------------------------------------------


@pytest.mark.django_db
def test_obcy_autor_z_dyscyplina_odrzucony(
    uczelnia, jednostka, autor_obcy, dyscyplina1
):
    """Repro: dawniej dyscyplina z podpowiedzi przechodziła i była dopisywana
    autorowi obcemu."""
    form = _form(autor_obcy, jednostka, dyscyplina1, uczelnia=uczelnia)
    assert not form.is_valid()
    assert KOMUNIKAT_OBCY in str(form.errors["dyscyplina_naukowa"])


@pytest.mark.django_db
def test_autor_bez_zadnej_jednostki_z_dyscyplina_odrzucony(
    uczelnia, jednostka, dyscyplina1
):
    autor = baker.make(Autor)
    form = _form(autor, jednostka, dyscyplina1, uczelnia=uczelnia)
    assert not form.is_valid()
    assert KOMUNIKAT_OBCY in str(form.errors["dyscyplina_naukowa"])


@pytest.mark.django_db
def test_obcy_z_przypisaniem_na_rok_bez_dyscypliny_przechodzi(
    uczelnia, jednostka, autor_obcy, dyscyplina1
):
    """Repro: obcy autor, któremu dyscyplina już się „dopięła” na rok pracy,
    wymuszał podanie dyscypliny („pole nie może być puste”). Teraz pole ma
    być puste — i podana dyscyplina dalej jest odrzucana."""
    Autor_Dyscyplina.objects.create(
        autor=autor_obcy, rok=ROK, dyscyplina_naukowa=dyscyplina1
    )
    assert _form(autor_obcy, jednostka, None, uczelnia=uczelnia).is_valid()

    form = _form(autor_obcy, jednostka, dyscyplina1, uczelnia=uczelnia)
    assert not form.is_valid()
    assert KOMUNIKAT_OBCY in str(form.errors["dyscyplina_naukowa"])


@pytest.mark.django_db
def test_model_bez_formularza_tez_odrzuca(uczelnia, jednostka, autor_obcy, dyscyplina1):
    """Bez formularza (uczelnia brana jako jedyna w systemie)."""
    Autor_Dyscyplina.objects.create(
        autor=autor_obcy, rok=ROK, dyscyplina_naukowa=dyscyplina1
    )
    zpa = Zgloszenie_Publikacji_Autor(
        autor=autor_obcy, jednostka=jednostka, dyscyplina_naukowa=dyscyplina1, rok=ROK
    )
    with pytest.raises(ValidationError, match=KOMUNIKAT_OBCY):
        zpa.clean()


@pytest.mark.django_db
def test_autor_uczelni_dyscyplina_jak_dotad(
    uczelnia, jednostka, autor_uczelni, dyscyplina1
):
    """Strażnik: autor uczelni dalej dostaje dyscyplinę z podpowiedzi
    (FD#620) i nadal nie może pominąć przypisanej."""
    assert _form(autor_uczelni, jednostka, dyscyplina1, uczelnia=uczelnia).is_valid()

    Autor_Dyscyplina.objects.create(
        autor=autor_uczelni, rok=ROK, dyscyplina_naukowa=dyscyplina1
    )
    form = _form(autor_uczelni, jednostka, None, uczelnia=uczelnia)
    assert not form.is_valid()
    assert "nie może być puste" in str(form.errors["dyscyplina_naukowa"])


@pytest.mark.django_db
def test_przypisz_dyscypline_pomija_obcego(
    uczelnia, jednostka, autor_obcy, dyscyplina1
):
    # Druga linia obrony: rekord z dyscypliną z pominięciem walidacji.
    zpa = baker.prepare(
        Zgloszenie_Publikacji_Autor,
        _save_related=True,
        autor=autor_obcy,
        jednostka=jednostka,
        dyscyplina_naukowa=dyscyplina1,
        rok=ROK,
    )
    zpa.save(**{"__disable_bmoa_clean_method": True})
    assert przypisz_dyscypline_jesli_brak(zpa, None) is None
    assert not Autor_Dyscyplina.objects.filter(autor=autor_obcy).exists()


# --- zapis zgłoszenia ------------------------------------------------------


def _wypelnij_autora(webtest_app, autor, jednostka, dyscyplina=None):
    page = _przejdz_do_kroku_danych(webtest_app, rodzaj="POZOSTALE")
    page = _krok2_dane(page, tytul="Mastitis", strona_www="https://example.com/")
    page2 = page.forms[0].submit()
    page2.forms[0]["3-0-autor"].force_value(autor.pk)
    page2.forms[0]["3-0-jednostka"].force_value(jednostka.pk)
    if dyscyplina is not None:
        page2.forms[0]["3-0-dyscyplina_naukowa"].force_value(dyscyplina.pk)
    return page2


@pytest.mark.django_db
def test_zgloszenie_obcego_nie_dopisuje_mu_jednostki_ani_dyscypliny(
    webtest_app,
    django_capture_on_commit_callbacks,
    typy_odpowiedzialnosci,
    uczelnia,
    autor_obcy,
    jednostka,
    dyscyplina1,
):
    """Repro: zgłoszenie z obcym autorem i jednostką uczelni dopisywało go do
    tej jednostki (nowa „aktualna jednostka”)."""
    page = _wypelnij_autora(webtest_app, autor_obcy, jednostka)
    with django_capture_on_commit_callbacks(execute=True):
        page.forms[0].submit().maybe_follow()

    zpa = Zgloszenie_Publikacji.objects.get().zgloszenie_publikacji_autor_set.get()
    assert zpa.autor == autor_obcy
    assert zpa.jednostka == jednostka
    assert zpa.dyscyplina_naukowa is None
    assert not Autor_Jednostka.objects.filter(
        autor=autor_obcy, jednostka=jednostka
    ).exists()
    assert not Autor_Dyscyplina.objects.filter(autor=autor_obcy).exists()
    autor_obcy.refresh_from_db()
    assert not autor_obcy.jest_autorem_uczelni(uczelnia)


@pytest.mark.django_db
def test_zgloszenie_obcego_z_dyscyplina_odrzucone(
    webtest_app,
    typy_odpowiedzialnosci,
    uczelnia,
    autor_obcy,
    jednostka,
    dyscyplina1,
):
    page = _wypelnij_autora(webtest_app, autor_obcy, jednostka, dyscyplina1)
    res = page.forms[0].submit()
    assert KOMUNIKAT_OBCY in res.text
    assert not Zgloszenie_Publikacji.objects.exists()
    assert not Autor_Dyscyplina.objects.filter(autor=autor_obcy).exists()


@pytest.mark.django_db
def test_zgloszenie_autora_uczelni_dyscyplina_przypisana(
    webtest_app,
    django_capture_on_commit_callbacks,
    typy_odpowiedzialnosci,
    uczelnia,
    autor_uczelni,
    jednostka,
    dyscyplina1,
):
    """Strażnik FD#620 dla autora uczelni."""
    page = _wypelnij_autora(webtest_app, autor_uczelni, jednostka, dyscyplina1)
    with django_capture_on_commit_callbacks(execute=True):
        page.forms[0].submit().maybe_follow()

    ad = Autor_Dyscyplina.objects.get(autor=autor_uczelni, rok=ROK)
    assert ad.dyscyplina_naukowa == dyscyplina1


# --- interfejs: pole dyscypliny chowane dla autora spoza uczelni -----------


def test_pole_dyscypliny_oznaczone_dla_js():
    widget = Zgloszenie_Publikacji_AutorForm.base_fields["dyscyplina_naukowa"].widget
    assert widget.attrs.get("data-tylko-autor-uczelni") == "1"


@pytest.mark.django_db
def test_api_mowi_czy_autor_uczelni(webtest_app, uczelnia, autor_obcy, autor_uczelni):
    url = reverse("bpp:api_ostatnia_jednostka_i_dyscyplina")
    for autor, oczekiwane in ((autor_obcy, False), (autor_uczelni, True)):
        res = webtest_app.post(url, {"autor_id": autor.pk, "rok": ROK}).json
        assert res["autor_uczelni"] is oczekiwane


@pytest.mark.django_db
def test_autocomplete_bez_zmian(webtest_app, uczelnia, autor_uczelni, dyscyplina1):
    """Strażnik: podpowiedź dyscyplin dla autora uczelni działa jak dotąd."""
    Autor_Dyscyplina.objects.create(
        autor=autor_uczelni, rok=ROK - 1, dyscyplina_naukowa=dyscyplina1
    )
    fwd = json.dumps({"autor": str(autor_uczelni.pk), "rok": str(ROK), "typowe": True})
    res = webtest_app.get(
        reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"), {"forward": fwd}
    ).json
    assert res["results"][0]["children"] == [
        {"id": dyscyplina1.pk, "text": dyscyplina1.nazwa}
    ]


# --- komenda porządkowa ----------------------------------------------------


def _dopiete_przez_zgloszenie(autor, jednostka, dyscyplina, rok=ROK):
    """Stan sprzed poprawki: zgłoszenie założyło autorowi powiązanie
    z jednostką i dopisało dyscyplinę (z wpisem w historii)."""
    from bpp.wersjonowanie import zarejestruj_utworzenie

    zpa = baker.prepare(
        Zgloszenie_Publikacji_Autor,
        _save_related=True,
        autor=autor,
        jednostka=jednostka,
        dyscyplina_naukowa=dyscyplina,
        rok=rok,
    )
    zpa.save(**{"__disable_bmoa_clean_method": True})
    Autor_Jednostka.objects.get_or_create(autor=autor, jednostka=jednostka)
    ad = Autor_Dyscyplina.objects.create(
        autor=autor, rok=rok, dyscyplina_naukowa=dyscyplina
    )
    zarejestruj_utworzenie(
        None,
        ad,
        f"Przypisano dyscyplinę „{dyscyplina}” na rok {rok} przez "
        "niezalogowanego zgłaszającego (x@y.pl) podczas zgłaszania pracy "
        f"„Praca” (zgłoszenie #{zpa.rekord_id})",
    )
    return ad


@pytest.mark.django_db
def test_komenda_raport_i_usuwanie(
    uczelnia, jednostka, obca_jednostka, autor_obcy, dyscyplina1
):
    from io import StringIO

    from django.core.management import call_command

    from bpp.models import Wydawnictwo_Ciagle_Autor

    # Obcy: dyscyplina + jednostka uczelni tylko ze zgłoszenia → do usunięcia.
    ad_obcy = _dopiete_przez_zgloszenie(autor_obcy, jednostka, dyscyplina1)

    # Autor uczelni (datowane zatrudnienie) — zostaje.
    swoj = baker.make(Autor, nazwisko="Swój")
    Autor_Jednostka.objects.create(
        autor=swoj, jednostka=jednostka, rozpoczal_prace=datetime.date(2020, 1, 1)
    )
    _dopiete_przez_zgloszenie(swoj, jednostka, dyscyplina1)

    # Autor z pracą w bazie w tej jednostce (powiązanie nie tylko ze
    # zgłoszenia) — zostaje.
    z_praca = baker.make(Autor, nazwisko="Zpraca")
    _dopiete_przez_zgloszenie(z_praca, jednostka, dyscyplina1)
    baker.make(Wydawnictwo_Ciagle_Autor, autor=z_praca, jednostka=jednostka)

    out = StringIO()
    call_command("fd640_dyscypliny_obcych_ze_zgloszen", stdout=out)
    raport = out.getvalue()
    assert "Yilmaz" in raport
    assert "Swój" not in raport and "Zpraca" not in raport
    assert "Przypadków: 1, do usunięcia: 1 (tylko raport" in raport
    assert Autor_Dyscyplina.objects.filter(pk=ad_obcy.pk).exists()

    call_command("fd640_dyscypliny_obcych_ze_zgloszen", "--usun", stdout=StringIO())
    assert not Autor_Dyscyplina.objects.filter(pk=ad_obcy.pk).exists()
    assert not Autor_Jednostka.objects.filter(
        autor=autor_obcy, jednostka=jednostka
    ).exists()
    # Powiązanie z jednostką obcą i dane pozostałych autorów — bez zmian.
    assert Autor_Jednostka.objects.filter(
        autor=autor_obcy, jednostka=obca_jednostka
    ).exists()
    assert Autor_Dyscyplina.objects.filter(autor__in=[swoj, z_praca]).count() == 2


@pytest.mark.django_db
def test_komenda_pomija_pracownika_innej_uczelni(uczelnia, jednostka, dyscyplina1):
    """Baza wielu uczelni: autor obcy dla jednej, pracownik drugiej."""
    from bpp.models import Jednostka, Uczelnia
    from zglos_publikacje.fd640 import znajdz_przypadki

    inna = baker.make(Uczelnia, skrot="IN", nazwa="Inna uczelnia")
    jednostka_innej = baker.make(
        Jednostka, uczelnia=inna, skupia_pracownikow=True, parent=None
    )
    autor = baker.make(Autor, nazwisko="Zinnej")
    Autor_Jednostka.objects.create(
        autor=autor,
        jednostka=jednostka_innej,
        rozpoczal_prace=datetime.date(2020, 1, 1),
    )
    _dopiete_przez_zgloszenie(autor, jednostka_innej, dyscyplina1)
    assert znajdz_przypadki() == []


@pytest.mark.django_db
def test_komenda_pomija_uzyte_w_pracach_i_zmienione(
    uczelnia, jednostka, obca_jednostka, dyscyplina1
):
    from django.contrib.admin.models import CHANGE, LogEntry

    from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor
    from zglos_publikacje.fd640 import POWOD_ZMIENIONE, usun, znajdz_przypadki

    w_pracy = baker.make(Autor, nazwisko="Wpracy")
    Autor_Jednostka.objects.create(autor=w_pracy, jednostka=obca_jednostka)
    _dopiete_przez_zgloszenie(w_pracy, jednostka, dyscyplina1)
    praca = baker.make(Wydawnictwo_Ciagle, rok=ROK)
    wca = baker.prepare(
        Wydawnictwo_Ciagle_Autor,
        rekord=praca,
        autor=w_pracy,
        jednostka=obca_jednostka,
        dyscyplina_naukowa=dyscyplina1,
        _save_related=True,
    )
    wca.save(**{"__disable_bmoa_clean_method": True})

    zmienione = baker.make(Autor, nazwisko="Zmienione")
    ad = _dopiete_przez_zgloszenie(zmienione, jednostka, dyscyplina1)
    LogEntry.objects.log_actions(
        baker.make("bpp.BppUser").pk, [ad], CHANGE, change_message="ręcznie"
    )

    przypadki = {p.autor.nazwisko: p for p in znajdz_przypadki()}
    assert "dyscyplina użyta w pracach (1)" in przypadki["Wpracy"].pominiety
    assert przypadki["Zmienione"].pominiety == POWOD_ZMIENIONE
    with pytest.raises(ValueError):
        usun(przypadki["Zmienione"])


@pytest.mark.django_db
def test_komenda_dwa_lata_jednego_autora(uczelnia, jednostka, autor_obcy, dyscyplina1):
    from io import StringIO

    from django.contrib.admin.models import DELETION, LogEntry
    from django.core.management import call_command

    _dopiete_przez_zgloszenie(autor_obcy, jednostka, dyscyplina1, rok=ROK)
    _dopiete_przez_zgloszenie(autor_obcy, jednostka, dyscyplina1, rok=ROK + 1)

    call_command("fd640_dyscypliny_obcych_ze_zgloszen", "--usun", stdout=StringIO())

    assert not Autor_Dyscyplina.objects.filter(autor=autor_obcy).exists()
    assert not Autor_Jednostka.objects.filter(
        autor=autor_obcy, jednostka=jednostka
    ).exists()
    assert (
        LogEntry.objects.filter(
            action_flag=DELETION, change_message__contains="powiązanie z jednostką"
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_formularz_bez_uczelni_z_requestu_fail_closed(
    jednostka, autor_uczelni, dyscyplina1
):
    """Uczelnia z requestu (także brak) jest wiążąca — zgłaszający nie
    „wybiera” uczelni jednostką."""
    form = _form(autor_uczelni, jednostka, dyscyplina1, uczelnia=None)
    assert not form.is_valid()
    assert KOMUNIKAT_OBCY in str(form.errors["dyscyplina_naukowa"])
