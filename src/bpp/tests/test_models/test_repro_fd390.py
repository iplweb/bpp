"""Repro FD#390 — trigger aktualna_jednostka: prawdziwa jednostka bije obcą.

Multi-homed, wspólna baza: jeden Autor bywa przypięty do jednostek w RÓŻNYCH
uczelniach. Klasyczny przypadek: autor jest pracownikiem uczelni A (przypięty
do jej „Jednostki Domyślnej", skupia_pracownikow=True), a przy okazji importu
publikacji uczelni B trafił do jej „Obcej jednostki" (skupia_pracownikow=False).

Bug: trigger wybierający ``aktualna_jednostka`` sortował m.in. po ``id DESC``,
więc gdy obca jednostka B miała wyższe ID (utworzona później), to ONA stawała
się aktualną → na stronie uczelni A autor „pokazywał się jako z obcej uczelni",
edycja 404 itd.

Fix: trigger demotuje obcą jednostkę (``skupia_pracownikow=False``) — realna
jednostka pracownicza zawsze wygrywa jako ``aktualna_jednostka``.
"""

import pytest
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka, Uczelnia


@pytest.mark.django_db
def test_repro_fd390_trigger_realna_jednostka_bije_obca():
    uczelnia_a = baker.make(Uczelnia)
    uczelnia_b = baker.make(Uczelnia)

    jednostka_realna = baker.make(
        Jednostka, uczelnia=uczelnia_a, wydzial=None, skupia_pracownikow=True
    )
    obca_jednostka = baker.make(
        Jednostka, uczelnia=uczelnia_b, wydzial=None, skupia_pracownikow=False
    )

    autor = baker.make(Autor)

    # Kolejność wstawiania: NAJPIERW realna, POTEM obca — obca dostaje wyższe
    # ID. Bez fixu trigger wybrałby obcą (id DESC). Oba wpisy bez dat,
    # bez „podstawowe miejsce pracy".
    Autor_Jednostka.objects.create(autor=autor, jednostka=jednostka_realna)
    Autor_Jednostka.objects.create(autor=autor, jednostka=obca_jednostka)

    autor.refresh_from_db()
    assert autor.aktualna_jednostka_id == jednostka_realna.pk, (
        "Trigger powinien wybrać realną jednostkę pracowniczą, nie obcą — "
        f"wybrał {autor.aktualna_jednostka_id} "
        f"(realna={jednostka_realna.pk}, obca={obca_jednostka.pk})."
    )


@pytest.mark.django_db
def test_repro_fd390_trigger_sam_obca_pozostaje_aktualna():
    """Regresja: autor przypięty WYŁĄCZNIE do obcej jednostki nadal ma ją jako
    aktualną (demotowanie działa tylko przy konflikcie z realną)."""
    uczelnia_b = baker.make(Uczelnia)
    obca_jednostka = baker.make(
        Jednostka, uczelnia=uczelnia_b, wydzial=None, skupia_pracownikow=False
    )
    autor = baker.make(Autor)
    Autor_Jednostka.objects.create(autor=autor, jednostka=obca_jednostka)

    autor.refresh_from_db()
    assert autor.aktualna_jednostka_id == obca_jednostka.pk
