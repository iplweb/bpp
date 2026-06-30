"""Testy komendy `zaloz_jednostki_domyslne`."""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from model_bakery import baker

from bpp.models import Autor_Jednostka, Jednostka


@pytest.mark.django_db
def test_zaloz_jednostki_domyslne_happy(uczelnia, wydzial):
    """Puste jednostki znikają, zostaje jedna domyślna na wydział."""
    baker.make(Jednostka, uczelnia=uczelnia, wydzial=wydzial)
    baker.make(Jednostka, uczelnia=uczelnia, wydzial=wydzial)

    call_command("zaloz_jednostki_domyslne", uczelnia.skrot)

    jednostki = Jednostka.objects.filter(uczelnia=uczelnia, wydzial=wydzial)
    assert jednostki.count() == 1
    assert jednostki.get().nazwa == f"Jednostka Domyślna - {wydzial.nazwa}"


@pytest.mark.django_db
def test_niepusta_jednostka_blokuje_i_nic_nie_kasuje(uczelnia, wydzial):
    """Jednostka z zatrudnieniem → CommandError, stan bazy nietknięty."""
    jednostka = baker.make(Jednostka, uczelnia=uczelnia, wydzial=wydzial)
    baker.make(Autor_Jednostka, jednostka=jednostka)

    with pytest.raises(CommandError):
        call_command("zaloz_jednostki_domyslne", uczelnia.skrot)

    assert Jednostka.objects.filter(pk=jednostka.pk).exists()
    # nie powstała żadna jednostka domyślna
    assert not Jednostka.objects.filter(
        nazwa__startswith="Jednostka Domyślna - "
    ).exists()


@pytest.mark.django_db
def test_dry_run_niczego_nie_zmienia(uczelnia, wydzial):
    """--dry-run pokazuje plan, ale nie zapisuje zmian."""
    baker.make(Jednostka, uczelnia=uczelnia, wydzial=wydzial)
    baker.make(Jednostka, uczelnia=uczelnia, wydzial=wydzial)
    przed = set(
        Jednostka.objects.filter(uczelnia=uczelnia).values_list("pk", flat=True)
    )

    call_command("zaloz_jednostki_domyslne", uczelnia.skrot, "--dry-run")

    po = set(Jednostka.objects.filter(uczelnia=uczelnia).values_list("pk", flat=True))
    assert po == przed
    assert not Jednostka.objects.filter(
        nazwa__startswith="Jednostka Domyślna - "
    ).exists()


@pytest.mark.django_db
def test_uczelnia_bez_wydzialow(uczelnia):
    """Uczelnia bez wydziałów → czytelny błąd."""
    with pytest.raises(CommandError):
        call_command("zaloz_jednostki_domyslne", uczelnia.skrot)
