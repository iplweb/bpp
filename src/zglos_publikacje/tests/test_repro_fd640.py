"""FD#640: dyscypliny przy obcych autorach w zgłoszeniach prac.

Formularz zgłaszania pozwalał podać (i podpowiadał) dyscyplinę autorowi
spoza uczelni, a zapis zgłoszenia dopisywał mu ją na rok pracy (widać ją
było potem w profilu autora). Do tego wybranie przy obcym autorze jednostki
uczelni dopisywało go do niej — stawała się jego „aktualną jednostką”.

Teraz dyscyplinę i jednostkę uczelni określa się tylko autorom uczelni
(``AutorQuerySet.autorzy_uczelni`` — przypisani obecnie lub kiedyś do
jednostki uczelni innej niż obca), autor spoza uczelni dostaje jednostkę obcą,
a zapis zgłoszenia nie zmienia danych autora: dyscyplina zostaje propozycją,
``Autor_Dyscyplina`` zakłada dopiero redakcja przy zatwierdzaniu (importer).
"""

import datetime
import json

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Dyscyplina, Autor_Jednostka, Jednostka
from zglos_publikacje.forms import Zgloszenie_Publikacji_AutorForm
from zglos_publikacje.models import Zgloszenie_Publikacji, Zgloszenie_Publikacji_Autor
from zglos_publikacje.tests.tests_zglos_publikacje import (
    _krok2_dane,
    _przejdz_do_kroku_danych,
)

ROK = 2020  # rok z _krok2_dane
KOMUNIKAT_OBCY = "nie jest autorem uczelni"
KOMUNIKAT_JEDNOSTKA_OBCEGO = "można go przypisać wyłącznie do jednostki"


@pytest.fixture
def autor_obcy(uczelnia_z_obca_jednostka, obca_jednostka):
    """Autor powiązany wyłącznie z jednostką obcą uczelni."""
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
def test_doktorant_jest_autorem_uczelni_i_ma_dyscypline(
    uczelnia_z_obca_jednostka, wydzial, jednostka, jednostka_maker, dyscyplina1
):
    """Strażnik #3: jednostka uczelni bez ``skupia_pracownikow`` (doktoranci,
    studenci, emeryci) czyni autora autorem uczelni — ta sama definicja co
    pełny profil autora (``AutorQuerySet.autorzy_uczelni``)."""
    uczelnia = uczelnia_z_obca_jednostka
    doktoranci = jednostka_maker(
        "Doktoranci", skrot="Dokt.", wydzial=wydzial, skupia_pracownikow=False
    )
    doktorant = baker.make(Autor, nazwisko="Doktorant")
    Autor_Jednostka.objects.create(autor=doktorant, jednostka=doktoranci)

    assert doktorant.jest_autorem_uczelni(uczelnia)
    assert Autor.objects.autorzy_uczelni(uczelnia).filter(pk=doktorant.pk).exists()

    form = _form(doktorant, jednostka, dyscyplina1, uczelnia=uczelnia)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_jednostka_o_ujemnym_pk_nie_czyni_autorem_uczelni(uczelnia, wydzial):
    bledna = baker.make(
        Jednostka, pk=-5, uczelnia=uczelnia, parent=None, skupia_pracownikow=True
    )
    autor = baker.make(Autor)
    Autor_Jednostka.objects.create(autor=autor, jednostka=bledna)
    assert not autor.jest_autorem_uczelni(uczelnia)


@pytest.mark.django_db
def test_jest_autorem_uczelni_innej_uczelni(uczelnia, jednostka, autor_uczelni):
    from bpp.models import Uczelnia

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
    uczelnia, obca_jednostka, autor_obcy, dyscyplina1
):
    """Repro: obcy autor, któremu dyscyplina już się „dopięła” na rok pracy,
    wymuszał podanie dyscypliny („pole nie może być puste”). Teraz pole ma
    być puste — i podana dyscyplina dalej jest odrzucana."""
    Autor_Dyscyplina.objects.create(
        autor=autor_obcy, rok=ROK, dyscyplina_naukowa=dyscyplina1
    )
    assert _form(autor_obcy, obca_jednostka, None, uczelnia=uczelnia).is_valid()

    form = _form(autor_obcy, obca_jednostka, dyscyplina1, uczelnia=uczelnia)
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


# --- jednostka autora spoza uczelni (punkt 2) ------------------------------


@pytest.mark.django_db
def test_obcy_z_jednostka_uczelni_odrzucony(uczelnia, jednostka, autor_obcy):
    """Repro: obcemu autorowi dało się wybrać jednostkę uczelni."""
    form = _form(autor_obcy, jednostka, None, uczelnia=uczelnia)
    assert not form.is_valid()
    bledy = str(form.errors["jednostka"])
    assert KOMUNIKAT_JEDNOSTKA_OBCEGO in bledy
    assert "Obca Jednostka" in bledy  # podpowiedź, co wybrać


@pytest.mark.django_db
def test_obcy_z_obca_jednostka_przechodzi_bez_afiliacji(
    uczelnia, obca_jednostka, autor_obcy
):
    form = _form(autor_obcy, obca_jednostka, None, uczelnia=uczelnia)
    assert form.is_valid(), form.errors
    assert form.instance.afiliuje is False


@pytest.mark.django_db
def test_autor_uczelni_z_obca_jednostka_odrzucony_jak_dotad(
    uczelnia_z_obca_jednostka, obca_jednostka, autor_uczelni
):
    """Strażnik #438: autor uczelni (afiliuje) nie dostaje jednostki obcej."""
    form = _form(
        autor_uczelni, obca_jednostka, None, uczelnia=uczelnia_z_obca_jednostka
    )
    assert not form.is_valid()
    assert "nie można afiliować" in str(form.errors["jednostka"])


@pytest.mark.django_db
def test_obcy_z_jednostka_innej_uczelni_odrzucony(uczelnia, autor_obcy):
    """„Zostaje wyłącznie jednostka obca” — także jednostka INNEJ uczelni
    w tej samej bazie nie przechodzi."""
    from bpp.models import Uczelnia

    inna = baker.make(Uczelnia, skrot="IN", nazwa="Inna uczelnia")
    jednostka_innej = baker.make(
        Jednostka, uczelnia=inna, skupia_pracownikow=True, parent=None
    )
    form = _form(autor_obcy, jednostka_innej, None, uczelnia=uczelnia)
    assert not form.is_valid()
    assert KOMUNIKAT_JEDNOSTKA_OBCEGO in str(form.errors["jednostka"])


@pytest.mark.django_db
def test_obcy_bez_skonfigurowanej_obcej_jednostki(
    uczelnia, jednostka, obca_jednostka, dyscyplina1
):
    """Uczelnia bez ``obca_jednostka``: autora spoza uczelni nie da się
    zgłosić — komunikat kieruje do redakcji (ustawienie ręczne)."""
    assert uczelnia.obca_jednostka_id is None
    autor = baker.make(Autor)  # bez żadnych przypisań = nie autor uczelni
    form = _form(autor, jednostka, None, uczelnia=uczelnia)
    assert not form.is_valid()
    bledy = str(form.errors["jednostka"])
    assert "nie ma jej ustawionej" in bledy
    assert "Obca jednostka" in bledy


@pytest.mark.django_db
def test_autocomplete_jednostki_dla_obcego_tylko_obca(
    webtest_app, uczelnia, jednostka, obca_jednostka, autor_obcy, autor_uczelni
):
    url = reverse("bpp:zgloszenie-jednostka-autocomplete")

    def ids(autor):
        fwd = json.dumps({"autor": str(autor.pk)}) if autor else "{}"
        res = webtest_app.get(url, {"forward": fwd}).json
        return {int(r["id"]) for r in res["results"]}

    assert ids(autor_obcy) == {obca_jednostka.pk}
    assert jednostka.pk in ids(autor_uczelni)
    assert jednostka.pk in ids(None)

    # Bez ustawionej obcej jednostki obcemu (tu: autor bez przypisań) nie ma
    # czego podpowiedzieć.
    uczelnia.obca_jednostka = None
    uczelnia.save()
    assert ids(baker.make(Autor)) == set()


@pytest.mark.django_db
def test_autocomplete_jednostki_mowi_o_afiliacji(
    webtest_app, uczelnia, jednostka, obca_jednostka
):
    """FD#640 (punkt 4): wynik autocomplete niesie ``przyjmuje_afiliacje`` —
    ``autorform_dependant.js`` odznacza wtedy „Afiliuje”."""
    obca_jednostka.widoczna = True
    obca_jednostka.save()
    res = webtest_app.get(reverse("bpp:public-jednostka-autocomplete")).json
    wg_id = {int(r["id"]): r["przyjmuje_afiliacje"] for r in res["results"]}
    assert wg_id[jednostka.pk] is True
    assert wg_id[obca_jednostka.pk] is False


def test_pole_jednostki_oznaczone_dla_js():
    widget = Zgloszenie_Publikacji_AutorForm.base_fields["jednostka"].widget
    assert widget.attrs.get("data-obcy-tylko-obca-jednostka") == "1"
    assert widget.url == reverse("bpp:zgloszenie-jednostka-autocomplete")
    assert "autor" in [getattr(f, "src", f) for f in widget.forward]


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
def test_zgloszenie_obcego_z_jednostka_uczelni_odrzucone(
    webtest_app,
    typy_odpowiedzialnosci,
    uczelnia,
    autor_obcy,
    jednostka,
):
    """Repro: zgłoszenie z obcym autorem i jednostką uczelni przechodziło
    (i dopisywało go do tej jednostki — nowa „aktualna jednostka”)."""
    page = _wypelnij_autora(webtest_app, autor_obcy, jednostka)
    res = page.forms[0].submit()
    assert KOMUNIKAT_JEDNOSTKA_OBCEGO in res.text
    assert not Zgloszenie_Publikacji.objects.exists()


@pytest.mark.django_db
def test_zgloszenie_obcego_z_obca_jednostka(
    webtest_app,
    django_capture_on_commit_callbacks,
    typy_odpowiedzialnosci,
    uczelnia,
    autor_obcy,
    obca_jednostka,
):
    page = _wypelnij_autora(webtest_app, autor_obcy, obca_jednostka)
    with django_capture_on_commit_callbacks(execute=True):
        page.forms[0].submit().maybe_follow()

    zpa = Zgloszenie_Publikacji.objects.get().zgloszenie_publikacji_autor_set.get()
    assert zpa.autor == autor_obcy
    assert zpa.jednostka == obca_jednostka
    assert zpa.afiliuje is False
    assert zpa.dyscyplina_naukowa is None
    assert not Autor_Dyscyplina.objects.filter(autor=autor_obcy).exists()
    autor_obcy.refresh_from_db()
    assert not autor_obcy.jest_autorem_uczelni(uczelnia)


@pytest.mark.django_db
def test_zgloszenie_nie_zaklada_autorowi_jednostki(
    webtest_app,
    django_capture_on_commit_callbacks,
    typy_odpowiedzialnosci,
    uczelnia,
    wydzial,
    jednostka_maker,
    autor_uczelni,
):
    """Autor uczelni zgłoszony z INNĄ jednostką uczelni: zgłoszenie nie
    zakłada mu ``Autor_Jednostka`` w tej jednostce (dawniej zakładało)."""
    druga = jednostka_maker("Druga Katedra", skrot="DK", wydzial=wydzial)
    page = _wypelnij_autora(webtest_app, autor_uczelni, druga)
    with django_capture_on_commit_callbacks(execute=True):
        page.forms[0].submit().maybe_follow()

    zpa = Zgloszenie_Publikacji.objects.get().zgloszenie_publikacji_autor_set.get()
    assert zpa.jednostka == druga
    assert not Autor_Jednostka.objects.filter(
        autor=autor_uczelni, jednostka=druga
    ).exists()


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
def test_zgloszenie_autora_uczelni_dyscyplina_tylko_propozycja(
    webtest_app,
    django_capture_on_commit_callbacks,
    typy_odpowiedzialnosci,
    uczelnia,
    autor_uczelni,
    jednostka,
    dyscyplina1,
):
    """Punkt 1: zapis zgłoszenia (anonim) NIE zakłada ``Autor_Dyscyplina`` —
    dyscyplina zostaje propozycją w zgłoszeniu. Przypisanie po zatwierdzeniu
    w importerze: ``importer_publikacji/tests/test_repro_fd640.py``."""
    page = _wypelnij_autora(webtest_app, autor_uczelni, jednostka, dyscyplina1)
    with django_capture_on_commit_callbacks(execute=True):
        page.forms[0].submit().maybe_follow()

    zpa = Zgloszenie_Publikacji.objects.get().zgloszenie_publikacji_autor_set.get()
    assert zpa.dyscyplina_naukowa == dyscyplina1
    assert not Autor_Dyscyplina.objects.filter(autor=autor_uczelni).exists()


# --- „Dodaj wyd. …” ze zgłoszenia w adminie ---------------------------------


def _zpa_bez_walidacji(autor, jednostka, dyscyplina=None, rok=ROK):
    zpa = baker.prepare(
        Zgloszenie_Publikacji_Autor,
        _save_related=True,
        autor=autor,
        jednostka=jednostka,
        dyscyplina_naukowa=dyscyplina,
        rok=rok,
    )
    zpa.save(**{"__disable_bmoa_clean_method": True})
    return zpa


@pytest.mark.django_db
def test_admin_podpowiedz_obcemu_bez_jednostki_uczelni_i_dyscypliny(
    uczelnia, jednostka, obca_jednostka, autor_obcy, dyscyplina1
):
    """Stare zgłoszenie: obcy autor z jednostką uczelni i dyscypliną."""
    from zglos_publikacje.dyscypliny import podpowiedz_dla_redakcji

    zpa = _zpa_bez_walidacji(autor_obcy, jednostka, dyscyplina1)
    initial, uwagi = podpowiedz_dla_redakcji(zpa, ROK)
    assert initial == {
        "autor": autor_obcy.pk,
        "jednostka": obca_jednostka.pk,
        "dyscyplina_naukowa": None,
        "afiliuje": False,  # obca jednostka nigdy nie afiliuje
    }
    assert "jest spoza uczelni" in uwagi[0]


@pytest.mark.django_db
def test_admin_podpowiedz_propozycji_bez_przypisania(
    uczelnia, jednostka, autor_uczelni, dyscyplina1
):
    """Propozycja dla autora uczelni bez przypisania na rok: nie wpisujemy
    (walidacja rekordu by jej nie przyjęła), redaktor dostaje komunikat.
    Z przypisaniem — wpisujemy."""
    from zglos_publikacje.dyscypliny import podpowiedz_dla_redakcji

    zpa = _zpa_bez_walidacji(autor_uczelni, jednostka, dyscyplina1)
    initial, uwagi = podpowiedz_dla_redakcji(zpa, ROK)
    assert initial["jednostka"] == jednostka.pk
    assert initial["dyscyplina_naukowa"] is None
    assert "nie ma do niej przypisania" in uwagi[0]

    Autor_Dyscyplina.objects.create(
        autor=autor_uczelni, rok=ROK, dyscyplina_naukowa=dyscyplina1
    )
    initial, uwagi = podpowiedz_dla_redakcji(zpa, ROK)
    assert initial["dyscyplina_naukowa"] == dyscyplina1.pk
    assert uwagi == []


@pytest.mark.django_db
def test_admin_dodaj_wydawnictwo_ze_zgloszenia_obcego(
    admin_app,
    typy_odpowiedzialnosci,
    uczelnia,
    jednostka,
    obca_jednostka,
    autor_obcy,
    dyscyplina1,
):
    from bpp.const import NUMER_ZGLOSZENIA_PARAM

    zpa = _zpa_bez_walidacji(autor_obcy, jednostka, dyscyplina1)
    page = admin_app.get(
        reverse("admin:bpp_wydawnictwo_ciagle_add")
        + f"?{NUMER_ZGLOSZENIA_PARAM}={zpa.rekord_id}"
    )
    form = page.forms["wydawnictwo_ciagle_form"]
    assert form["autorzy_set-0-autor"].value == str(autor_obcy.pk)
    assert form["autorzy_set-0-jednostka"].value == str(obca_jednostka.pk)
    assert not form["autorzy_set-0-dyscyplina_naukowa"].value
    assert "jest spoza uczelni" in page.text


# --- interfejs: pole dyscypliny chowane dla autora spoza uczelni -----------


def test_pole_dyscypliny_oznaczone_dla_js():
    widget = Zgloszenie_Publikacji_AutorForm.base_fields["dyscyplina_naukowa"].widget
    assert widget.attrs.get("data-tylko-autor-uczelni") == "1"


@pytest.mark.django_db
def test_api_mowi_czy_autor_uczelni(
    webtest_app, uczelnia, obca_jednostka, autor_obcy, autor_uczelni
):
    url = reverse("bpp:api_ostatnia_jednostka_i_dyscyplina")
    res = webtest_app.post(url, {"autor_id": autor_obcy.pk, "rok": ROK}).json
    assert res["autor_uczelni"] is False
    assert res["obca_jednostka_id"] == obca_jednostka.pk
    assert res["obca_jednostka_nazwa"] == obca_jednostka.nazwa

    res = webtest_app.post(url, {"autor_id": autor_uczelni.pk, "rok": ROK}).json
    assert res["autor_uczelni"] is True
    assert "obca_jednostka_id" not in res


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


def _raport(*args):
    from io import StringIO

    from django.core.management import call_command

    out = StringIO()
    call_command("fd640_dyscypliny_obcych_ze_zgloszen", *args, stdout=out)
    return out.getvalue()


def _stan_bazy():
    return (
        sorted(Autor_Dyscyplina.objects.values_list("pk", "autor_id", "rok")),
        sorted(Autor_Jednostka.objects.values_list("pk", "autor_id", "jednostka_id")),
    )


@pytest.mark.django_db
def test_komenda_tylko_raport(
    uczelnia, jednostka, obca_jednostka, autor_obcy, dyscyplina1
):
    from django.core.management.base import CommandError

    from bpp.models import Wydawnictwo_Ciagle_Autor
    from zglos_publikacje.fd640 import znajdz_przypadki

    # Obcy: dyscyplina + jednostka uczelni wyglądająca na „ze zgłoszenia”.
    _dopiete_przez_zgloszenie(autor_obcy, jednostka, dyscyplina1)

    # Autor uczelni (datowane zatrudnienie) — nie trafia do raportu.
    swoj = baker.make(Autor, nazwisko="Swój")
    Autor_Jednostka.objects.create(
        autor=swoj, jednostka=jednostka, rozpoczal_prace=datetime.date(2020, 1, 1)
    )
    _dopiete_przez_zgloszenie(swoj, jednostka, dyscyplina1)

    # Autor z pracą w tej jednostce (powiązanie nie tylko ze zgłoszenia).
    z_praca = baker.make(Autor, nazwisko="Zpraca")
    _dopiete_przez_zgloszenie(z_praca, jednostka, dyscyplina1)
    baker.make(Wydawnictwo_Ciagle_Autor, autor=z_praca, jednostka=jednostka)

    # Obcy, któremu zgłoszenie dopisało tylko dyscyplinę (jednostka obca) —
    # przypadek pewny.
    pewny = baker.make(Autor, nazwisko="Pewny")
    Autor_Jednostka.objects.create(autor=pewny, jednostka=obca_jednostka)
    _dopiete_przez_zgloszenie(pewny, obca_jednostka, dyscyplina1)

    przed = _stan_bazy()
    raport = _raport()
    assert _stan_bazy() == przed  # tylko odczyt

    assert "tylko odczyt" in raport
    assert "Yilmaz" in raport and "Pewny" in raport
    assert "Swój" not in raport and "Zpraca" not in raport
    assert "Przypadków: 2, w tym niepewnych: 1" in raport
    przypadki = {p.autor.nazwisko: p for p in znajdz_przypadki()}
    assert przypadki["Yilmaz"].niepewne
    assert [aj.jednostka for aj in przypadki["Yilmaz"].jednostki_ze_zgloszenia] == [
        jednostka
    ]
    assert not przypadki["Pewny"].niepewne

    with pytest.raises(CommandError):
        _raport("--usun")


@pytest.mark.django_db
def test_komenda_csv(uczelnia, jednostka, autor_obcy, dyscyplina1):
    import csv
    from io import StringIO

    _dopiete_przez_zgloszenie(autor_obcy, jednostka, dyscyplina1)
    wiersze = list(csv.DictReader(StringIO(_raport("--csv"))))
    assert len(wiersze) == 1
    assert wiersze[0]["sekcja"] == "dyscyplina"
    assert wiersze[0]["autor_id"] == str(autor_obcy.pk)
    assert wiersze[0]["niepewne"] == "tak"
    assert wiersze[0]["zmienione_przez_redakcje"] == "nie"


@pytest.mark.django_db
def test_komenda_pomija_pracownika_innej_uczelni(uczelnia, jednostka, dyscyplina1):
    """Baza wielu uczelni: autor obcy dla jednej, pracownik drugiej."""
    from bpp.models import Uczelnia
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
def test_komenda_zmiana_przez_inline_w_edycji_autora(
    admin_app, uczelnia, obca_jednostka, autor_obcy, dyscyplina1
):
    """Prawdziwa ścieżka redakcji: zmiana przypisania w inline „Powiązania
    autor-dyscyplina” formularza autora (POST) — raport oznacza przypadek
    jako zmieniony."""
    from zglos_publikacje.fd640 import znajdz_przypadki

    ad = _dopiete_przez_zgloszenie(autor_obcy, obca_jednostka, dyscyplina1)
    (przypadek,) = znajdz_przypadki()
    assert not przypadek.zmienione

    form = admin_app.get(
        reverse("admin:bpp_autor_change", args=(autor_obcy.pk,))
    ).forms["autor_form"]
    i = next(
        n
        for n in range(int(form["autor_dyscyplina_set-TOTAL_FORMS"].value))
        if form[f"autor_dyscyplina_set-{n}-id"].value == str(ad.pk)
    )
    form[f"autor_dyscyplina_set-{i}-procent_dyscypliny"] = "50.00"
    res = form.submit()
    assert res.status_code == 302, res.text[:2000]
    ad.refresh_from_db()
    assert ad.procent_dyscypliny == 50

    (przypadek,) = znajdz_przypadki()
    assert przypadek.zmienione
    assert "zmieniono później" in _raport()


@pytest.mark.django_db
def test_komenda_liczy_prace_jak_trigger(
    uczelnia, obca_jednostka, autor_obcy, dyscyplina1, dyscyplina2
):
    """Trigger ``bpp_autor_dyscyplina_delete`` zeruje dyscyplinę we
    wszystkich autorstwach autora z danego roku — także z INNĄ dyscypliną.
    Raport liczy tak samo (sprawdzone na prawdziwym usunięciu, cofniętym)."""
    from django.db import transaction

    from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor
    from zglos_publikacje.fd640 import znajdz_przypadki

    ad = _dopiete_przez_zgloszenie(autor_obcy, obca_jednostka, dyscyplina1)

    def autorstwo(rok, dyscyplina):
        wca = baker.prepare(
            Wydawnictwo_Ciagle_Autor,
            rekord=baker.make(Wydawnictwo_Ciagle, rok=rok),
            autor=autor_obcy,
            jednostka=obca_jednostka,
            afiliuje=False,
            dyscyplina_naukowa=dyscyplina,
            _save_related=True,
        )
        wca.save(**{"__disable_bmoa_clean_method": True})

    autorstwo(ROK, dyscyplina1)
    autorstwo(ROK, dyscyplina2)  # inna dyscyplina — trigger też ją zeruje
    autorstwo(ROK, None)
    autorstwo(ROK + 1, dyscyplina1)  # inny rok — bez zmian

    (przypadek,) = znajdz_przypadki()
    assert przypadek.prace_tracace_dyscypline == 2
    assert "wyzerowałoby dyscyplinę w 2 autorstwach" in _raport()

    z_dyscyplina = Wydawnictwo_Ciagle_Autor.objects.filter(
        autor=autor_obcy, dyscyplina_naukowa__isnull=False
    )
    przed = z_dyscyplina.count()
    with transaction.atomic():
        Autor_Dyscyplina.objects.filter(pk=ad.pk).delete()
        assert przed - z_dyscyplina.count() == 2
        transaction.set_rollback(True)


@pytest.mark.django_db
def test_komenda_sekcja_jednostek_bez_dyscyplin(
    admin_app, uczelnia_z_obca_jednostka, jednostka, obca_jednostka
):
    """Zgłoszenie sprzed FD#620: powiązanie z jednostką bez dyscypliny.
    Raport pokazuje autora w osobnej sekcji (niepewne); powiązanie dodane
    w edycji autora (historia admina) nie jest brane za „ze zgłoszenia”."""
    from zglos_publikacje.fd640 import znajdz_jednostki_bez_dyscyplin

    def stare_zgloszenie(autor):
        Autor_Jednostka.objects.create(autor=autor, jednostka=obca_jednostka)
        zpa = baker.prepare(
            Zgloszenie_Publikacji_Autor,
            _save_related=True,
            autor=autor,
            jednostka=jednostka,
            rok=ROK,
        )
        zpa.save(**{"__disable_bmoa_clean_method": True})

    ze_zgloszenia = baker.make(Autor, nazwisko="Zezgloszenia")
    stare_zgloszenie(ze_zgloszenia)
    Autor_Jednostka.objects.create(autor=ze_zgloszenia, jednostka=jednostka)

    z_redakcji = baker.make(Autor, nazwisko="Zredakcji")
    stare_zgloszenie(z_redakcji)
    form = admin_app.get(
        reverse("admin:bpp_autor_change", args=(z_redakcji.pk,))
    ).forms["autor_form"]
    i = int(form["autor_jednostka_set-INITIAL_FORMS"].value)
    form[f"autor_jednostka_set-{i}-jednostka"].force_value(jednostka.pk)
    assert form.submit().status_code == 302
    assert Autor_Jednostka.objects.filter(
        autor=z_redakcji, jednostka=jednostka
    ).exists()

    wynik = znajdz_jednostki_bez_dyscyplin()
    assert [p.autor for p in wynik] == [ze_zgloszenia]
    assert wynik[0].niepewne
    raport = _raport()
    assert "2. Autorzy" in raport and "Zezgloszenia" in raport
    assert "Zredakcji" not in raport


@pytest.mark.django_db
def test_formularz_bez_uczelni_z_requestu_fail_closed(
    jednostka, autor_uczelni, dyscyplina1
):
    """Uczelnia z requestu (także brak) jest wiążąca — zgłaszający nie
    „wybiera” uczelni jednostką."""
    form = _form(autor_uczelni, jednostka, dyscyplina1, uczelnia=None)
    assert not form.is_valid()
    assert KOMUNIKAT_OBCY in str(form.errors["dyscyplina_naukowa"])


# --- anonimowy zgłaszający niczego nie zapisuje w danych autorów ------------


def _migawka_autorow():
    """Pełny stan ``Autor`` / ``Autor_Jednostka`` / ``Autor_Dyscyplina`` oraz
    ich historii — do porównania przed i po działaniu zgłaszającego."""
    from django.contrib.admin.models import LogEntry
    from django.contrib.contenttypes.models import ContentType
    from reversion.models import Version

    modele = (Autor, Autor_Jednostka, Autor_Dyscyplina)
    cts = [ContentType.objects.get_for_model(m) for m in modele]
    return (
        list(Autor.global_objects.order_by("pk").values()),
        list(Autor_Jednostka.objects.order_by("pk").values()),
        list(Autor_Dyscyplina.all_objects.order_by("pk").values()),
        LogEntry.objects.filter(content_type__in=cts).count(),
        Version.objects.filter(content_type__in=cts).count(),
    )


def _przejdz_poprawke(webtest_app, zgloszenie):
    """Kroki 0–2 poprawki zwróconego zgłoszenia (link z e-maila)."""
    url = reverse("zglos_publikacje:edycja_zgloszenia", args=[zgloszenie.kod_do_edycji])
    page = webtest_app.get(url)
    page.forms[0]["0-rodzaj"] = "POZOSTALE"
    page = page.forms[0].submit()
    page.forms[0]["1-forma_dostepu"] = "OTWARTY"
    page = page.forms[0].submit()
    page = page.forms[0].submit()  # dane — bez zmian
    assert "3-TOTAL_FORMS" in page.forms[0].fields, page.text[:3000]
    return page


@pytest.mark.django_db
def test_anonim_nie_zmienia_danych_autorow_przy_zgloszeniu_i_poprawce(
    webtest_app,
    django_capture_on_commit_callbacks,
    typy_odpowiedzialnosci,
    uczelnia,
    jednostka,
    obca_jednostka,
    autor_uczelni,
    autor_obcy,
    dyscyplina1,
):
    """Wymaganie właściciela (punkt 6): anonimowy zgłaszający nie powoduje
    żadnego zapisu w ``Autor``/``Autor_Jednostka``/``Autor_Dyscyplina`` — ani
    przy złożeniu zgłoszenia, ani przy poprawce zwróconego. Przypisania
    powstają dopiero przy zatwierdzeniu przez redakcję."""
    import uuid

    przed = _migawka_autorow()

    page = _wypelnij_autora(webtest_app, autor_uczelni, jednostka, dyscyplina1)
    with django_capture_on_commit_callbacks(execute=True):
        page.forms[0].submit().maybe_follow()
    assert _migawka_autorow() == przed

    # Redakcja zwraca zgłoszenie; zgłaszający poprawia je i dopisuje obcego.
    zgloszenie = Zgloszenie_Publikacji.objects.get()
    zgloszenie.status = Zgloszenie_Publikacji.Statusy.WYMAGA_ZMIAN
    zgloszenie.kod_do_edycji = uuid.uuid4()
    zgloszenie.save()

    page = _przejdz_poprawke(webtest_app, zgloszenie)
    form = page.forms[0]
    form["3-TOTAL_FORMS"] = "2"
    form["3-1-autor"].force_value(autor_obcy.pk)
    form["3-1-jednostka"].force_value(obca_jednostka.pk)
    form["3-1-rok"].force_value(ROK)
    with django_capture_on_commit_callbacks(execute=True):
        res = form.submit().maybe_follow()
    assert "3-0-autor" not in res.text, res.text[:3000]

    autorzy = set(
        Zgloszenie_Publikacji.objects.get().zgloszenie_publikacji_autor_set.values_list(
            "autor_id", flat=True
        )
    )
    assert autorzy == {autor_uczelni.pk, autor_obcy.pk}
    assert _migawka_autorow() == przed


@pytest.mark.django_db
def test_poprawka_usuwa_niepoprawny_wiersz_oznaczony_do_usuniecia(
    webtest_app,
    django_capture_on_commit_callbacks,
    typy_odpowiedzialnosci,
    uczelnia,
    jednostka,
    autor_uczelni,
    autor_obcy,
    dyscyplina1,
):
    """Repro (punkt 2): stary wiersz zgłoszenia, który nie przechodzi już
    walidacji (obcy autor z jednostką uczelni i dyscypliną), oznaczony przez
    zgłaszającego do usunięcia, zostawał w zgłoszeniu — zapis sprawdzał
    poprawność wiersza PRZED „Usuń”."""
    import uuid

    page = _wypelnij_autora(webtest_app, autor_uczelni, jednostka)
    with django_capture_on_commit_callbacks(execute=True):
        page.forms[0].submit().maybe_follow()
    zgloszenie = Zgloszenie_Publikacji.objects.get()
    stary = baker.prepare(
        Zgloszenie_Publikacji_Autor,
        rekord=zgloszenie,
        autor=autor_obcy,
        jednostka=jednostka,
        dyscyplina_naukowa=dyscyplina1,
        typ_odpowiedzialnosci=typy_odpowiedzialnosci["aut."],
        rok=ROK,
        kolejnosc=1,
    )
    stary.save(**{"__disable_bmoa_clean_method": True})
    zgloszenie.status = Zgloszenie_Publikacji.Statusy.WYMAGA_ZMIAN
    zgloszenie.kod_do_edycji = uuid.uuid4()
    zgloszenie.save()
    przed = _migawka_autorow()

    page = _przejdz_poprawke(webtest_app, zgloszenie)
    form = page.forms[0]
    i = next(
        n
        for n in range(int(form["3-TOTAL_FORMS"].value))
        if form[f"3-{n}-autor"].value == str(autor_obcy.pk)
    )
    form[f"3-{i}-DELETE"].checked = True
    with django_capture_on_commit_callbacks(execute=True):
        form.submit().maybe_follow()

    assert not Zgloszenie_Publikacji_Autor.objects.filter(pk=stary.pk).exists()
    assert list(
        zgloszenie.zgloszenie_publikacji_autor_set.values_list("autor_id", flat=True)
    ) == [autor_uczelni.pk]
    assert (
        Zgloszenie_Publikacji.objects.get().status
        == Zgloszenie_Publikacji.Statusy.PO_ZMIANACH
    )
    assert _migawka_autorow() == przed


# --- obca jednostka: system check i komunikat w adminie -------------------


@pytest.mark.django_db
def test_system_check_uczelnia_bez_obcej_jednostki(uczelnia, obca_jednostka):
    from bpp.checks import W301_ID, uczelnia_bez_obcej_jednostki_check

    wynik = uczelnia_bez_obcej_jednostki_check(None, databases=["default"])
    assert [w.id for w in wynik] == [W301_ID]
    assert uczelnia.nazwa in wynik[0].msg
    assert uczelnia_bez_obcej_jednostki_check(None) == []  # bez bazy — nic

    uczelnia.obca_jednostka = obca_jednostka
    uczelnia.save()
    assert uczelnia_bez_obcej_jednostki_check(None, databases=["default"]) == []


@pytest.mark.django_db
def test_admin_zgloszen_przypomina_o_obcej_jednostce(
    admin_app, uczelnia, obca_jednostka
):
    url = reverse("admin:zglos_publikacje_zgloszenie_publikacji_changelist")
    assert "nie ma ustawionej obcej jednostki" in admin_app.get(url).text

    uczelnia.obca_jednostka = obca_jednostka
    uczelnia.save()
    assert "nie ma ustawionej obcej jednostki" not in admin_app.get(url).text


# --- afiliacja jednostki obcej przy zatwierdzaniu (punkt 4) -----------------


def _formularz_ze_zgloszenia(admin_app, zgloszenie_id, zrodlo, slowniki):
    from bpp.const import NUMER_ZGLOSZENIA_PARAM
    from bpp.models import Status_Korekty, Typ_KBN

    page = admin_app.get(
        reverse("admin:bpp_wydawnictwo_ciagle_add")
        + f"?{NUMER_ZGLOSZENIA_PARAM}={zgloszenie_id}"
    )
    form = page.forms["wydawnictwo_ciagle_form"]
    form["tytul_oryginalny"] = "Mastitis"
    form["rok"] = str(ROK)
    form["zrodlo"].force_value([zrodlo.pk])
    charaktery, jezyki = slowniki
    form["charakter_formalny"] = charaktery["AC"].pk
    form["jezyk"] = jezyki["pol."].pk
    form["typ_kbn"] = Typ_KBN.objects.get(skrot="PO").pk
    form["status_korekty"] = Status_Korekty.objects.first().pk
    return form


@pytest.mark.django_db
def test_dodaj_wydawnictwo_ze_zgloszenia_obcy_bez_afiliacji_zapis(
    admin_app,
    typy_odpowiedzialnosci,
    uczelnia,
    jednostka,
    obca_jednostka,
    autor_obcy,
    zrodlo,
    charaktery_formalne,
    jezyki,
    typy_kbn,
    statusy_korekt,
):
    """Prefill „Dodaj wyd. ciągłe” ze zgłoszenia: obcy autor dostaje obcą
    jednostkę z odznaczonym „Afiliuje” — i rekord się zapisuje (POST).
    Walidacja afiliacji zostaje: zaznaczone „Afiliuje” przy jednostce obcej
    jest odrzucane."""
    from bpp.models import Wydawnictwo_Ciagle_Autor

    zpa = _zpa_bez_walidacji(autor_obcy, jednostka)
    slowniki = (charaktery_formalne, jezyki)

    form = _formularz_ze_zgloszenia(admin_app, zpa.rekord_id, zrodlo, slowniki)
    assert form["autorzy_set-0-jednostka"].value == str(obca_jednostka.pk)
    assert not form["autorzy_set-0-afiliuje"].checked
    form["autorzy_set-0-zapisany_jako"].force_value(f"{autor_obcy}")

    # Walidacja bez zmian: obca jednostka + „Afiliuje” → błąd, bez zapisu.
    form["autorzy_set-0-afiliuje"].checked = True
    res = form.submit(expect_errors=True)
    assert res.status_code == 200
    assert not Wydawnictwo_Ciagle_Autor.objects.filter(autor=autor_obcy).exists()

    form = _formularz_ze_zgloszenia(admin_app, zpa.rekord_id, zrodlo, slowniki)
    form["autorzy_set-0-zapisany_jako"].force_value(f"{autor_obcy}")
    res = form.submit()
    assert res.status_code == 302, res.text[:3000]
    wca = Wydawnictwo_Ciagle_Autor.objects.get(autor=autor_obcy)
    assert wca.jednostka == obca_jednostka
    assert wca.afiliuje is False
    assert wca.dyscyplina_naukowa is None
