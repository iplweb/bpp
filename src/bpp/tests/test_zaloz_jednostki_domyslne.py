"""Testy komendy `zaloz_jednostki_domyslne`."""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from model_bakery import baker

from bpp.models import Autor_Jednostka, Jednostka


@pytest.fixture
def wydzial_root(uczelnia):
    # Faza C (#438): „wydział" = jednostka top-level (parent IS NULL); jednostki
    # wiszą pod nim, a ich denorm ``wydzial`` (korzeń) wskazuje ten root.
    return baker.make(
        Jednostka,
        uczelnia=uczelnia,
        parent=None,
        nazwa="Wydział Testowy",
        skrot="WT",
    )


@pytest.mark.django_db
def test_zaloz_jednostki_domyslne_happy(uczelnia, wydzial_root):
    """Puste jednostki znikają, zostaje jedna domyślna na wydział."""
    baker.make(Jednostka, uczelnia=uczelnia, parent=wydzial_root)
    baker.make(Jednostka, uczelnia=uczelnia, parent=wydzial_root)

    call_command("zaloz_jednostki_domyslne", uczelnia.skrot)

    jednostki = Jednostka.objects.filter(uczelnia=uczelnia, wydzial=wydzial_root)
    assert jednostki.count() == 1
    assert jednostki.get().nazwa == f"Jednostka Domyślna - {wydzial_root.nazwa}"


@pytest.mark.django_db
def test_niepusta_jednostka_blokuje_i_nic_nie_kasuje(uczelnia, wydzial_root):
    """Jednostka z zatrudnieniem → CommandError, stan bazy nietknięty."""
    jednostka = baker.make(Jednostka, uczelnia=uczelnia, parent=wydzial_root)
    baker.make(Autor_Jednostka, jednostka=jednostka)

    with pytest.raises(CommandError):
        call_command("zaloz_jednostki_domyslne", uczelnia.skrot)

    assert Jednostka.objects.filter(pk=jednostka.pk).exists()
    # nie powstała żadna jednostka domyślna
    assert not Jednostka.objects.filter(
        nazwa__startswith="Jednostka Domyślna - "
    ).exists()


@pytest.mark.django_db
def test_dry_run_niczego_nie_zmienia(uczelnia, wydzial_root):
    """--dry-run pokazuje plan, ale nie zapisuje zmian."""
    baker.make(Jednostka, uczelnia=uczelnia, parent=wydzial_root)
    baker.make(Jednostka, uczelnia=uczelnia, parent=wydzial_root)
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
