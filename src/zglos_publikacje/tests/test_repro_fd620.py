"""FD#620 (część 2): formularz zgłaszania publikacji — autor bez przypisanej
dyscypliny na rok pracy.

Dotąd dla takiego autora lista „Dyscyplina naukowa” pokazywała tylko „Brak
przypisania dla roku …”, a wybranie dyscypliny i tak blokowała walidacja.
Teraz lista podpowiada (wspólna funkcja z importerem) dyscypliny autora
z najbliższego wcześniejszego roku albo typowe dla uczelni, a wybrana
dyscyplina zostaje przypisana autorowi na rok pracy przy zapisie zgłoszenia,
z wpisem w historii.
"""

import json

import pytest
from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Dyscyplina, Autor_Jednostka
from bpp.wersjonowanie import konto_systemowe
from zglos_publikacje.dyscypliny import przypisz_dyscypline_jesli_brak
from zglos_publikacje.forms import Zgloszenie_Publikacji_AutorForm
from zglos_publikacje.models import Zgloszenie_Publikacji, Zgloszenie_Publikacji_Autor
from zglos_publikacje.tests.tests_zglos_publikacje import (
    _krok2_dane,
    _przejdz_do_kroku_danych,
)

ROK = 2020  # rok z _krok2_dane


@pytest.fixture
def autor(jednostka):
    # FD#640: dyscyplinę w zgłoszeniu określa się tylko autorom uczelni.
    autor = baker.make(Autor, nazwisko="Gromek", imiona="Paweł")
    Autor_Jednostka.objects.create(autor=autor, jednostka=jednostka)
    return autor


def _wpisy(obj):
    return LogEntry.objects.filter(
        content_type=ContentType.objects.get_for_model(obj),
        object_id=str(obj.pk),
    )


def _form(autor, jednostka, dyscyplina, rok=ROK):
    return Zgloszenie_Publikacji_AutorForm(
        data={
            "autor": autor.pk,
            "jednostka": jednostka.pk,
            "dyscyplina_naukowa": dyscyplina.pk,
            "rok": rok,
        }
    )


# --- walidacja formularza --------------------------------------------------


@pytest.mark.django_db
def test_autor_bez_przypisania_dyscyplina_z_ubieglego_roku_przechodzi(
    autor, jednostka, dyscyplina1, dyscyplina2
):
    Autor_Dyscyplina.objects.create(
        autor=autor, rok=ROK - 1, dyscyplina_naukowa=dyscyplina1
    )
    assert _form(autor, jednostka, dyscyplina1).is_valid()

    # Spoza podpowiedzi (autor miał w ubiegłym roku tylko dyscyplina1).
    form = _form(autor, jednostka, dyscyplina2)
    assert not form.is_valid()
    assert "Wybierz dyscyplinę z podpowiadanej listy" in str(
        form.errors["dyscyplina_naukowa"]
    )


@pytest.mark.django_db
def test_autor_bez_dyscyplin_nigdy_typowe_przechodza(
    autor, jednostka, dyscyplina1
):
    # Brak prac z dyscyplinami w bazie — podpowiedź to wszystkie dyscypliny.
    assert _form(autor, jednostka, dyscyplina1).is_valid()


@pytest.mark.django_db
def test_autor_z_przypisaniem_walidacja_bez_zmian(
    autor, jednostka, dyscyplina1, dyscyplina2
):
    Autor_Dyscyplina.objects.create(autor=autor, rok=ROK, dyscyplina_naukowa=dyscyplina1)
    assert _form(autor, jednostka, dyscyplina1).is_valid()
    form = _form(autor, jednostka, dyscyplina2)
    assert not form.is_valid()
    assert "nie ma przypisania na rok" in str(form.errors["dyscyplina_naukowa"])


@pytest.mark.django_db
def test_poza_formularzem_walidacja_scisla(autor, jednostka, dyscyplina1):
    """Model bez zgody formularza (np. moduł redagowania) — jak dotąd."""
    zpa = Zgloszenie_Publikacji_Autor(
        autor=autor, jednostka=jednostka, dyscyplina_naukowa=dyscyplina1, rok=ROK
    )
    with pytest.raises(ValidationError, match="nie ma przypisania na"):
        zpa.clean()


def test_widget_prosi_o_podpowiedz():
    widget = Zgloszenie_Publikacji_AutorForm.base_fields["dyscyplina_naukowa"].widget
    stale = [f for f in widget.forward if getattr(f, "dst", None) == "typowe"]
    assert len(stale) == 1
    assert stale[0].val is True


# --- zapis zgłoszenia ------------------------------------------------------


@pytest.mark.django_db
def test_zgloszenie_przypisuje_dyscypline_niezalogowany(
    webtest_app,
    django_capture_on_commit_callbacks,
    typy_odpowiedzialnosci,
    uczelnia,
    autor,
    jednostka,
    dyscyplina1,
):
    Autor_Dyscyplina.objects.create(
        autor=autor, rok=ROK - 2, dyscyplina_naukowa=dyscyplina1
    )
    page = _przejdz_do_kroku_danych(webtest_app, rodzaj="POZOSTALE")
    page = _krok2_dane(
        page, tytul="Ochrona ludności", strona_www="https://example.com/"
    )
    page2 = page.forms[0].submit()
    page2.forms[0]["3-0-autor"].force_value(autor.pk)
    page2.forms[0]["3-0-jednostka"].force_value(jednostka.pk)
    page2.forms[0]["3-0-dyscyplina_naukowa"].force_value(dyscyplina1.pk)
    with django_capture_on_commit_callbacks(execute=True):
        page2.forms[0].submit().maybe_follow()

    zgloszenie = Zgloszenie_Publikacji.objects.get()
    assert zgloszenie.zgloszenie_publikacji_autor_set.get().dyscyplina_naukowa == (
        dyscyplina1
    )
    ad = Autor_Dyscyplina.objects.get(autor=autor, rok=ROK)
    assert ad.dyscyplina_naukowa == dyscyplina1

    komunikat = (
        f"Przypisano dyscyplinę „{dyscyplina1}” na rok {ROK} przez "
        f"niezalogowanego zgłaszającego (test@test.pl) podczas zgłaszania pracy "
        f"„Ochrona ludności” (zgłoszenie #{zgloszenie.pk})"
    )
    wpis = _wpisy(ad).get()
    assert wpis.action_flag == ADDITION
    assert wpis.user == konto_systemowe()
    assert wpis.change_message == komunikat
    wpis_autora = _wpisy(autor).get()
    assert wpis_autora.action_flag == CHANGE
    assert wpis_autora.change_message == komunikat


@pytest.mark.django_db
def test_przypisanie_w_imieniu_zalogowanego(autor, jednostka, dyscyplina1):
    from reversion.models import Version

    user = baker.make(
        "bpp.BppUser", username="jbihalowicz", first_name="Jan", last_name="Bihałowicz"
    )
    zgloszenie = baker.make(
        Zgloszenie_Publikacji, tytul_oryginalny="Praca", email="x@example.com"
    )
    zpa = baker.prepare(
        Zgloszenie_Publikacji_Autor,
        _save_related=True,
        rekord=zgloszenie,
        autor=autor,
        jednostka=jednostka,
        dyscyplina_naukowa=dyscyplina1,
        rok=ROK,
    )
    zpa.dopusc_propozycje_dyscypliny = True  # jak formularz zgłoszenia
    zpa.save()

    ad = przypisz_dyscypline_jesli_brak(zpa, user)

    komunikat = (
        f"Przypisano dyscyplinę „{dyscyplina1}” na rok {ROK} przez użytkownika "
        f"Jan Bihałowicz (jbihalowicz) podczas zgłaszania pracy „Praca” "
        f"(zgłoszenie #{zgloszenie.pk})"
    )
    assert _wpisy(ad).get().user == user
    assert _wpisy(ad).get().change_message == komunikat
    assert _wpisy(autor).get().user == user
    wersja = Version.objects.get_for_object(autor).first()
    assert wersja.revision.user == user
    assert wersja.revision.comment == komunikat

    # Drugi raz (np. ten sam autor dwukrotnie) — nic nowego.
    assert przypisz_dyscypline_jesli_brak(zpa, user) is None
    assert Autor_Dyscyplina.objects.filter(autor=autor).count() == 1


@pytest.mark.django_db
def test_autor_z_przypisaniem_nie_dostaje_nowego(autor, jednostka, dyscyplina1):
    Autor_Dyscyplina.objects.create(autor=autor, rok=ROK, dyscyplina_naukowa=dyscyplina1)
    zpa = baker.make(
        Zgloszenie_Publikacji_Autor,
        autor=autor,
        jednostka=jednostka,
        dyscyplina_naukowa=dyscyplina1,
        rok=ROK,
    )
    assert przypisz_dyscypline_jesli_brak(zpa, None) is None
    assert not _wpisy(autor).exists()


@pytest.mark.django_db
def test_autocomplete_dla_formularza_zwraca_podpowiedz(
    webtest_app, uczelnia, autor, dyscyplina1
):
    """Ten sam forward co widżet formularza (napisy + ``typowe``)."""
    Autor_Dyscyplina.objects.create(
        autor=autor, rok=ROK - 1, dyscyplina_naukowa=dyscyplina1
    )
    fwd = json.dumps({"autor": str(autor.pk), "rok": str(ROK), "typowe": True})
    res = webtest_app.get(
        reverse("bpp:dyscyplina-naukowa-przypisanie-autocomplete"), {"forward": fwd}
    ).json
    assert res["results"][0]["children"] == [
        {"id": dyscyplina1.pk, "text": dyscyplina1.nazwa}
    ]
    assert res["brak_przypisania"]["rok_zrodla"] == ROK - 1
