"""FD#370: import CiteScore z eksportu źródeł Scopus.

Pliki testowe są budowane w testach (zmyślone tytuły) — w repo nie ma
żadnego prawdziwego eksportu.
"""

from decimal import Decimal

import openpyxl
import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Punktacja_Zrodla, Zrodlo
from import_common.core.zrodlo import kandydaci_zrodla
from import_punktacji_zrodel.core_scopus import (
    NiedozwolonyWybor,
    analyze_scopus_file,
    ustaw_wybor,
)
from import_punktacji_zrodel.models import (
    RODZAJ_SCOPUS,
    WYBOR_POMIN,
    ImportPunktacjiZrodel,
)
from import_punktacji_zrodel.parser_scopus import (
    parsuj_citescore,
    parsuj_issn,
    parsuj_percentyl,
    wczytaj_plik_scopus,
)

NAGLOWEK = [
    "Source title",
    "CiteScore",
    "Highest percentile",
    "2022-25 Citations",
    "2022-25 Documents",
    "% Cited",
    "SNIP",
    "SJR",
    "Publisher",
]
NAGLOWEK_ISSN = ["Source title", "Print-ISSN", "E-ISSN", *NAGLOWEK[1:]]


def _xlsx(tmp_path, wiersze, naglowek=NAGLOWEK, nazwa="scopus.xlsx"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(naglowek)
    for w in wiersze:
        ws.append(w)
    sciezka = tmp_path / nazwa
    wb.save(sciezka)
    return str(sciezka)


def _wiersz(tytul, citescore=7.3, percentyl="80.0%\n12/345\nTesting", snip=1.234):
    return [tytul, citescore, percentyl, 100.0, 10.0, 90.0, snip, 2.5, "Wydawca X"]


def _wiersz_issn(tytul, issn, e_issn, **kw):
    w = _wiersz(tytul, **kw)
    return [w[0], issn, e_issn, *w[1:]]


# --------------------------------------------------------------------------- #
# Parser                                                                       #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "komorka,oczekiwane",
    [
        ("99.0%\n1/428\nOncology", 99),
        ("74.5%\n3/10\nX", 75),
        ("74.4%\n3/10\nX", 74),
        ("0.0%\n10/10\nX", 0),
        ("100%", 100),
        ("87,6 %", 88),
        (87, 87),
        (87.4, 87),
        ("63", 63),
        ("101%", None),
        ("-5", None),
        ("brak", None),
        ("", None),
        (None, None),
    ],
)
def test_parsuj_percentyl(komorka, oczekiwane):
    assert parsuj_percentyl(komorka) == oczekiwane


def test_parsuj_citescore_i_issn():
    assert parsuj_citescore(649.84) == Decimal("649.8")
    assert parsuj_citescore("3,25") == Decimal("3.3")
    assert parsuj_citescore(-1) is None
    assert parsuj_citescore("N/A") is None
    # Excel gubi zera wiodące; pełna lista Scopus nie ma myślników.
    assert parsuj_issn(79235) == "00079235"
    assert parsuj_issn(79235.0) == "00079235"
    assert parsuj_issn("1234-567x") == "1234-567X"
    assert parsuj_issn(None) is None


def test_wczytaj_plik_bez_issn(tmp_path):
    sciezka = _xlsx(tmp_path, [_wiersz("Alpha Journal"), _wiersz("Beta Review", 0.0)])
    alpha, beta = wczytaj_plik_scopus(sciezka)
    assert alpha.nazwa == "Alpha Journal"
    assert alpha.citescore == Decimal("7.3")
    assert alpha.percentyl == 80
    assert alpha.snip == Decimal("1.234")
    assert alpha.wydawca == "Wydawca X"
    assert alpha.issn is None and alpha.e_issn is None
    assert beta.citescore == Decimal("0.0")


def test_wczytaj_plik_z_issn(tmp_path):
    sciezka = _xlsx(
        tmp_path,
        [_wiersz_issn("Alpha Journal", 12345678, "8765-432X")],
        naglowek=NAGLOWEK_ISSN,
    )
    (alpha,) = wczytaj_plik_scopus(sciezka)
    assert alpha.issn == "12345678"
    assert alpha.e_issn == "8765-432X"
    assert alpha.citescore == Decimal("7.3")


def test_wczytaj_plik_nie_scopus(tmp_path):
    sciezka = _xlsx(tmp_path, [["x", 1]], naglowek=["Journal name", "JIF Quartile"])
    with pytest.raises(ValueError, match="Source title"):
        wczytaj_plik_scopus(sciezka)


# --------------------------------------------------------------------------- #
# Dopasowanie i zapis                                                          #
# --------------------------------------------------------------------------- #


def _import(owner, sciezka, **kw):
    kw.setdefault("rok", 2025)
    op = baker.make(
        ImportPunktacjiZrodel, owner=owner, rodzaj_pliku=RODZAJ_SCOPUS, wybory={}, **kw
    )
    op._sciezka = sciezka
    return op


def _uruchom(op, zapisz=False):
    if zapisz:
        op.zapisz_zmiany_do_bazy = True
        op.save(update_fields=["zapisz_zmiany_do_bazy"])
    op.on_restart()
    analyze_scopus_file(op._sciezka, op, MockProgress(op))
    return {w.nr_wiersza: w for w in op.get_details_set()}


def _pz(zrodlo, rok=2025):
    return Punktacja_Zrodla.objects.filter(zrodlo=zrodlo, rok=rok).first()


@pytest.mark.django_db
def test_podglad_niczego_nie_zapisuje(tmp_path, admin_user):
    z = baker.make(Zrodlo, nazwa="Alpha Journal")
    op = _import(admin_user, _xlsx(tmp_path, [_wiersz("Alpha Journal")]))
    wiersze = _uruchom(op)
    assert wiersze[1].zrodlo == z
    assert wiersze[1].wymaga_zmian is True
    assert "CiteScore: brak → 7.3" in wiersze[1].rezultat
    assert "Najwyższy percentyl: brak → 80" in wiersze[1].rezultat
    assert "Kwartyl Scopus: brak → Q1" in wiersze[1].rezultat
    assert _pz(z) is None


@pytest.mark.django_db
def test_zapis_tworzy_punktacje_i_uzupelnia_kwartyl(tmp_path, admin_user):
    z = baker.make(Zrodlo, nazwa="Alpha Journal")
    op = _import(admin_user, _xlsx(tmp_path, [_wiersz("Alpha Journal")]))
    _uruchom(op, zapisz=True)
    pz = _pz(z)
    assert pz.citescore == Decimal("7.3")
    assert pz.citescore_percentyl == 80
    assert pz.kwartyl_w_scopus == 1
    # SNIP jest opcją domyślnie wyłączoną.
    assert pz.punktacja_snip == 0


@pytest.mark.django_db
def test_tytul_bez_wzgledu_na_wielkosc_liter_i_akcenty(tmp_path, admin_user):
    z = baker.make(Zrodlo, nazwa="Védelem Tudomány Próbny", skrot="VTP")
    po_skrocie = baker.make(Zrodlo, nazwa="Żółte Zeszyty Testowe", skrot="Żół. Zesz.")
    op = _import(
        admin_user,
        _xlsx(
            tmp_path,
            [_wiersz("VEDELEM TUDOMANY PROBNY"), _wiersz("zol. zesz.", 2.0, "30%")],
        ),
    )
    wiersze = _uruchom(op, zapisz=True)
    assert wiersze[1].zrodlo == z
    assert wiersze[2].zrodlo == po_skrocie
    assert _pz(z).citescore == Decimal("7.3")
    assert _pz(po_skrocie).kwartyl_w_scopus == 3


@pytest.mark.django_db
def test_issn_ma_pierwszenstwo_przed_tytulem(tmp_path, admin_user):
    po_tytule = baker.make(Zrodlo, nazwa="Alpha Journal", issn="1111-1111")
    po_issn = baker.make(Zrodlo, nazwa="Zupełnie Inna Nazwa", e_issn="2222-222X")
    op = _import(
        admin_user,
        _xlsx(
            tmp_path,
            # ISSN w pliku bez myślnika i w „złej” kolumnie (cross-field).
            [_wiersz_issn("Alpha Journal", "2222222x", None)],
            naglowek=NAGLOWEK_ISSN,
        ),
    )
    wiersze = _uruchom(op, zapisz=True)
    assert wiersze[1].zrodlo == po_issn
    assert "Dopasowano po: ISSN" in wiersze[1].rezultat
    assert _pz(po_issn).citescore == Decimal("7.3")
    assert _pz(po_tytule) is None


@pytest.mark.django_db
def test_plik_z_issn_spada_na_tytul_gdy_numeru_nie_ma_w_bpp(tmp_path, admin_user):
    z = baker.make(Zrodlo, nazwa="Alpha Journal", issn="")
    op = _import(
        admin_user,
        _xlsx(
            tmp_path,
            [_wiersz_issn("alpha journal", "9999-9999", None)],
            naglowek=NAGLOWEK_ISSN,
        ),
    )
    wiersze = _uruchom(op)
    assert wiersze[1].zrodlo == z
    assert "Dopasowano po: tytuł" in wiersze[1].rezultat


@pytest.mark.django_db
def test_brak_dopasowania_rozmytego_i_brak_tworzenia_zrodel(tmp_path, admin_user):
    baker.make(Zrodlo, nazwa="Journal of Testing Research")
    przed = Zrodlo.objects.count()
    op = _import(
        admin_user,
        _xlsx(tmp_path, [_wiersz("Journal of Testing"), _wiersz("Nieznane Pismo.")]),
    )
    wiersze = _uruchom(op, zapisz=True)
    assert wiersze[1].zrodlo is None and wiersze[2].zrodlo is None
    assert wiersze[1].rezultat == "Brak źródła w BPP"
    assert wiersze[1].do_rozstrzygniecia is False
    assert list(op.niedopasowane().values_list("nr_wiersza", flat=True)) == [1, 2]
    assert Zrodlo.objects.count() == przed
    assert Punktacja_Zrodla.objects.count() == 0


@pytest.mark.django_db
def test_kilka_zrodel_o_tym_tytule_nie_jest_zapisywane_bez_wyboru(tmp_path, admin_user):
    a = baker.make(Zrodlo, nazwa="Acta Testowa", issn="1111-1111")
    b = baker.make(Zrodlo, nazwa="ACTA TESTOWA", issn="2222-2222")
    op = _import(admin_user, _xlsx(tmp_path, [_wiersz("Acta Testowa")]))

    wiersze = _uruchom(op)
    assert wiersze[1].do_rozstrzygniecia is True
    assert wiersze[1].zrodlo is None
    assert wiersze[1].wymaga_zmian is False
    assert sorted(wiersze[1].kandydaci) == sorted([a.pk, b.pk])
    assert "Pasuje kilka źródeł w BPP (2)" in wiersze[1].rezultat

    # Zatwierdzenie bez decyzji: nadal nic.
    wiersze = _uruchom(op, zapisz=True)
    assert wiersze[1].do_rozstrzygniecia is True
    assert Punktacja_Zrodla.objects.count() == 0
    assert op.niedopasowane().count() == 0


@pytest.mark.django_db
def test_wybor_uzytkownika_jest_respektowany(tmp_path, admin_user):
    a = baker.make(Zrodlo, nazwa="Acta Testowa", issn="1111-1111")
    b = baker.make(Zrodlo, nazwa="ACTA TESTOWA", issn="2222-2222")
    op = _import(admin_user, _xlsx(tmp_path, [_wiersz("Acta Testowa")]))
    wiersze = _uruchom(op)

    ustaw_wybor(op, wiersze[1], b.pk)
    wiersze[1].refresh_from_db()
    assert wiersze[1].zrodlo == b
    assert wiersze[1].do_rozstrzygniecia is False
    assert wiersze[1].wymaga_zmian is True
    assert "Wybrano: ACTA TESTOWA" in wiersze[1].rezultat
    # Sam wybór to nadal podgląd.
    assert Punktacja_Zrodla.objects.count() == 0

    op.refresh_from_db()
    assert op.wybory == {"1": b.pk}
    _uruchom(op, zapisz=True)
    assert _pz(b).citescore == Decimal("7.3")
    assert _pz(a) is None


@pytest.mark.django_db
def test_pominiecie_wiersza(tmp_path, admin_user):
    baker.make(Zrodlo, nazwa="Acta Testowa", issn="1111-1111")
    baker.make(Zrodlo, nazwa="ACTA TESTOWA", issn="2222-2222")
    op = _import(admin_user, _xlsx(tmp_path, [_wiersz("Acta Testowa")]))
    wiersze = _uruchom(op)
    ustaw_wybor(op, wiersze[1], WYBOR_POMIN)
    op.refresh_from_db()
    wiersze = _uruchom(op, zapisz=True)
    assert wiersze[1].do_rozstrzygniecia is False
    assert "Pominięto — decyzja użytkownika" in wiersze[1].rezultat
    assert Punktacja_Zrodla.objects.count() == 0
    # Pominięty to nie „niedopasowany”.
    assert op.niedopasowane().count() == 0


@pytest.mark.django_db
def test_wybor_spoza_kandydatow_odrzucony(tmp_path, admin_user):
    baker.make(Zrodlo, nazwa="Acta Testowa", issn="1111-1111")
    baker.make(Zrodlo, nazwa="ACTA TESTOWA", issn="2222-2222")
    obce = baker.make(Zrodlo, nazwa="Obce Pismo")
    jednoznaczne = baker.make(Zrodlo, nazwa="Alpha Journal")
    op = _import(
        admin_user, _xlsx(tmp_path, [_wiersz("Acta Testowa"), _wiersz("Alpha Journal")])
    )
    wiersze = _uruchom(op)
    with pytest.raises(NiedozwolonyWybor):
        ustaw_wybor(op, wiersze[1], obce.pk)
    # Wiersz dopasowany jednoznacznie nie przyjmuje „wyboru”.
    with pytest.raises(NiedozwolonyWybor):
        ustaw_wybor(op, wiersze[2], jednoznaczne.pk)
    op.refresh_from_db()
    assert op.wybory == {}


@pytest.mark.django_db
def test_kilka_wierszy_na_jedno_zrodlo_wymaga_decyzji(tmp_path, admin_user):
    z = baker.make(Zrodlo, nazwa="Alpha Journal")
    op = _import(
        admin_user,
        _xlsx(
            tmp_path,
            [
                _wiersz("Alpha Journal", 1.0, "10%"),
                _wiersz("ALPHA JOURNAL", 9.0, "90%"),
            ],
        ),
    )
    wiersze = _uruchom(op)
    assert wiersze[1].do_rozstrzygniecia and wiersze[2].do_rozstrzygniecia
    assert "wiersze: 2" in wiersze[1].rezultat
    assert "wiersze: 1" in wiersze[2].rezultat

    _uruchom(op, zapisz=True)
    assert _pz(z) is None

    # Wybór drugiego wiersza; pierwszego dla tego samego źródła już nie wolno.
    op.zapisz_zmiany_do_bazy = False
    op.save(update_fields=["zapisz_zmiany_do_bazy"])
    wiersze = _uruchom(op)
    ustaw_wybor(op, wiersze[2], z.pk)
    with pytest.raises(NiedozwolonyWybor, match="wiersza 2"):
        ustaw_wybor(op, wiersze[1], z.pk)
    ustaw_wybor(op, wiersze[1], WYBOR_POMIN)
    op.refresh_from_db()
    _uruchom(op, zapisz=True)
    assert _pz(z).citescore == Decimal("9.0")
    assert _pz(z).kwartyl_w_scopus == 1


@pytest.mark.django_db
def test_bez_opcji_nie_nadpisuje_istniejacych(tmp_path, admin_user):
    z = baker.make(Zrodlo, nazwa="Alpha Journal")
    baker.make(
        Punktacja_Zrodla,
        zrodlo=z,
        rok=2025,
        citescore=Decimal("1.5"),
        citescore_percentyl=None,
        kwartyl_w_scopus=4,
    )
    op = _import(admin_user, _xlsx(tmp_path, [_wiersz("Alpha Journal")]))
    wiersze = _uruchom(op, zapisz=True)
    pz = _pz(z)
    # CiteScore był wpisany → zostaje; percentyl był pusty → uzupełniony;
    # kwartyl wpisany ręcznie → zostaje.
    assert pz.citescore == Decimal("1.5")
    assert pz.citescore_percentyl == 80
    assert pz.kwartyl_w_scopus == 4
    assert "w BPP 1.5, w pliku 7.3 — zostaje 1.5" in wiersze[1].rezultat
    assert "Kwartyl Scopus: zostaje Q4" in wiersze[1].rezultat


@pytest.mark.django_db
def test_opcja_nadpisz_istniejace(tmp_path, admin_user):
    z = baker.make(Zrodlo, nazwa="Alpha Journal")
    baker.make(
        Punktacja_Zrodla,
        zrodlo=z,
        rok=2025,
        citescore=Decimal("1.5"),
        citescore_percentyl=10,
        kwartyl_w_scopus=4,
        impact_factor=Decimal("2.000"),
    )
    op = _import(
        admin_user, _xlsx(tmp_path, [_wiersz("Alpha Journal")]), nadpisz_istniejace=True
    )
    wiersze = _uruchom(op, zapisz=True)
    pz = _pz(z)
    assert pz.citescore == Decimal("7.3")
    assert pz.citescore_percentyl == 80
    # Kwartyl nawet przy nadpisywaniu nie jest ruszany, inne pola też nie.
    assert pz.kwartyl_w_scopus == 4
    assert pz.impact_factor == Decimal("2.000")
    assert "CiteScore: 1.5 → 7.3" in wiersze[1].rezultat


@pytest.mark.django_db
def test_inny_rok_nie_jest_ruszany(tmp_path, admin_user):
    z = baker.make(Zrodlo, nazwa="Alpha Journal")
    baker.make(Punktacja_Zrodla, zrodlo=z, rok=2024, citescore=Decimal("1.5"))
    op = _import(
        admin_user, _xlsx(tmp_path, [_wiersz("Alpha Journal")]), nadpisz_istniejace=True
    )
    _uruchom(op, zapisz=True)
    assert _pz(z, 2024).citescore == Decimal("1.5")
    assert _pz(z, 2025).citescore == Decimal("7.3")


@pytest.mark.django_db
def test_snip_tylko_po_zaznaczeniu(tmp_path, admin_user):
    z = baker.make(Zrodlo, nazwa="Alpha Journal")
    op = _import(
        admin_user,
        _xlsx(tmp_path, [_wiersz("Alpha Journal")]),
        importuj_snip=True,
        importuj_citescore=False,
    )
    _uruchom(op, zapisz=True)
    pz = _pz(z)
    assert pz.punktacja_snip == Decimal("1.234")
    assert pz.citescore is None


@pytest.mark.django_db
def test_zapis_zostawia_slad_w_historii_zrodla(tmp_path, admin_user):
    from reversion.models import Version

    z = baker.make(Zrodlo, nazwa="Alpha Journal")
    bez_zmian = baker.make(Zrodlo, nazwa="Beta Review")
    baker.make(
        Punktacja_Zrodla,
        zrodlo=bez_zmian,
        rok=2025,
        citescore=Decimal("7.3"),
        citescore_percentyl=80,
    )
    op = _import(
        admin_user, _xlsx(tmp_path, [_wiersz("Alpha Journal"), _wiersz("Beta Review")])
    )
    _uruchom(op, zapisz=True)

    ct = ContentType.objects.get_for_model(Zrodlo)
    wpisy = LogEntry.objects.filter(content_type=ct, action_flag=CHANGE)
    wpis = wpisy.get(object_id=str(z.pk))
    assert wpis.user == admin_user
    assert "Import CiteScore (Scopus) za rok 2025" in wpis.change_message
    assert "CiteScore: brak → 7.3" in wpis.change_message
    assert Version.objects.get_for_object(z).exists()
    # Źródło, w którym nic się nie zmieniło, nie dostaje wpisu.
    assert not wpisy.filter(object_id=str(bez_zmian.pk)).exists()


@pytest.mark.django_db
def test_brak_roku_to_blad(tmp_path, admin_user):
    op = _import(admin_user, _xlsx(tmp_path, [_wiersz("Alpha Journal")]), rok=None)
    with pytest.raises(ValueError, match="rok"):
        analyze_scopus_file(op._sciezka, op, MockProgress(op))


@pytest.mark.django_db
def test_kandydaci_zrodla_kilka_po_issn():
    a = baker.make(Zrodlo, nazwa="Jedno", issn="1111-1111")
    b = baker.make(Zrodlo, nazwa="Drugie", issn="1111-1111")
    kandydaci, sposob = kandydaci_zrodla("Cokolwiek", issn="11111111")
    assert {z.pk for z in kandydaci} == {a.pk, b.pk}
    assert sposob == "ISSN"
    assert kandydaci_zrodla("Nie ma takiego") == ([], "")


@pytest.mark.django_db
def test_run_rozdziela_na_import_scopus(tmp_path, admin_user, settings):
    settings.MEDIA_ROOT = str(tmp_path)
    z = baker.make(Zrodlo, nazwa="Alpha Journal")
    baker.make(Zrodlo, nazwa="Acta Testowa", issn="1111-1111")
    baker.make(Zrodlo, nazwa="ACTA TESTOWA", issn="2222-2222")
    _xlsx(
        tmp_path,
        [_wiersz("Alpha Journal"), _wiersz("Acta Testowa"), _wiersz("Nieznane")],
        nazwa="plik.xlsx",
    )
    op = _import(admin_user, None)
    op.plik.name = "plik.xlsx"
    op.save(update_fields=["plik"])
    op.run(MockProgress(op))
    op.refresh_from_db()
    assert op.finished_successfully is True
    assert op.result_context["total"] == 3
    assert op.result_context["do_aktualizacji"] == 1
    assert op.result_context["do_rozstrzygniecia"] == 1
    assert op.result_context["niedopasowane"] == 1
    assert _pz(z) is None


# --------------------------------------------------------------------------- #
# Widoki                                                                       #
# --------------------------------------------------------------------------- #


def _user_w_grupie(django_user_model, username):
    user = django_user_model.objects.create_user(username=username, password="x")
    grupa, _ = Group.objects.get_or_create(name="wprowadzanie danych")
    user.groups.add(grupa)
    return user


@pytest.fixture
def podglad(tmp_path, django_user_model):
    """Gotowy podgląd: wiersz 1 jednoznaczny, 2 — dwa źródła, 3 — brak."""
    user = _user_w_grupie(django_user_model, "redaktor370")
    alpha = baker.make(Zrodlo, nazwa="Alpha Journal")
    a = baker.make(Zrodlo, nazwa="Acta Testowa", issn="1111-1111", wydawca="Wyd. A")
    b = baker.make(Zrodlo, nazwa="ACTA TESTOWA", e_issn="2222-2222")
    op = _import(
        user,
        _xlsx(
            tmp_path,
            [_wiersz("Alpha Journal"), _wiersz("Acta Testowa"), _wiersz("+Nieznane")],
        ),
    )
    wiersze = _uruchom(op)
    now = timezone.now()
    op.started_on = op.finished_on = now
    op.finished_successfully = True
    op.save(update_fields=["started_on", "finished_on", "finished_successfully"])
    return {"op": op, "user": user, "wiersze": wiersze, "alpha": alpha, "a": a, "b": b}


def _adresy(op, wiersz):
    return [
        ("get", reverse("import_punktacji_zrodel:new-scopus")),
        (
            "get",
            reverse(
                "import_punktacji_zrodel:importpunktacjizrodel-results", args=[op.pk]
            ),
        ),
        ("get", reverse("import_punktacji_zrodel:niedopasowane-csv", args=[op.pk])),
        (
            "post",
            reverse("import_punktacji_zrodel:wybierz-zrodlo", args=[op.pk, wiersz.pk]),
        ),
    ]


@pytest.mark.django_db
def test_uprawnienia_bez_grupy(client, django_user_model, podglad):
    op, wiersz = podglad["op"], podglad["wiersze"][2]
    for metoda, url in _adresy(op, wiersz):
        assert getattr(client, metoda)(url).status_code in (302, 403), url
    obcy = django_user_model.objects.create_user(username="bezgrupy", password="x")
    client.force_login(obcy)
    for metoda, url in _adresy(op, wiersz):
        assert getattr(client, metoda)(url).status_code in (302, 403), url
    op.refresh_from_db()
    assert op.wybory == {}


@pytest.mark.django_db
def test_cudzy_import_niedostepny(client, django_user_model, podglad):
    op, wiersz = podglad["op"], podglad["wiersze"][2]
    inny = _user_w_grupie(django_user_model, "inny370")
    client.force_login(inny)
    for metoda, url in _adresy(op, wiersz)[1:]:
        assert getattr(client, metoda)(url).status_code == 404, url
    resp = client.post(
        reverse("import_punktacji_zrodel:wybierz-zrodlo", args=[op.pk, wiersz.pk]),
        {"zrodlo": str(podglad["a"].pk)},
    )
    assert resp.status_code == 404
    op.refresh_from_db()
    assert op.wybory == {}


@pytest.mark.django_db
def test_formularz_tworzy_import_scopus_jako_podglad(client, django_user_model):
    from unittest.mock import patch

    user = _user_w_grupie(django_user_model, "nowy370")
    client.force_login(user)
    url = reverse("import_punktacji_zrodel:new-scopus")
    assert client.get(url).status_code == 200

    plik = SimpleUploadedFile("scopus.xlsx", b"PK-nieistotne")
    with patch.object(ImportPunktacjiZrodel, "enqueue") as enqueue:
        resp = client.post(
            url, {"plik": plik, "rok": "2025", "importuj_citescore": "on"}
        )
    assert resp.status_code == 302
    enqueue.assert_called_once()
    op = ImportPunktacjiZrodel.objects.get(owner=user)
    assert op.rodzaj_pliku == RODZAJ_SCOPUS
    assert op.zapisz_zmiany_do_bazy is False
    assert op.nadpisz_istniejace is False
    assert op.importuj_snip is False
    assert op.rok == 2025


@pytest.mark.django_db
def test_formularz_wymaga_roku(client, django_user_model):
    user = _user_w_grupie(django_user_model, "bezroku370")
    client.force_login(user)
    plik = SimpleUploadedFile("scopus.xlsx", b"PK-nieistotne")
    resp = client.post(
        reverse("import_punktacji_zrodel:new-scopus"),
        {"plik": plik, "importuj_citescore": "on"},
    )
    assert resp.status_code == 200
    assert not ImportPunktacjiZrodel.objects.exists()


@pytest.mark.django_db
def test_strona_wynikow_pokazuje_kandydatow(client, podglad):
    op = podglad["op"]
    client.force_login(podglad["user"])
    resp = client.get(
        reverse("import_punktacji_zrodel:importpunktacjizrodel-results", args=[op.pk])
    )
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "Do rozstrzygnięcia: 1" in html
    assert "Niedopasowanych: 1" in html
    assert "Wyd. A" in html
    assert "1111-1111" in html and "2222-2222" in html
    assert reverse("admin:bpp_zrodlo_change", args=[podglad["a"].pk]) in html
    assert reverse("admin:bpp_zrodlo_change", args=[podglad["b"].pk]) in html
    assert reverse("import_punktacji_zrodel:niedopasowane-csv", args=[op.pk]) in html
    assert "Zatwierdź i zapisz do bazy" in html

    resp = client.get(
        reverse("import_punktacji_zrodel:importpunktacjizrodel-results", args=[op.pk])
        + "?tylko_do_rozstrzygniecia=1"
    )
    assert [w.nr_wiersza for w in resp.context["object_list"]] == [2]


@pytest.mark.django_db
def test_widok_wyboru_zapisuje_decyzje(client, podglad):
    op, wiersz, b = podglad["op"], podglad["wiersze"][2], podglad["b"]
    client.force_login(podglad["user"])
    url = reverse("import_punktacji_zrodel:wybierz-zrodlo", args=[op.pk, wiersz.pk])

    resp = client.post(
        url, {"zrodlo": str(b.pk), "filtry": "tylko_do_rozstrzygniecia=1&x=//zly"}
    )
    assert resp.status_code == 302
    assert resp.url == (
        reverse("import_punktacji_zrodel:importpunktacjizrodel-results", args=[op.pk])
        + "?tylko_do_rozstrzygniecia=1"
    )
    op.refresh_from_db()
    wiersz.refresh_from_db()
    assert op.wybory == {"2": b.pk}
    assert wiersz.zrodlo == b
    assert Punktacja_Zrodla.objects.count() == 0

    client.post(url, {"zrodlo": "pomin"})
    op.refresh_from_db()
    assert op.wybory == {"2": WYBOR_POMIN}

    client.post(url, {"zrodlo": ""})
    op.refresh_from_db()
    wiersz.refresh_from_db()
    assert op.wybory == {}
    assert wiersz.do_rozstrzygniecia is True


@pytest.mark.django_db
def test_widok_wyboru_odrzuca_zrodlo_spoza_listy(client, podglad):
    op, wiersz = podglad["op"], podglad["wiersze"][2]
    client.force_login(podglad["user"])
    url = reverse("import_punktacji_zrodel:wybierz-zrodlo", args=[op.pk, wiersz.pk])
    resp = client.post(url, {"zrodlo": str(podglad["alpha"].pk)})
    assert resp.status_code == 302
    op.refresh_from_db()
    assert op.wybory == {}
    assert client.post(url, {"zrodlo": "abc"}).status_code == 404


@pytest.mark.django_db
def test_widok_wyboru_tylko_w_podgladzie(client, podglad):
    op, wiersz = podglad["op"], podglad["wiersze"][2]
    op.zapisz_zmiany_do_bazy = True
    op.save(update_fields=["zapisz_zmiany_do_bazy"])
    client.force_login(podglad["user"])
    client.post(
        reverse("import_punktacji_zrodel:wybierz-zrodlo", args=[op.pk, wiersz.pk]),
        {"zrodlo": str(podglad["b"].pk)},
    )
    op.refresh_from_db()
    assert op.wybory == {}


@pytest.mark.django_db
def test_csv_niedopasowanych(client, podglad):
    op = podglad["op"]
    client.force_login(podglad["user"])
    resp = client.get(
        reverse("import_punktacji_zrodel:niedopasowane-csv", args=[op.pk])
    )
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")
    tresc = resp.content.decode("utf-8-sig")
    linie = tresc.strip().splitlines()
    assert len(linie) == 2
    # Tytuł zaczynający się od znaku formuły jest unieszkodliwiony apostrofem.
    assert linie[1].startswith("3;'+Nieznane;")
    assert "Acta Testowa" not in tresc and "Alpha Journal" not in tresc


@pytest.mark.django_db
def test_import_jcr_nie_ma_widokow_scopus(client, django_user_model):
    user = _user_w_grupie(django_user_model, "jcr370")
    client.force_login(user)
    op = baker.make(ImportPunktacjiZrodel, owner=user, rok=2025)
    assert op.rodzaj_pliku == "jcr"
    resp = client.get(
        reverse("import_punktacji_zrodel:niedopasowane-csv", args=[op.pk])
    )
    assert resp.status_code == 404


@pytest.mark.django_db
def test_strona_wynikow_po_zapisie(client, podglad):
    op = podglad["op"]
    _uruchom(op, zapisz=True)
    client.force_login(podglad["user"])
    resp = client.get(
        reverse("import_punktacji_zrodel:importpunktacjizrodel-results", args=[op.pk])
    )
    html = resp.content.decode()
    assert "Zmiany zapisane" in html
    assert "Zatwierdź i zapisz do bazy" not in html
    assert "Zapisz wybór" not in html
    assert reverse("rozbieznosci:index", kwargs={"metryka": "kw_scopus"}) in html
    assert _pz(podglad["alpha"]).citescore == Decimal("7.3")
    # Wiersz bez decyzji nie zapisał niczego żadnemu z kandydatów.
    assert _pz(podglad["a"]) is None and _pz(podglad["b"]) is None


@pytest.mark.django_db
def test_lista_importow_ma_przycisk_scopus(client, podglad):
    client.force_login(podglad["user"])
    html = client.get(reverse("import_punktacji_zrodel:index")).content.decode()
    assert reverse("import_punktacji_zrodel:new-scopus") in html
    assert "Scopus (CiteScore)" in html
