"""Ekran weryfikacji tytułów (WeryfikacjaTytulowView) — mirror jednostek."""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Tytul
from import_pracownikow.models import ImportPracownikow, ImportPracownikowTytul

AKCEPTUJ = ImportPracownikowTytul.DECYZJA_AKCEPTUJ
MAPUJ = ImportPracownikowTytul.DECYZJA_MAPUJ
POMIN = ImportPracownikowTytul.DECYZJA_POMIN
BRAK = ImportPracownikowTytul.TRYB_BRAK
ZGADYWANIE = ImportPracownikowTytul.TRYB_ZGADYWANIE


def _imp(owner, stan=ImportPracownikow.STAN_PRZEANALIZOWANY):
    return baker.make(ImportPracownikow, owner=owner, stan=stan)


def _dec(imp, nazwa, **kw):
    kw.setdefault("tryb", BRAK)
    kw.setdefault("decyzja", AKCEPTUJ)
    return baker.make(ImportPracownikowTytul, parent=imp, nazwa_zrodlowa=nazwa, **kw)


@pytest.mark.django_db
def test_get_renderuje_sekcje_brak(admin_client, admin_user):
    imp = _imp(admin_user)
    dec = _dec(
        imp,
        "profesor belwederski",
        tryb=BRAK,
        nazwa_do_utworzenia="profesor belwederski",
        skrot_do_utworzenia="prof. belw.",
    )
    url = reverse("import_pracownikow:tytuly", kwargs={"pk": imp.pk})
    resp = admin_client.get(url)
    assert resp.status_code == 200
    assert b"Do utworzenia" in resp.content
    assert b"profesor belwederski" in resp.content
    # edytowalne pola nazwa/skrót dla trybu brak
    assert f"dec_{dec.pk}_nazwa".encode() in resp.content
    assert f"dec_{dec.pk}_skrot".encode() in resp.content


@pytest.mark.django_db
def test_get_renderuje_sekcje_zgadywanie(admin_client, admin_user):
    imp = _imp(admin_user)
    # unikalna nazwa/skrót — baseline seeduje realne tytuły (np. „dr hab.”)
    t, _ = Tytul.objects.get_or_create(
        nazwa="doktor testowy weryfikacji", skrot="dr test. wer."
    )
    _dec(
        imp,
        "dr. test wer",
        tryb=ZGADYWANIE,
        auto_tytul=t,
        auto_similarity=0.91,
    )
    url = reverse("import_pracownikow:tytuly", kwargs={"pk": imp.pk})
    resp = admin_client.get(url)
    assert resp.status_code == 200
    assert b"Dopasowane automatycznie" in resp.content
    assert b"dr test. wer." in resp.content
    # floatformat:2 — locale pl renderuje przecinek („0,91”), en kropkę
    assert b"0,91" in resp.content or b"0.91" in resp.content


@pytest.mark.django_db
def test_get_wszystko_dopasowane_callout(admin_client, admin_user):
    imp = _imp(admin_user)
    url = reverse("import_pracownikow:tytuly", kwargs={"pk": imp.pk})
    resp = admin_client.get(url)
    assert resp.status_code == 200
    # brak decyzji obu typów → callout "wszystko dopasowane"
    assert b"nie ma nic do" in resp.content


@pytest.mark.django_db
def test_post_zapisuje_decyzje_mapuj(admin_client, admin_user):
    imp = _imp(admin_user)
    t = baker.make(Tytul, nazwa="Docelowy", skrot="doc.")
    dec = _dec(imp, "zrodlowy", tryb=ZGADYWANIE)
    url = reverse("import_pracownikow:tytuly", kwargs={"pk": imp.pk})
    resp = admin_client.post(
        url,
        {f"dec_{dec.pk}_decyzja": MAPUJ, f"dec_{dec.pk}_wybrana": str(t.pk)},
    )
    assert resp.status_code == 302
    dec.refresh_from_db()
    assert dec.decyzja == MAPUJ
    assert dec.wybrany_tytul_id == t.pk


@pytest.mark.django_db
def test_post_zapisuje_edytowalne_nazwa_skrot_dla_brak(admin_client, admin_user):
    imp = _imp(admin_user)
    dec = _dec(
        imp,
        "prof zwyczajny",
        tryb=BRAK,
        nazwa_do_utworzenia="stara nazwa",
        skrot_do_utworzenia="st.",
    )
    url = reverse("import_pracownikow:tytuly", kwargs={"pk": imp.pk})
    resp = admin_client.post(
        url,
        {
            f"dec_{dec.pk}_decyzja": AKCEPTUJ,
            f"dec_{dec.pk}_nazwa": "profesor zwyczajny",
            f"dec_{dec.pk}_skrot": "prof. zw.",
        },
    )
    assert resp.status_code == 302
    dec.refresh_from_db()
    assert dec.decyzja == AKCEPTUJ
    assert dec.nazwa_do_utworzenia == "profesor zwyczajny"
    assert dec.skrot_do_utworzenia == "prof. zw."


@pytest.mark.django_db
def test_post_przycina_nazwe_i_skrot_do_max_length(admin_client, admin_user):
    imp = _imp(admin_user)
    dec = _dec(imp, "x", tryb=BRAK)
    url = reverse("import_pracownikow:tytuly", kwargs={"pk": imp.pk})
    resp = admin_client.post(
        url,
        {
            f"dec_{dec.pk}_decyzja": AKCEPTUJ,
            f"dec_{dec.pk}_nazwa": "n" * 600,
            f"dec_{dec.pk}_skrot": "s" * 200,
        },
    )
    assert resp.status_code == 302
    dec.refresh_from_db()
    assert len(dec.nazwa_do_utworzenia) == 512
    assert len(dec.skrot_do_utworzenia) == 128


@pytest.mark.django_db
def test_post_poza_podgladem_400_nie_zmienia(admin_client, admin_user):
    imp = _imp(admin_user, stan=ImportPracownikow.STAN_ZINTEGROWANY)
    dec = _dec(imp, "x", decyzja=AKCEPTUJ)
    url = reverse("import_pracownikow:tytuly", kwargs={"pk": imp.pk})
    resp = admin_client.post(url, {f"dec_{dec.pk}_decyzja": POMIN})
    assert resp.status_code == 400
    dec.refresh_from_db()
    assert dec.decyzja == AKCEPTUJ


@pytest.mark.django_db
def test_get_poza_podgladem_kontrolki_disabled(admin_client, admin_user):
    imp = _imp(admin_user, stan=ImportPracownikow.STAN_ZINTEGROWANY)
    _dec(imp, "prof x", tryb=BRAK)
    url = reverse("import_pracownikow:tytuly", kwargs={"pk": imp.pk})
    resp = admin_client.get(url)
    assert resp.status_code == 200
    assert b"disabled" in resp.content
    # brak przycisku "Zapisz decyzje" poza podglądem
    assert b"Zapisz decyzje" not in resp.content


@pytest.mark.django_db
def test_nazwa_ze_skryptem_jest_escapowana(admin_client, admin_user):
    imp = _imp(admin_user)
    _dec(imp, "<script>alert(1)</script>", tryb=BRAK)
    url = reverse("import_pracownikow:tytuly", kwargs={"pk": imp.pk})
    resp = admin_client.get(url)
    assert resp.status_code == 200
    assert b"<script>alert(1)</script>" not in resp.content
    assert b"&lt;script&gt;" in resp.content


@pytest.mark.django_db
def test_scoping_obcy_import_404(client, django_user_model, admin_user):
    imp = _imp(admin_user)
    obcy = django_user_model.objects.create_user(
        username="obcy_tyt", password="x", is_superuser=False
    )
    from django.contrib.auth.models import Group

    grupa, _ = Group.objects.get_or_create(name="wprowadzanie danych")
    obcy.groups.add(grupa)
    client.force_login(obcy)
    url = reverse("import_pracownikow:tytuly", kwargs={"pk": imp.pk})
    resp = client.get(url)
    assert resp.status_code == 404
