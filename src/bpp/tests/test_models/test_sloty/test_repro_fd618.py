"""Repro FD#618 (z FD#610) — √(k/m) i k/m zaokrąglane do 4 miejsc PRZED mnożeniem.

Rozporządzenie w sprawie ewaluacji jakości działalności naukowej (t.j. Dz.U.
2026 poz. 1346), § 13 ust. 6: „Wartości liczb √k/m i k/m ustala się
z dokładnością do czterech miejsc po przecinku.” Dopiero tak ustaloną wartość
mnoży się przez całkowitą wartość punktową (§ 13 ust. 1, 3 i 5).

Przykład z FD#610 (APOŻ): redakcja monografii za 20 pkt (wydawca poziomu 1),
6 redaktorów, z czego 1 z danej dyscypliny: √(1/6) = 0,4082, więc
P = 20 × 0,4082 = 8,1640 pkt. Wcześniej BPP mnożył niezaokrąglony pierwiastek
i pokazywał 8,1650.
"""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from bpp.models import Autor_Dyscyplina
from bpp.models.sloty.common import SlotMixin, zaokraglij_do_4_miejsc
from bpp.models.sloty.core import IPunktacjaCacher, ISlot
from bpp.models.sloty.wydawnictwo_ciagle import (
    SlotKalkulator_Wydawnictwo_Ciagle_Prog2,
    SlotKalkulator_Wydawnictwo_Ciagle_Prog3,
)
from bpp.models.sloty.wydawnictwo_zwarte import (
    SlotKalkulator_Wydawnictwo_Zwarte_Prog2,
)


class _KalkulatorKM(SlotMixin):
    """SlotMixin z podstawionymi k i m — bez bazy danych."""

    def __init__(self, k, m):
        super().__init__(original=None)
        self._k = k
        self._m = m

    def wszyscy(self):
        return self._m

    def liczba_k(self, dyscyplina):
        return self._k


@pytest.mark.parametrize(
    "k,m,pierwiastek,k_przez_m",
    [
        (1, 6, "0.4082", "0.1667"),  # FD#610: √0,1666… = 0,40824…
        (1, 2, "0.7071", "0.5000"),
        (1, 3, "0.5774", "0.3333"),
        (2, 3, "0.8165", "0.6667"),
        (3, 3, "1.0000", "1.0000"),  # k = m
        (1, 1, "1.0000", "1.0000"),  # k = m, jeden autor
        (0, 5, "0.0000", "0.0000"),
        (1, 101, "0.0995", "0.0099"),  # poniżej progu 10% (minimum osobno)
        (1, 160, "0.0791", "0.0063"),  # 0,00625 → 0,0063 (połówka w górę)
    ],
)
def test_fd618_wartosci_zaokraglone_do_4_miejsc(k, m, pierwiastek, k_przez_m):
    kalk = _KalkulatorKM(k, m)

    p = kalk.pierwiastek_k_przez_m(None)
    km = kalk.k_przez_m(None)

    assert isinstance(p, Decimal)
    assert isinstance(km, Decimal)
    # Porównanie napisów sprawdza też, że jest DOKŁADNIE 4 miejsca po przecinku.
    assert str(p) == pierwiastek
    assert str(km) == k_przez_m


def test_fd618_brak_autorow_zwraca_none():
    kalk = _KalkulatorKM(0, 0)
    assert kalk.pierwiastek_k_przez_m(None) is None
    assert kalk.k_przez_m(None) is None


@pytest.mark.parametrize(
    "wartosc,oczekiwana",
    [
        ("0.00625", "0.0063"),
        ("0.00635", "0.0064"),  # ROUND_HALF_UP, nie „bankierskie”
        ("0.40824829", "0.4082"),
        ("0.99995", "1.0000"),
    ],
)
def test_fd618_zaokraglanie_polowek_w_gore(wartosc, oczekiwana):
    assert str(zaokraglij_do_4_miejsc(Decimal(wartosc))) == oczekiwana


def _dopisz_obcych(rekord, autor_maker, jednostka, ile, skrot):
    for n in range(ile):
        rekord.dodaj_autora(
            autor_maker(imiona="Obcy", nazwisko=f"Redaktor{n}"),
            jednostka,
            typ_odpowiedzialnosci_skrot=skrot,
            afiliuje=False,
        )


@pytest.mark.django_db
def test_fd618_redakcja_monografii_20_pkt_k1_m6(
    zwarte_z_dyscyplinami,
    autor_maker,
    jednostka,
    dyscyplina1,
    dyscyplina2,
    typ_odpowiedzialnosci_redaktor,
    rok,
):
    """Odtworzenie FD#610: 20 × √(1/6) = 20 × 0,4082 = 8,1640 (było 8,1650)."""
    rekord = zwarte_z_dyscyplinami
    rekord.wydawca.poziom_wydawcy_set.create(rok=rok, poziom=1)
    rekord.punkty_kbn = 20
    rekord.save()

    for wza in rekord.autorzy_set.all():
        wza.typ_odpowiedzialnosci = typ_odpowiedzialnosci_redaktor
        wza.save()

    # 4 redaktorów spoza uczelni: m = 6, k = 1 w każdej z dwóch dyscyplin.
    _dopisz_obcych(rekord, autor_maker, jednostka, 4, "red.")

    kalk = ISlot(rekord)
    assert isinstance(kalk, SlotKalkulator_Wydawnictwo_Zwarte_Prog2)
    assert kalk.wszyscy() == 6

    for dyscyplina in (dyscyplina1, dyscyplina2):
        assert kalk.punkty_pkd(dyscyplina) == Decimal("8.1640")
        assert kalk.slot_dla_dyscypliny(dyscyplina) == Decimal("0.4082")

    for wza in rekord.autorzy_set.filter(afiliuje=True):
        assert kalk.pkd_dla_autora(wza) == Decimal("8.1640")
        assert kalk.slot_dla_autora(wza) == Decimal("0.4082")

    # To samo musi trafić do zapisanych wartości (cache punktacji).
    cacher = IPunktacjaCacher(rekord)
    cacher.rebuildEntries()
    cpd = cacher.cache_punktacja_dyscypliny
    assert {(c.pkd, c.slot) for c in cpd} == {(Decimal("8.1640"), Decimal("0.4082"))}
    cpa = cacher.cache_punktacja_autora
    assert cpa.count() == 2
    assert {(c.pkdaut, c.slot) for c in cpa} == {
        (Decimal("8.1640"), Decimal("0.4082"))
    }


def _ciagle_jedna_dyscyplina(ciagle, rok_rekordu, punkty, rok, autor_jan_kowalski):
    """Artykuł, w którym obaj autorzy fixture'a są z tej samej dyscypliny."""
    ciagle.rok = rok_rekordu
    ciagle.punkty_kbn = punkty
    ciagle.save()
    for wca in ciagle.autorzy_set.all():
        ad = wca.autor.autor_dyscyplina_set.get(rok=rok)
        ad.pk = None
        ad.rok = rok_rekordu
        ad.save()
    # Kowalski przechodzi do dyscypliny Nowaka (dyscyplina1).
    wca = ciagle.autorzy_set.get(autor=autor_jan_kowalski)
    nowak = ciagle.autorzy_set.exclude(autor=autor_jan_kowalski).get()
    Autor_Dyscyplina.objects.filter(autor=autor_jan_kowalski, rok=rok_rekordu).update(
        dyscyplina_naukowa=nowak.dyscyplina_naukowa
    )
    wca.dyscyplina_naukowa = nowak.dyscyplina_naukowa
    wca.save()


@pytest.mark.django_db
def test_fd618_artykul_70_pkt_k_rowne_m(
    ciagle_z_dyscyplinami, dyscyplina1, rok, autor_jan_kowalski
):
    """k = m: √1 = 1,0000 — pełne punkty, bez zmian względem starego kodu."""
    _ciagle_jedna_dyscyplina(ciagle_z_dyscyplinami, 2022, 70, rok, autor_jan_kowalski)

    kalk = ISlot(ciagle_z_dyscyplinami)
    assert isinstance(kalk, SlotKalkulator_Wydawnictwo_Ciagle_Prog2)
    assert kalk.punkty_pkd(dyscyplina1) == Decimal("70.0000")
    assert kalk.slot_dla_dyscypliny(dyscyplina1) == Decimal("1.0000")
    assert kalk.slot_dla_autora_z_dyscypliny(dyscyplina1) == Decimal("0.5000")


@pytest.mark.django_db
def test_fd618_artykul_70_pkt_k1_m2(ciagle_z_dyscyplinami, dyscyplina1, rok):
    """70 × 0,7071 = 49,4970 (wcześniej 70 × 0,70710678… = 49,4975)."""
    ciagle_z_dyscyplinami.rok = 2022
    ciagle_z_dyscyplinami.punkty_kbn = 70
    ciagle_z_dyscyplinami.save()
    for wca in ciagle_z_dyscyplinami.autorzy_set.all():
        ad = wca.autor.autor_dyscyplina_set.get(rok=rok)
        ad.pk = None
        ad.rok = 2022
        ad.save()

    kalk = ISlot(ciagle_z_dyscyplinami)
    assert kalk.punkty_pkd(dyscyplina1) == Decimal("49.4970")
    assert kalk.slot_dla_dyscypliny(dyscyplina1) == Decimal("0.7071")


@pytest.mark.django_db
def test_fd618_artykul_20_pkt_k2_m3(
    ciagle_z_dyscyplinami, dyscyplina1, rok, autor_jan_kowalski, autor_maker, jednostka
):
    """Wzór k/m (20 pkt): k/m = 0,6667 → P = 13,3340 (wcześniej 13,3333).

    Udział jednostkowy U = P/Pc × 1/k = 0,6667 / 2 = 0,33335 → 0,3334
    po zapisie (§ 16 ust. 2 i 3); wcześniej 1/m = 0,3333.
    """
    _ciagle_jedna_dyscyplina(ciagle_z_dyscyplinami, 2022, 20, rok, autor_jan_kowalski)
    _dopisz_obcych(ciagle_z_dyscyplinami, autor_maker, jednostka, 1, "aut.")

    kalk = ISlot(ciagle_z_dyscyplinami)
    assert isinstance(kalk, SlotKalkulator_Wydawnictwo_Ciagle_Prog3)
    assert kalk.wszyscy() == 3
    assert kalk.punkty_pkd(dyscyplina1) == Decimal("13.3340")
    assert kalk.slot_dla_dyscypliny(dyscyplina1) == Decimal("0.6667")

    cacher = IPunktacjaCacher(ciagle_z_dyscyplinami)
    cacher.rebuildEntries()
    cpa = cacher.cache_punktacja_autora
    assert {(c.pkdaut, c.slot) for c in cpa} == {
        (Decimal("6.6670"), Decimal("0.3334"))
    }


@pytest.mark.django_db
def test_fd618_minimum_10_procent_k_przez_m(
    ciagle_z_dyscyplinami, dyscyplina1, rok, autor_maker, jednostka
):
    """k/m = 1/12 = 0,0833 < 0,1 → P = 10% × 20 = 2,0000, slot 0,1000.

    Slot (udział jednostkowy, § 16 ust. 2: U = P/Pc × 1/k) wynika z punktów
    podniesionych do minimum — wcześniej BPP dawał tu slot 0,0833."""
    ciagle_z_dyscyplinami.rok = 2022
    ciagle_z_dyscyplinami.punkty_kbn = 20
    ciagle_z_dyscyplinami.save()
    for wca in ciagle_z_dyscyplinami.autorzy_set.all():
        ad = wca.autor.autor_dyscyplina_set.get(rok=rok)
        ad.pk = None
        ad.rok = 2022
        ad.save()
    _dopisz_obcych(ciagle_z_dyscyplinami, autor_maker, jednostka, 10, "aut.")

    kalk = ISlot(ciagle_z_dyscyplinami)
    assert kalk.wszyscy() == 12
    assert kalk.k_przez_m(dyscyplina1) == Decimal("0.0833")
    assert kalk.punkty_pkd(dyscyplina1) == Decimal("2.0")
    assert kalk.slot_dla_dyscypliny(dyscyplina1) == Decimal("0.1")
    assert kalk.slot_dla_autora_z_dyscypliny(dyscyplina1) == Decimal("0.1")

    cacher = IPunktacjaCacher(ciagle_z_dyscyplinami)
    cacher.rebuildEntries()
    cpd = cacher.cache_punktacja_dyscypliny.get(dyscyplina=dyscyplina1)
    assert (cpd.pkd, cpd.slot) == (Decimal("2.0000"), Decimal("0.1000"))


@pytest.mark.django_db
def test_fd618_minimum_10_procent_pierwiastek_k1_m150(
    ciagle_z_dyscyplinami, dyscyplina1, rok, autor_maker, jednostka
):
    """Artykuł 70 pkt, k = 1, m = 150: √(1/150) = 0,0816 < 0,1
    → P = 7,0000 (10% × 70), slot dyscypliny i autora 0,1000 (było 0,0816)."""
    ciagle_z_dyscyplinami.rok = 2022
    ciagle_z_dyscyplinami.punkty_kbn = 70
    ciagle_z_dyscyplinami.save()
    for wca in ciagle_z_dyscyplinami.autorzy_set.all():
        ad = wca.autor.autor_dyscyplina_set.get(rok=rok)
        ad.pk = None
        ad.rok = 2022
        ad.save()
    _dopisz_obcych(ciagle_z_dyscyplinami, autor_maker, jednostka, 148, "aut.")

    kalk = ISlot(ciagle_z_dyscyplinami)
    assert isinstance(kalk, SlotKalkulator_Wydawnictwo_Ciagle_Prog2)
    assert kalk.wszyscy() == 150
    assert kalk.pierwiastek_k_przez_m(dyscyplina1) == Decimal("0.0816")

    cacher = IPunktacjaCacher(ciagle_z_dyscyplinami)
    cacher.rebuildEntries()
    cpd = cacher.cache_punktacja_dyscypliny.get(dyscyplina=dyscyplina1)
    assert (cpd.pkd, cpd.slot) == (Decimal("7.0000"), Decimal("0.1000"))
    cpa = cacher.cache_punktacja_autora.get(dyscyplina=dyscyplina1)
    assert (cpa.pkdaut, cpa.slot) == (Decimal("7.0000"), Decimal("0.1000"))


class _Prog2KM(SlotKalkulator_Wydawnictwo_Ciagle_Prog2, _KalkulatorKM):
    def __init__(self, k, m, punkty):
        _KalkulatorKM.__init__(self, k, m)
        self.original = SimpleNamespace(punkty_kbn=Decimal(punkty))

    def ma_dyscypline(self, dyscyplina):
        return True


class _Prog3KM(SlotKalkulator_Wydawnictwo_Ciagle_Prog3, _Prog2KM):
    pass


@pytest.mark.parametrize(
    "klass,k,m,punkty,pkd,slot_d,slot_aut",
    [
        # √(k/m) poniżej progu, k > 1: P = 10%, slot 0,1 na dyscyplinę, 0,1/k
        (_Prog2KM, 2, 500, 70, "7.0000", "0.1000", "0.0500"),
        (_Prog2KM, 1, 150, 40, "4.0000", "0.1000", "0.1000"),
        # √(1/100) = 0,1 — dokładnie na progu
        (_Prog2KM, 1, 100, 70, "7.0000", "0.1000", "0.1000"),
        # powyżej progu — bez zmian
        (_Prog2KM, 1, 6, 20, "8.1640", "0.4082", "0.4082"),
        # k/m poniżej progu (k > 1): 3/40 = 0,075
        (_Prog3KM, 3, 40, 20, "2.0000", "0.1000", "0.0333"),
        (_Prog3KM, 1, 12, 5, "0.5000", "0.1000", "0.1000"),
        # k/m powyżej progu — bez zmian
        (_Prog3KM, 2, 3, 20, "13.3340", "0.6667", "0.3334"),
        # brak autorów z dyscypliny (k = 0): 0, bez minimum
        (_Prog3KM, 0, 12, 20, "0", "0.0000", None),
        (_Prog2KM, 0, 150, 70, "0", "0.0000", None),
    ],
)
def test_fd618_minimum_10_procent_sloty(
    klass, k, m, punkty, pkd, slot_d, slot_aut
):
    kalk = klass(k, m, punkty)

    def q(v):
        return None if v is None else zaokraglij_do_4_miejsc(v)

    assert q(kalk.punkty_pkd(None)) == Decimal(pkd)
    assert q(kalk.slot_dla_dyscypliny(None)) == Decimal(slot_d)
    if slot_aut is None:
        assert kalk.slot_dla_autora_z_dyscypliny(None) is None
    else:
        assert q(kalk.slot_dla_autora_z_dyscypliny(None)) == Decimal(slot_aut)


@pytest.mark.django_db
def test_fd618_komenda_przelicza_zapisane_wartosci(
    ciagle_z_dyscyplinami, dyscyplina1, rok
):
    """Komenda ``przelicz_punktacje_dyscyplin`` poprawia stary cache (slot < 1)."""
    from io import StringIO

    from django.core.management import call_command

    ciagle_z_dyscyplinami.rok = 2022
    ciagle_z_dyscyplinami.punkty_kbn = 70
    ciagle_z_dyscyplinami.save()
    for wca in ciagle_z_dyscyplinami.autorzy_set.all():
        ad = wca.autor.autor_dyscyplina_set.get(rok=rok)
        ad.pk = None
        ad.rok = 2022
        ad.save()

    cacher = IPunktacjaCacher(ciagle_z_dyscyplinami)
    cacher.removeEntries()
    cacher.rebuildEntries()
    # Symulacja wartości zapisanych przez stary kod (bez zaokrąglenia √).
    cacher.cache_punktacja_dyscypliny.update(pkd=Decimal("49.4975"))
    cacher.cache_punktacja_autora.update(pkdaut=Decimal("49.4975"))

    out = StringIO()
    call_command("przelicz_punktacje_dyscyplin", "--dry-run", stdout=out)
    assert "Rekordów do przeliczenia: 1" in out.getvalue()
    assert {c.pkd for c in cacher.cache_punktacja_dyscypliny} == {Decimal("49.4975")}

    call_command("przelicz_punktacje_dyscyplin", stdout=StringIO())

    assert {c.pkd for c in cacher.cache_punktacja_dyscypliny} == {Decimal("49.4970")}
    assert {c.pkdaut for c in cacher.cache_punktacja_autora} == {Decimal("49.4970")}
    ciagle_z_dyscyplinami.refresh_from_db()
    assert "49.4970" in str(ciagle_z_dyscyplinami.cached_punkty_dyscyplin)

    # Rekord ze slotem 1 (100% punktów) nie jest wybierany domyślnie.
    ciagle_z_dyscyplinami.punkty_kbn = 100
    ciagle_z_dyscyplinami.save()
    cacher.removeEntries()
    cacher.rebuildEntries()
    out = StringIO()
    call_command("przelicz_punktacje_dyscyplin", "--dry-run", stdout=out)
    assert "Rekordów do przeliczenia: 0" in out.getvalue()
    out = StringIO()
    call_command(
        "przelicz_punktacje_dyscyplin", "--dry-run", "--wszystkie", stdout=out
    )
    assert "Rekordów do przeliczenia: 0" not in out.getvalue()
