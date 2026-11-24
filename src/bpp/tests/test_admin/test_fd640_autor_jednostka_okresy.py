"""FD#640 / GlitchTip BPP-1A: nakładające się okresy pracy w adminie autora.

Dodanie w „Powiązaniach autor-jednostka” nowego okresu w tej samej
jednostce, gdy poprzedni nie ma daty zakończenia, kończyło się błędem 500
(``bpp_autor_jednostka_okresy_bez_nakladan``) — i przepadała cała edycja
autora, np. usunięcie dyscypliny, którą chciała zdjąć biblioteka. Teraz to
zwykły błąd formularza z podpowiedzią, co poprawić.
"""

import datetime

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Dyscyplina, Autor_Jednostka

KOMUNIKAT = "nakładają się"


def _formularz_autora(app, autor):
    res = app.get(reverse("admin:bpp_autor_change", args=(autor.pk,)))
    return res.forms["autor_form"]


def _indeks_nowego(form):
    return int(form["autor_jednostka_set-INITIAL_FORMS"].value)


@pytest.fixture
def autor_z_okresem(jednostka):
    autor = baker.make(Autor, nazwisko="Kowalczyk", imiona="Anna")
    Autor_Jednostka.objects.create(
        autor=autor, jednostka=jednostka, rozpoczal_prace=datetime.date(2022, 10, 1)
    )
    return autor


@pytest.mark.django_db
def test_nakladajacy_sie_okres_to_blad_formularza_nie_500(
    admin_app, uczelnia, jednostka, autor_z_okresem
):
    form = _formularz_autora(admin_app, autor_z_okresem)
    i = _indeks_nowego(form)
    form[f"autor_jednostka_set-{i}-jednostka"].force_value(jednostka.pk)
    form[f"autor_jednostka_set-{i}-rozpoczal_prace"] = "2026-10-01"

    res = form.submit(expect_errors=True)

    assert res.status_code == 200
    assert KOMUNIKAT in res.text
    assert "Zakończył pracę" in res.text
    assert Autor_Jednostka.objects.filter(autor=autor_z_okresem).count() == 1


@pytest.mark.django_db
def test_nowy_okres_po_zamknieciu_poprzedniego_przechodzi(
    admin_app, uczelnia, jednostka, autor_z_okresem
):
    """Strażnik: legalne „przeniesienie” — zamknięcie starego okresu i nowy
    okres od następnego dnia w jednym zapisie."""
    form = _formularz_autora(admin_app, autor_z_okresem)
    form["autor_jednostka_set-0-zakonczyl_prace"] = "2026-09-30"
    i = _indeks_nowego(form)
    form[f"autor_jednostka_set-{i}-jednostka"].force_value(jednostka.pk)
    form[f"autor_jednostka_set-{i}-rozpoczal_prace"] = "2026-10-01"

    res = form.submit()

    assert res.status_code == 302
    assert Autor_Jednostka.objects.filter(autor=autor_z_okresem).count() == 2


@pytest.mark.django_db
def test_okres_w_innej_jednostce_przechodzi(
    admin_app, uczelnia, druga_jednostka, autor_z_okresem
):
    form = _formularz_autora(admin_app, autor_z_okresem)
    i = _indeks_nowego(form)
    form[f"autor_jednostka_set-{i}-jednostka"].force_value(druga_jednostka.pk)
    form[f"autor_jednostka_set-{i}-rozpoczal_prace"] = "2026-10-01"

    assert form.submit().status_code == 302


@pytest.mark.django_db
def test_usuniecie_dyscypliny_autorowi_obcemu(
    admin_app, uczelnia, obca_jednostka, dyscyplina1
):
    """Strażnik: dyscyplinę dopiętą autorowi obcemu da się zdjąć w adminie
    autora („Usunąć?” przy powiązaniu autor-dyscyplina)."""
    autor = baker.make(Autor, nazwisko="Markiewicz", imiona="Włodzimierz")
    Autor_Jednostka.objects.create(autor=autor, jednostka=obca_jednostka)
    Autor_Dyscyplina.objects.create(autor=autor, rok=2026, dyscyplina_naukowa=dyscyplina1)

    form = _formularz_autora(admin_app, autor)
    form["autor_dyscyplina_set-0-DELETE"] = True

    assert form.submit().status_code == 302
    assert not Autor_Dyscyplina.objects.filter(autor=autor).exists()
