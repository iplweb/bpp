"""Eksport prac autora (BibTeX/RIS) stosuje te same reguły widoczności,
co publiczna strona autora i strony rekordów:

- autor z ``pokazuj=False`` — 404 dla wszystkich poza redaktorem
  (``moze_wprowadzac_dane``), jak w ``AutorView``;
- prace o statusach korekty ukrytych w kanale ``podglad`` nie trafiają do
  eksportu synchronicznego (poza redaktorem) ani NIGDY do pliku z zadania
  Celery — ten plik jest serwowany publicznie po UUID zadania.
"""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Autor, AutorEksportTask, Rekord, Uczelnia, Wydawnictwo_Ciagle

TOKEN_UKRYTY = "kwazarniewidzialny"
TOKEN_JAWNY = "pulsarwidoczny"

ROLE = ["anonim", "zwykly", "redaktor"]


def _zaloguj(client, django_user_model, rola):
    if rola == "anonim":
        return
    user = django_user_model.objects.create_user(rola, password="haslo123")
    if rola == "redaktor":
        grupa, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
        user.groups.add(grupa)
    client.force_login(user)


@pytest.fixture
def delay(mocker):
    return mocker.patch("bpp.tasks.generuj_eksport_autora.delay")


@pytest.fixture
def autor_ukryty(uczelnia):
    return baker.make(Autor, imiona="Ukryty", nazwisko="Autorukryty", pokazuj=False)


@pytest.fixture
def autor_z_ukryta_praca(
    uczelnia,
    przed_korekta,
    po_korekcie,
    autor_jan_kowalski,
    jednostka,
    typ_odpowiedzialnosci_autor,
):
    for tytul, status in (
        (f"Tajny {TOKEN_UKRYTY} artykul", przed_korekta),
        (f"Jawny {TOKEN_JAWNY} artykul", po_korekcie),
    ):
        pub = baker.make(
            Wydawnictwo_Ciagle,
            tytul_oryginalny=tytul,
            rok=2031,
            status_korekty=status,
        )
        pub.dodaj_autora(autor_jan_kowalski, jednostka, zapisany_jako="Kowalski Jan")
    Rekord.objects.full_refresh()
    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)
    return autor_jan_kowalski


# --- ukryty autor: eksport synchroniczny ----------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("nazwa", ["autor_eksport_bibtex", "autor_eksport_ris"])
@pytest.mark.parametrize(
    "rola,oczekiwany", [("anonim", 302), ("zwykly", 404), ("redaktor", 200)]
)
def test_eksport_sync_ukryty_autor(
    client, django_user_model, autor_ukryty, nazwa, rola, oczekiwany
):
    # Anonim dostaje przekierowanie do logowania (LoginRequiredMixin) zanim
    # w ogóle dojdzie do autora.
    _zaloguj(client, django_user_model, rola)
    res = client.get(reverse(f"bpp:{nazwa}", args=(autor_ukryty.pk,)))
    assert res.status_code == oczekiwany


# --- ukryty autor: start eksportu asynchronicznego ------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("rola", ROLE)
def test_start_eksportu_get_ukryty_autor(
    client, django_user_model, autor_ukryty, delay, rola
):
    _zaloguj(client, django_user_model, rola)
    url = reverse("bpp:autor_eksport_start", args=(autor_ukryty.pk, "bib"))
    res = client.get(url)
    assert res.status_code == (200 if rola == "redaktor" else 404)


@pytest.mark.django_db
@pytest.mark.parametrize("rola", ["anonim", "zwykly"])
def test_start_eksportu_post_ukryty_autor_404(
    client, django_user_model, autor_ukryty, delay, rola
):
    _zaloguj(client, django_user_model, rola)
    url = reverse("bpp:autor_eksport_start", args=(autor_ukryty.pk, "bib"))
    res = client.post(url)
    assert res.status_code == 404
    assert not AutorEksportTask.objects.exists()
    delay.assert_not_called()


@pytest.mark.django_db
def test_start_eksportu_post_ukryty_autor_redaktor(
    client, django_user_model, autor_ukryty, delay
):
    _zaloguj(client, django_user_model, "redaktor")
    url = reverse("bpp:autor_eksport_start", args=(autor_ukryty.pk, "bib"))
    res = client.post(url)
    assert res.status_code == 302
    delay.assert_called_once()


# --- ukryte statusy: eksport synchroniczny --------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("nazwa", ["autor_eksport_bibtex", "autor_eksport_ris"])
@pytest.mark.parametrize("rola", ["zwykly", "redaktor"])
def test_eksport_sync_ukryte_statusy(
    client, django_user_model, autor_z_ukryta_praca, nazwa, rola
):
    _zaloguj(client, django_user_model, rola)
    res = client.get(reverse(f"bpp:{nazwa}", args=(autor_z_ukryta_praca.pk,)))
    assert res.status_code == 200
    body = res.content.decode("utf-8")
    assert TOKEN_JAWNY in body
    assert (TOKEN_UKRYTY in body) == (rola == "redaktor")


# --- ukryte statusy: zadanie Celery ---------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("format", ["bib", "ris"])
def test_zadanie_eksportu_pomija_ukryte_statusy(
    autor_z_ukryta_praca, uczelnia, format
):
    from bpp.tasks import generuj_eksport_autora

    task = AutorEksportTask.objects.create(
        autor=autor_z_ukryta_praca, format=format, uczelnia=uczelnia
    )
    generuj_eksport_autora(str(task.pk))

    task.refresh_from_db()
    assert task.status == "completed"
    body = task.result_file.read().decode("utf-8")
    assert TOKEN_JAWNY in body
    assert TOKEN_UKRYTY not in body


@pytest.mark.django_db
def test_zadanie_eksportu_bez_uczelni_pomija_ukryte_statusy(autor_z_ukryta_praca):
    """Zadanie bez zapisanej uczelni (np. sprzed tej poprawki) nie może
    wypuścić ukrytych prac — wykluczamy wtedy statusy ukryte gdziekolwiek."""
    from bpp.tasks import generuj_eksport_autora

    task = AutorEksportTask.objects.create(autor=autor_z_ukryta_praca, format="bib")
    generuj_eksport_autora(str(task.pk))

    task.refresh_from_db()
    body = task.result_file.read().decode("utf-8")
    assert TOKEN_JAWNY in body
    assert TOKEN_UKRYTY not in body


@pytest.mark.django_db
def test_start_eksportu_redaktora_tez_pomija_ukryte_statusy(
    client, django_user_model, autor_z_ukryta_praca, uczelnia, mocker
):
    """Plik z zadania jest publiczny po UUID i współdzielony przez
    deduplikację — nawet start przez redaktora daje plik bez ukrytych prac."""
    from bpp.tasks import generuj_eksport_autora

    delay = mocker.patch("bpp.tasks.generuj_eksport_autora.delay")
    _zaloguj(client, django_user_model, "redaktor")
    url = reverse("bpp:autor_eksport_start", args=(autor_z_ukryta_praca.pk, "bib"))
    client.post(url)

    task = AutorEksportTask.objects.get()
    assert task.uczelnia == uczelnia
    delay.assert_called_once_with(str(task.pk))

    generuj_eksport_autora(str(task.pk))
    task.refresh_from_db()
    body = task.result_file.read().decode("utf-8")
    assert TOKEN_UKRYTY not in body


@pytest.mark.django_db
def test_start_eksportu_nie_reuzywa_zadania_innej_uczelni(
    client, django_user_model, autor_jan_kowalski, uczelnia, delay
):
    """Deduplikacja jest per uczelnia — statusy ukryte są ustawiane per
    uczelnia, więc plik zbudowany pod regułami innej uczelni nie może być
    oddany oglądającemu z tej."""
    inna = baker.make(Uczelnia, skrot="IN", nazwa="Inna uczelnia")
    obcy = AutorEksportTask.objects.create(
        autor=autor_jan_kowalski, format="bib", uczelnia=inna
    )
    _zaloguj(client, django_user_model, "zwykly")
    url = reverse("bpp:autor_eksport_start", args=(autor_jan_kowalski.pk, "bib"))
    res = client.post(url)

    nowy = AutorEksportTask.objects.exclude(pk=obcy.pk).get()
    assert nowy.uczelnia == uczelnia
    assert res["Location"].endswith(
        reverse("bpp:autor_eksport_status", args=(nowy.pk,))
    )
