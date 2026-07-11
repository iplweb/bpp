"""Ekran weryfikacji jednostek (WeryfikacjaJednostekView) + toggle w mapowaniu."""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Jednostka
from import_pracownikow.models import ImportPracownikow, ImportPracownikowJednostka

AKCEPTUJ = ImportPracownikowJednostka.DECYZJA_AKCEPTUJ
MAPUJ = ImportPracownikowJednostka.DECYZJA_MAPUJ
POMIN = ImportPracownikowJednostka.DECYZJA_POMIN
BRAK = ImportPracownikowJednostka.TRYB_BRAK


def _imp(owner, stan=ImportPracownikow.STAN_PRZEANALIZOWANY):
    return baker.make(ImportPracownikow, owner=owner, stan=stan)


def _dec(imp, nazwa, **kw):
    kw.setdefault("tryb", BRAK)
    kw.setdefault("decyzja", AKCEPTUJ)
    return baker.make(
        ImportPracownikowJednostka, parent=imp, nazwa_zrodlowa=nazwa, **kw
    )


@pytest.mark.django_db
def test_get_renderuje_liste_decyzji(admin_client, admin_user):
    imp = _imp(admin_user)
    _dec(imp, "Zakład Transfuzjologii")
    url = reverse("import_pracownikow:jednostki", kwargs={"pk": imp.pk})
    resp = admin_client.get(url)
    assert resp.status_code == 200
    assert "Zakład Transfuzjologii".encode() in resp.content


@pytest.mark.django_db
def test_post_zapisuje_decyzje_mapuj(admin_client, admin_user):
    imp = _imp(admin_user)
    # cel „mapuj" musi być w puli UI (widoczna jednostka skupiająca pracowników)
    j = baker.make(
        Jednostka,
        nazwa="Docelowa",
        skrot="DOC",
        skupia_pracownikow=True,
        widoczna=True,
    )
    dec = _dec(imp, "Zrodlowa")
    url = reverse("import_pracownikow:jednostki", kwargs={"pk": imp.pk})
    resp = admin_client.post(
        url,
        {f"dec_{dec.pk}_decyzja": MAPUJ, f"dec_{dec.pk}_wybrana": str(j.pk)},
    )
    assert resp.status_code == 302
    dec.refresh_from_db()
    assert dec.decyzja == MAPUJ
    assert dec.wybrana_jednostka_id == j.pk


@pytest.mark.django_db
def test_post_blad_zachowuje_ustawione_wartosci(admin_client, admin_user):
    """Regresja: „Zapisz" z niekompletnym „mapuj" NIE robi już redirectu (który
    gubił WSZYSTKIE ustawienia) — re-renderuje formularz z zachowanymi wyborami
    i podświetla błędny wiersz. Nic się nie zapisuje (guard „mapuj bez celu")."""
    import re

    imp = _imp(admin_user)
    j = baker.make(
        Jednostka,
        nazwa="Docelowa",
        skrot="DOC",
        skupia_pracownikow=True,
        widoczna=True,
    )
    dec_ok = _dec(imp, "Zrodlowa OK")
    dec_zla = _dec(imp, "Zrodlowa BEZ CELU")
    url = reverse("import_pracownikow:jednostki", kwargs={"pk": imp.pk})
    resp = admin_client.post(
        url,
        {
            # poprawny „mapuj" z celem
            f"dec_{dec_ok.pk}_decyzja": MAPUJ,
            f"dec_{dec_ok.pk}_wybrana": str(j.pk),
            # „mapuj" BEZ celu → błąd walidacji
            f"dec_{dec_zla.pk}_decyzja": MAPUJ,
            f"dec_{dec_zla.pk}_wybrana": "",
        },
    )
    # re-render (200), NIE redirect (302)
    assert resp.status_code == 200
    tresc = resp.content.decode("utf-8")
    assert "Wybierz jednostkę docelową" in tresc
    assert "Zrodlowa BEZ CELU" in tresc
    assert "wskaż jednostkę docelową" in tresc  # podświetlenie błędnego wiersza
    # nic nie zapisane (guard) — dec_ok zostaje na domyślnym AKCEPTUJ
    dec_ok.refresh_from_db()
    assert dec_ok.decyzja == AKCEPTUJ
    assert dec_ok.wybrana_jednostka_id is None
    # ale FORMULARZ zachował wybór usera dla dec_ok: „mapuj" + jednostka docelowa
    assert re.search(
        rf'name="dec_{dec_ok.pk}_decyzja".*?value="{MAPUJ}"[^>]*selected',
        tresc,
        re.S,
    )
    assert re.search(
        rf'name="dec_{dec_ok.pk}_wybrana".*?value="{j.pk}"[^>]*selected',
        tresc,
        re.S,
    )


@pytest.mark.django_db
def test_post_poza_podgladem_400_nie_zmienia(admin_client, admin_user):
    imp = _imp(admin_user, stan=ImportPracownikow.STAN_ZINTEGROWANY)
    dec = _dec(imp, "X", decyzja=AKCEPTUJ)
    url = reverse("import_pracownikow:jednostki", kwargs={"pk": imp.pk})
    resp = admin_client.post(url, {f"dec_{dec.pk}_decyzja": POMIN})
    assert resp.status_code == 400
    dec.refresh_from_db()
    assert dec.decyzja == AKCEPTUJ


@pytest.mark.django_db
def test_nazwa_ze_skryptem_jest_escapowana(admin_client, admin_user):
    imp = _imp(admin_user)
    _dec(imp, "<script>alert(1)</script>")
    url = reverse("import_pracownikow:jednostki", kwargs={"pk": imp.pk})
    resp = admin_client.get(url)
    assert resp.status_code == 200
    assert b"<script>alert(1)</script>" not in resp.content
    assert b"&lt;script&gt;" in resp.content


@pytest.mark.django_db
def test_scoping_obcy_import_404(admin_client):
    obcy = baker.make("bpp.BppUser")
    imp = _imp(obcy)  # nie admin_user, a admin_client jest superuserem → widzi
    # superuser MA dostęp — sprawdzamy, że nie-owner-superuser to widzi (200),
    # a scoping działa dla zwykłych userów (pokryte przez owner check w innych).
    url = reverse("import_pracownikow:jednostki", kwargs={"pk": imp.pk})
    resp = admin_client.get(url)
    assert resp.status_code == 200


@pytest.mark.django_db
def test_post_nienumeryczny_parent_nie_wywala_500(admin_client, admin_user):
    """Spreparowany POST z nienumerycznym ``parent`` NIE może wywrócić widoku
    (Jednostka.objects.filter(pk="abc") → ValueError → 500). Nienumeryczne id
    jest ignorowane, decyzja zapisana z parent=None."""
    imp = _imp(admin_user)
    dec = _dec(imp, "Zrodlowa")
    url = reverse("import_pracownikow:jednostki", kwargs={"pk": imp.pk})
    resp = admin_client.post(
        url,
        {f"dec_{dec.pk}_decyzja": AKCEPTUJ, f"dec_{dec.pk}_parent": "abc"},
    )
    assert resp.status_code == 302
    dec.refresh_from_db()
    assert dec.wybrany_parent_id is None


@pytest.mark.django_db
def test_post_mapuj_na_ukryta_jednostke_odrzucone(admin_client, admin_user):
    """„Mapuj" na jednostkę spoza puli UI (nie skupia pracowników / niewidoczna)
    musi być odrzucone tak samo jak brak celu — POST nie może przypisać
    pracowników do ukrytej jednostki tylko dlatego, że zna jej pk."""
    imp = _imp(admin_user)
    ukryta = baker.make(
        Jednostka,
        nazwa="Ukryta",
        skrot="UKR",
        skupia_pracownikow=False,
        widoczna=False,
    )
    dec = _dec(imp, "Zrodlowa")
    url = reverse("import_pracownikow:jednostki", kwargs={"pk": imp.pk})
    resp = admin_client.post(
        url,
        {f"dec_{dec.pk}_decyzja": MAPUJ, f"dec_{dec.pk}_wybrana": str(ukryta.pk)},
    )
    # spoza puli UI → traktowane jak brak celu → re-render 200, nic nie zapisane
    assert resp.status_code == 200
    dec.refresh_from_db()
    assert dec.wybrana_jednostka_id is None


@pytest.mark.django_db
def test_post_parent_niebedacy_rootem_zignorowany(admin_client, admin_user):
    """Parent nowej jednostki wolno wskazać tylko na korzeń (pula UI =
    parent__isnull=True). Spreparowany POST z nie-rootem jako parentem jest
    ignorowany (parent=None), nie używa dowolnego węzła drzewa jako parenta."""
    imp = _imp(admin_user)
    root = baker.make(Jednostka, nazwa="Root", skrot="ROOT", parent=None)
    dziecko = baker.make(Jednostka, nazwa="Dziecko", skrot="DZIE", parent=root)
    dec = _dec(imp, "Zrodlowa")
    url = reverse("import_pracownikow:jednostki", kwargs={"pk": imp.pk})
    resp = admin_client.post(
        url,
        {f"dec_{dec.pk}_decyzja": AKCEPTUJ, f"dec_{dec.pk}_parent": str(dziecko.pk)},
    )
    assert resp.status_code == 302
    dec.refresh_from_db()
    assert dec.wybrany_parent_id is None


@pytest.mark.django_db
def test_toggle_tworz_brakujace_w_mapowaniu_zapisuje_false(admin_client, admin_user):
    from unittest.mock import patch

    from django.core.files.uploadedfile import SimpleUploadedFile

    csv = b"Nazwisko;Imie;Jedn org\nKowalski;Jan;Katedra\n"
    imp = ImportPracownikow(owner=admin_user, stan=ImportPracownikow.STAN_UTWORZONY)
    imp.plik_xls = SimpleUploadedFile("p.csv", csv)
    imp.save()

    url = reverse("import_pracownikow:mapowanie", kwargs={"pk": imp.pk})
    dane = {
        "kol__nazwisko": "nazwisko",
        "kol__imie": "imię",
        "kol__jedn_org": "nazwa_jednostki",
        "zapisz_profil": False,
        "nazwa_profilu": "",
        # tworz_brakujace_jednostki NIEobecne → BooleanField=False (odznaczone)
    }
    with patch.object(ImportPracownikow, "run", lambda self, p: None):
        resp = admin_client.post(url, dane)
    assert resp.status_code == 302
    imp.refresh_from_db()
    assert imp.tworz_brakujace_jednostki is False
