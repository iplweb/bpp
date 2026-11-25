"""FD#587: „wieczne pliki” — pliki rekordów nigdy nie giną z systemu.

- plik usunięty w formularzu publikacji trafia do kosza, a z kosza da się
  go przywrócić w tym samym formularzu,
- plik, który traci odwołanie w bazie (trwałe usunięcie, kaskada, podmiana,
  wyczyszczenie pola), zostaje w „Archiwum plików” i da się go pobrać;
  plik na dysku zostaje nietknięty.
"""

import pytest
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.urls import reverse
from model_bakery import baker

from bpp.const import TRYB_DOSTEPU
from bpp.models import Element_Repozytorium
from historia_zmian.models import ArchiwalnyPlik
from zglos_publikacje.models import Zgloszenie_Publikacji_Zalacznik

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.SENDFILE_ROOT = str(tmp_path)
    return tmp_path


def _plik(nazwa="praca.pdf", tresc=b"%PDF-1.4 tresc"):
    return SimpleUploadedFile(nazwa, tresc, content_type="application/pdf")


def _element(rekord, nazwa="praca.pdf"):
    return Element_Repozytorium.objects.create(
        rekord=rekord,
        rodzaj="pełny tekst",
        nazwa_pliku=nazwa,
        tryb_dostepu=TRYB_DOSTEPU.JAWNY.value,
        plik=_plik(nazwa),
    )


def test_plik_usuniety_w_formularzu_trafia_do_kosza_i_wraca(
    admin_app, wydawnictwo_ciagle
):
    element = _element(wydawnictwo_ciagle)
    sciezka = element.plik.path
    url = reverse("admin:bpp_wydawnictwo_ciagle_change", args=(wydawnictwo_ciagle.pk,))

    strona = admin_app.get(url)
    assert "usunięty plik trafia do kosza" in strona.text
    form = strona.forms["wydawnictwo_ciagle_form"]
    prefiks = next(
        k[: -len("-0-DELETE")] for k in form.fields if k.endswith("-0-DELETE")
    )
    form[f"{prefiks}-0-DELETE"].checked = True
    res = form.submit()
    assert res.status_code == 302, res.text[:2000]

    element = Element_Repozytorium.deleted_objects.get(pk=element.pk)
    assert element.deleted_at is not None
    assert ArchiwalnyPlik.objects.count() == 0  # kosz to nie utrata pliku

    strona = admin_app.get(url)
    assert "pliki repozytorium w koszu" in strona.text.lower()
    form = strona.forms["wydawnictwo_ciagle_form"]
    pole = next(k for k in form.fields if k.endswith("-0-przywroc"))
    form[pole].checked = True
    res = form.submit()
    assert res.status_code == 302, res.text[:2000]

    element = Element_Repozytorium.objects.get(pk=element.pk)
    assert element.deleted_at is None
    with open(sciezka, "rb") as f:
        assert f.read() == b"%PDF-1.4 tresc"


def test_trwale_usuniecie_elementu_trafia_do_archiwum(wydawnictwo_ciagle, admin_user):
    element = _element(wydawnictwo_ciagle, "artykul.pdf")
    nazwa, sciezka = element.plik.name, element.plik.path

    element.hard_delete()

    wpis = ArchiwalnyPlik.objects.get()
    assert wpis.plik.name == nazwa
    assert wpis.powod == ArchiwalnyPlik.Powody.USUNIETO_WIERSZ
    assert wpis.oryginalna_nazwa_pliku == "artykul.pdf"
    assert wydawnictwo_ciagle.tytul_oryginalny in wpis.opis
    assert wpis.model_zrodlowy == "bpp.element_repozytorium"
    with open(sciezka, "rb") as f:
        assert f.read() == b"%PDF-1.4 tresc"


def test_wycofana_transakcja_nie_zostawia_wpisu(wydawnictwo_ciagle):
    element = _element(wydawnictwo_ciagle)
    pk = element.pk

    class Wycofaj(Exception):
        pass

    with pytest.raises(Wycofaj), transaction.atomic():
        element.hard_delete()
        raise Wycofaj

    assert not ArchiwalnyPlik.objects.exists()
    assert Element_Repozytorium.objects.filter(pk=pk).exists()


def test_zgloszenie_podmiana_i_wyczyszczenie_pliku(zgloszenie_publikacji):
    zgloszenie_publikacji.plik = _plik("pierwszy.pdf")
    zgloszenie_publikacji.oryginalna_nazwa_pliku = "pierwszy.pdf"
    zgloszenie_publikacji.save()
    pierwszy = zgloszenie_publikacji.plik.name

    zgloszenie_publikacji.plik = _plik("drugi.pdf")
    zgloszenie_publikacji.oryginalna_nazwa_pliku = "drugi.pdf"
    zgloszenie_publikacji.save()
    drugi = zgloszenie_publikacji.plik.name

    zgloszenie_publikacji.plik = None
    zgloszenie_publikacji.save()

    wpisy = list(ArchiwalnyPlik.objects.order_by("pk"))
    assert [(w.plik.name, w.oryginalna_nazwa_pliku, w.powod) for w in wpisy] == [
        (pierwszy, "pierwszy.pdf", ArchiwalnyPlik.Powody.PODMIENIONO),
        (drugi, "drugi.pdf", ArchiwalnyPlik.Powody.WYCZYSZCZONO),
    ]
    # Zapis bez zmiany pliku nie tworzy wpisu.
    zgloszenie_publikacji.save()
    assert ArchiwalnyPlik.objects.count() == 2


def test_usuniecie_zalacznika_zgloszenia_trafia_do_archiwum(zgloszenie_publikacji):
    zalacznik = Zgloszenie_Publikacji_Zalacznik.objects.create(
        zgloszenie=zgloszenie_publikacji,
        plik=_plik("zalacznik.pdf"),
        oryginalna_nazwa_pliku="zalacznik.pdf",
    )
    zalacznik.delete()

    wpis = ArchiwalnyPlik.objects.get()
    assert wpis.oryginalna_nazwa_pliku == "zalacznik.pdf"
    assert wpis.powod == ArchiwalnyPlik.Powody.USUNIETO_WIERSZ


def test_pobranie_z_archiwum(
    admin_client, client, django_user_model, wydawnictwo_ciagle
):
    _element(wydawnictwo_ciagle, "do-pobrania.pdf").hard_delete()
    wpis = ArchiwalnyPlik.objects.get()
    url = reverse("admin:historia_zmian_archiwalnyplik_pobierz", args=(wpis.pk,))

    lista = admin_client.get(reverse("admin:historia_zmian_archiwalnyplik_changelist"))
    assert lista.status_code == 200
    assert "do-pobrania.pdf" in lista.content.decode()

    res = admin_client.get(url)
    assert res.status_code == 200
    assert "do-pobrania.pdf" in res["Content-Disposition"]

    personel = baker.make(django_user_model, is_staff=True)
    client.force_login(personel)
    assert client.get(url).status_code == 403

    # Samo uprawnienie do archiwum nie wystarcza — plik należał do elementu
    # repozytorium, a tych personel oglądać nie może.
    personel.user_permissions.add(
        Permission.objects.get(codename="view_archiwalnyplik")
    )
    assert client.get(url).status_code == 404
    lista = client.get(reverse("admin:historia_zmian_archiwalnyplik_changelist"))
    assert "do-pobrania.pdf" not in lista.content.decode()

    personel.user_permissions.add(
        Permission.objects.get(codename="view_element_repozytorium")
    )
    personel = django_user_model.objects.get(pk=personel.pk)  # cache uprawnień
    client.force_login(personel)
    assert client.get(url).status_code == 200


def test_zapis_publikacji_z_plikiem_w_koszu(admin_app, wydawnictwo_ciagle):
    """Inline kosza nie może blokować zwykłego zapisu rekordu."""
    element = _element(wydawnictwo_ciagle)
    element.delete()
    url = reverse("admin:bpp_wydawnictwo_ciagle_change", args=(wydawnictwo_ciagle.pk,))

    form = admin_app.get(url).forms["wydawnictwo_ciagle_form"]
    form["tytul_oryginalny"].value = "Tytuł po zmianie FD587"
    res = form.submit()
    assert res.status_code == 302, res.text[:2000]

    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.tytul_oryginalny == "Tytuł po zmianie FD587"
    assert Element_Repozytorium.deleted_objects.filter(pk=element.pk).exists()


def test_trwale_usuniecie_publikacji_archiwizuje_jej_pliki(wydawnictwo_ciagle):
    from bpp.models import Wydawnictwo_Ciagle

    _element(wydawnictwo_ciagle, "w-publikacji.pdf")
    tytul = wydawnictwo_ciagle.tytul_oryginalny
    wydawnictwo_ciagle.delete()
    Wydawnictwo_Ciagle.deleted_objects.filter(pk=wydawnictwo_ciagle.pk).hard_delete()

    wpis = ArchiwalnyPlik.objects.get()
    assert wpis.oryginalna_nazwa_pliku == "w-publikacji.pdf"
    assert wpis.powod == ArchiwalnyPlik.Powody.USUNIETO_WIERSZ
    assert tytul in wpis.opis


def _redaktor_bez_usuwania_plikow(django_user_model):
    """Personel z uprawnieniami grupy „wprowadzanie danych” poza
    ``delete_element_repozytorium``."""
    from django.contrib.auth.models import Group

    from bpp.const import GR_WPROWADZANIE_DANYCH

    redaktor = baker.make(django_user_model, is_staff=True)
    redaktor.user_permissions.set(
        Group.objects.get(name=GR_WPROWADZANIE_DANYCH).permissions.exclude(
            codename="delete_element_repozytorium"
        )
    )
    return redaktor


def test_przywrocenie_z_kosza_wymaga_uprawnienia_do_usuwania(
    admin_app, wydawnictwo_ciagle, django_user_model
):
    element = _element(wydawnictwo_ciagle)
    element.delete()
    redaktor = _redaktor_bez_usuwania_plikow(django_user_model)
    url = reverse("admin:bpp_wydawnictwo_ciagle_change", args=(wydawnictwo_ciagle.pk,))

    strona = admin_app.get(url, user=redaktor)
    form = strona.forms["wydawnictwo_ciagle_form"]
    assert not any(k.endswith("-przywroc") for k in form.fields)

    # Spreparowany POST z polem „przywróć” też nic nie przywraca.
    prefiks = next(
        k[: -len("-TOTAL_FORMS")]
        for k, v in form.fields.items()
        if k.endswith("-TOTAL_FORMS")
        and f"{k[: -len('-TOTAL_FORMS')]}-0-id" in form.fields
        and form[f"{k[: -len('-TOTAL_FORMS')]}-0-id"].value == str(element.pk)
        and f"{k[: -len('-TOTAL_FORMS')]}-0-DELETE" not in form.fields
    )
    pola = list(form.submit_fields()) + [(f"{prefiks}-0-przywroc", "on")]
    res = admin_app.post(url, params=pola, user=redaktor)
    assert res.status_code == 302, res.text[:2000]
    assert Element_Repozytorium.deleted_objects.filter(pk=element.pk).exists()


def test_podmiana_pliku_w_transakcji_blokuje_wiersz(zgloszenie_publikacji):
    """W transakcji odczyt starego pliku idzie z ``FOR UPDATE``."""
    zgloszenie_publikacji.plik = _plik("pierwszy.pdf")
    zgloszenie_publikacji.save()
    with transaction.atomic():
        zgloszenie_publikacji.plik = _plik("drugi.pdf")
        zgloszenie_publikacji.save()
    assert ArchiwalnyPlik.objects.get().powod == ArchiwalnyPlik.Powody.PODMIENIONO
