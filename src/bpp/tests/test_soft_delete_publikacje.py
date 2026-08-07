"""Soft-delete PUBLIKACJI (faza 02).

Testy wąskiej, kontrolowanej kaskady `publikacja -> *_Autor` pod wspólnym
`transaction_id`, bez refleksyjnej kaskady pakietu `django-soft-delete`
(która ruszyłaby `*_Streszczenie` i inne nie-soft dzieci).
"""

import pytest
from model_bakery import baker

from bpp.models import (
    Patent,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
)

#: Wszystkie 5 modeli publikacji objętych fazą 02.
MODELE_PUBLIKACJI = [
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
    Patent,
    Praca_Doktorska,
    Praca_Habilitacyjna,
]


@pytest.mark.django_db
def test_soft_delete_publikacji_kaskaduje_na_autor_wspolny_txid():
    wc = baker.make(Wydawnictwo_Ciagle)
    # `kolejnosc` JAWNIE różna. Bez tego `baker` nadaje obu wierszom 0, co
    # łamie ograniczenie wykluczające `wc_autor_excl_rekord_kolejnosc`
    # (faza 01). Ograniczenie jest DEFERRABLE i warunkowane
    # `deleted_at IS NULL`, więc soft-delete wyprowadzał oba wiersze poza
    # jego zakres, zanim zdążyło zadziałać przy COMMIT — test przechodził
    # wtedy CZĘŚCIOWO z powodu efektu ubocznego, a nie samej kaskady.
    a1 = baker.make(Wydawnictwo_Ciagle_Autor, rekord=wc, kolejnosc=0)
    a2 = baker.make(Wydawnictwo_Ciagle_Autor, rekord=wc, kolejnosc=1)

    wc.delete()

    wc.refresh_from_db()
    assert wc.deleted_at is not None
    assert wc.transaction_id is not None

    for a in (a1, a2):
        row = Wydawnictwo_Ciagle_Autor.global_objects.get(pk=a.pk)
        assert row.deleted_at is not None, "autorstwo nie zostało soft-skasowane"
        assert row.transaction_id == wc.transaction_id, "różny transaction_id"


# --- Task 4: przeplecenie menedżerów ------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("klasa", MODELE_PUBLIKACJI)
def test_objects_ukrywa_skasowane_global_widzi(klasa):
    """``objects`` musi ukrywać kosz na WSZYSTKICH pięciu modelach.

    Do fazy 02 ``Wydawnictwo_Ciagle`` i ``Wydawnictwo_Zwarte`` miały własne
    menedżery (mixin opłat + goły ``models.Manager``), które przesłaniały
    menedżer wniesiony przez ``BppPublikacjaSoftDeleteMixin`` — i NIE
    filtrowały ``deleted_at``. Pozostałe trzy modele dostawały filtr
    „z urodzenia". Ta asymetria była niewidoczna, dopóki nie sprawdzono jej
    wprost: żaden wcześniejszy test fazy 02 na nią nie trafiał, bo wszystkie
    szły przez widoki albo przez surowy SQL.
    """
    zywy = baker.make(klasa)
    kosz = baker.make(klasa)
    kosz.delete()

    widoczne = set(klasa.objects.values_list("pk", flat=True))
    assert zywy.pk in widoczne
    assert kosz.pk not in widoczne, (
        f"{klasa.__name__}.objects ({type(klasa.objects).__name__}) "
        f"NIE ukrywa skasowanych"
    )

    wszystkie = set(klasa.global_objects.values_list("pk", flat=True))
    assert kosz.pk in wszystkie, f"{klasa.__name__}.global_objects nie widzi kosza"

    skasowane = set(klasa.deleted_objects.values_list("pk", flat=True))
    assert skasowane == {kosz.pk} & skasowane and kosz.pk in skasowane, (
        f"{klasa.__name__}.deleted_objects nie zwraca skasowanego"
    )
    assert zywy.pk not in skasowane, (
        f"{klasa.__name__}.deleted_objects zwraca ŻYWY rekord"
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "klasa", [Wydawnictwo_Ciagle, Wydawnictwo_Zwarte], ids=["ciagle", "zwarte"]
)
def test_metoda_oplat_zachowana_i_tez_filtruje(klasa):
    """``rekordy_z_oplata()`` (mixin opłat) ma DALEJ działać po przepleceniu
    menedżerów — i sama z siebie pomijać kosz.

    To jest sedno Taska 4: filtr soft-delete i metody opłat muszą współżyć
    bez nadpisywania tych drugich. ``ManagerModeliZOplataZaPublikacjeMixin``
    woła ``self.exclude(...)``, więc działa nad KAŻDYM querysetem — o ile
    stoi w MRO PRZED menedżerem dostarczającym queryset.
    """
    zywy = baker.make(klasa, opl_pub_cost_free=True)
    kosz = baker.make(klasa, opl_pub_cost_free=True)
    kosz.delete()

    z_oplata = set(klasa.objects.rekordy_z_oplata().values_list("pk", flat=True))
    assert zywy.pk in z_oplata, "rekordy_z_oplata() zgubiło żywy rekord"
    assert kosz.pk not in z_oplata, "rekordy_z_oplata() pokazuje kosz"


@pytest.mark.django_db
def test_wydawnictwa_nadrzedne_dla_innych_zachowane():
    """Druga metoda menedżera ``Wydawnictwo_Zwarte`` przeżywa przeplecenie."""
    matka = baker.make(Wydawnictwo_Zwarte)
    baker.make(Wydawnictwo_Zwarte, wydawnictwo_nadrzedne=matka)

    nadrzedne = set(Wydawnictwo_Zwarte.objects.wydawnictwa_nadrzedne_dla_innych())
    assert matka.pk in nadrzedne
