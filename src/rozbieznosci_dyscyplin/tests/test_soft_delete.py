"""Raport rozbieżności dyscyplin źródeł a soft-delete autorstw.

``rozbieznosci_dyscyplin_rozbieznoscizrodelview`` (migracja 0017, przeładowana
przez 0018/0019/0020) czyta SUROWĄ tabelę ``bpp_wydawnictwo_ciagle_autor``.
Bez filtra ``deleted_at IS NULL`` raport pokazuje rozbieżności dyscyplin dla
autorstw, których w systemie już nie ma — a użytkownik nie ma jak ich
„naprawić", bo w interfejsie nie istnieją.
"""

import pytest
from django.db import connection
from model_bakery import baker

from bpp.models import Dyscyplina_Zrodla, Wydawnictwo_Ciagle
from rozbieznosci_dyscyplin.models import RozbieznosciZrodelView


@pytest.fixture
def rozbieznosc_zrodla(
    autor_z_dyscyplina,
    rok,
    zrodlo,
    dyscyplina1,
    dyscyplina2,
    jednostka,
    typy_odpowiedzialnosci,
):
    """Autorstwo z dyscypliną SPOZA listy dyscyplin źródła — czyli dokładnie
    to, co raportuje ``RozbieznosciZrodelView``."""
    Dyscyplina_Zrodla.objects.create(rok=rok, zrodlo=zrodlo, dyscyplina=dyscyplina2)
    wc = baker.make(Wydawnictwo_Ciagle, rok=rok, zrodlo=zrodlo)
    return wc.dodaj_autora(
        autor_z_dyscyplina.autor, jednostka, dyscyplina_naukowa=dyscyplina1
    )


@pytest.mark.django_db
def test_rozbieznosci_zrodel_pomijaja_soft_deletowane(rozbieznosc_zrodla):
    """Wyrocznia: bez ``deleted_at IS NULL`` w definicji widoku druga
    asercja by padła — skasowane autorstwo dalej generowałoby wiersz
    raportu."""
    assert RozbieznosciZrodelView.objects.filter(
        autor_id=rozbieznosc_zrodla.autor_id
    ).exists()

    rozbieznosc_zrodla.delete()  # soft-delete

    assert not RozbieznosciZrodelView.objects.filter(
        autor_id=rozbieznosc_zrodla.autor_id
    ).exists()


@pytest.mark.django_db
def test_rozbieznosci_zrodel_pomijaja_soft_deletowana_publikacje(rozbieznosc_zrodla):
    """Wymiar PUBLIKACJI (faza 02, migracja 0023 tej aplikacji).

    ⚠️ Kasujemy publikację SUROWYM UPDATE-em, nie ``rekord.delete()``, i jest
    to celowe: ``delete()`` kaskaduje na autorstwa, więc wiersz raportu
    zniknąłby z DWÓCH niezależnych powodów — przez filtr publikacji (to, co
    ten test sprawdza) ORAZ przez filtr autorstwa z migracji ``0022``. Test
    przechodziłby wtedy nawet po cofnięciu ``0023``, czyli nie byłby
    wyrocznią niczego.
    """
    autor_id = rozbieznosc_zrodla.autor_id
    assert RozbieznosciZrodelView.objects.filter(autor_id=autor_id).exists()

    with connection.cursor() as cur:
        cur.execute(
            "UPDATE bpp_wydawnictwo_ciagle SET deleted_at = now() WHERE id = %s",
            [rozbieznosc_zrodla.rekord_id],
        )

    assert not RozbieznosciZrodelView.objects.filter(autor_id=autor_id).exists(), (
        "soft-skasowana publikacja dalej generuje wiersz raportu rozbieznosci"
    )
