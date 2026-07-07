import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor
from powiazania_autorow.models import AuthorConnection


@pytest.mark.django_db
def test_dane_zwraca_centrum_i_sasiadow_posortowanych(client):
    centrum = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pokazuj=True)
    a = baker.make(Autor, imiona="Anna", nazwisko="Nowak", pokazuj=True)
    b = baker.make(Autor, imiona="Bob", nazwisko="Zet", pokazuj=True)
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=a, shared_publications_count=2
    )
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=b, shared_publications_count=9
    )

    url = reverse("bpp:browse_autor_powiazania_dane", args=[centrum.pk])
    resp = client.get(url)

    assert resp.status_code == 200
    data = resp.json()
    assert data["center"]["id"] == centrum.pk
    assert data["center"]["label"] == "Jan Kowalski"
    labels = [n["label"] for n in data["neighbors"]]
    assert labels == ["Bob Zet", "Anna Nowak"]
    assert data["neighbors"][0]["shared"] == 9


@pytest.mark.django_db
def test_dane_zawiera_tytul_orcid_pbn(client):
    from bpp.models import Tytul

    tytul = baker.make(Tytul, skrot="prof. dr hab.")
    centrum = baker.make(Autor, pokazuj=True)
    sasiad = baker.make(
        Autor,
        imiona="Anna",
        nazwisko="Nowak",
        pokazuj=True,
        tytul=tytul,
        orcid="0000-0002-1825-0097",
    )
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=sasiad, shared_publications_count=2
    )

    url = reverse("bpp:browse_autor_powiazania_dane", args=[centrum.pk])
    data = client.get(url).json()

    n = data["neighbors"][0]
    assert n["tytul"] == "prof. dr hab."
    assert n["orcid"] == "0000-0002-1825-0097"
    assert n["pbn_url"] == ""  # brak pbn_uid -> brak linku do PBN
    assert "total_works" in n  # liczba wszystkich prac (rozmiar węzła)
    assert isinstance(n["total_works"], int)
    assert "if_sum" in n  # sumaryczny IF (alternatywna metryka rozmiaru)
    assert "pk_sum" in n  # sumaryczny PK
    # centrum też ma komplet kluczy (bez tytułu/orcid -> puste stringi)
    assert data["center"]["tytul"] == ""
    assert data["center"]["orcid"] == ""
    assert data["center"]["pbn_url"] == ""
    assert isinstance(data["center"]["total_works"], int)
    assert "if_sum" in data["center"]
    assert "pk_sum" in data["center"]


@pytest.mark.django_db
def test_dane_dziala_gdy_autor_jest_secondary(client):
    centrum = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pokazuj=True)
    inny = baker.make(Autor, imiona="Ewa", nazwisko="Lis", pokazuj=True)
    AuthorConnection.objects.create(
        primary_author=inny, secondary_author=centrum, shared_publications_count=4
    )

    url = reverse("bpp:browse_autor_powiazania_dane", args=[centrum.pk])
    data = client.get(url).json()

    assert [n["label"] for n in data["neighbors"]] == ["Ewa Lis"]


@pytest.mark.django_db
def test_dane_pomija_autorow_z_pokazuj_false(client):
    centrum = baker.make(Autor, pokazuj=True)
    ukryty = baker.make(Autor, imiona="X", nazwisko="Ukryty", pokazuj=False)
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=ukryty, shared_publications_count=3
    )

    url = reverse("bpp:browse_autor_powiazania_dane", args=[centrum.pk])
    data = client.get(url).json()

    assert data["neighbors"] == []


@pytest.mark.django_db
def test_dane_pusty_gdy_brak_powiazan(client):
    centrum = baker.make(Autor, pokazuj=True)
    url = reverse("bpp:browse_autor_powiazania_dane", args=[centrum.pk])
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.json()["neighbors"] == []


@pytest.mark.django_db
def test_dane_404_dla_nieistniejacego_autora(client):
    url = reverse("bpp:browse_autor_powiazania_dane", args=[99999])
    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_siec_bfs_dwa_poziomy(client):
    centrum = baker.make(Autor, pokazuj=True)
    a = baker.make(Autor, pokazuj=True)
    b = baker.make(Autor, pokazuj=True)
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=a, shared_publications_count=5
    )
    AuthorConnection.objects.create(
        primary_author=a, secondary_author=b, shared_publications_count=3
    )

    url = reverse("bpp:browse_autor_powiazania_siec", args=[centrum.pk])
    data = client.get(url, {"depth": 2, "topn": 10}).json()

    assert data["center_id"] == centrum.pk
    poziomy = {n["id"]: n["level"] for n in data["nodes"]}
    assert poziomy == {centrum.pk: 0, a.pk: 1, b.pk: 2}
    rodzice = {n["id"]: n["parent"] for n in data["nodes"]}
    assert rodzice[centrum.pk] is None
    assert rodzice[a.pk] == centrum.pk
    assert rodzice[b.pk] == a.pk
    assert data["truncated"] is False
    # krawędzie drzewa rozwijania
    pary = {(e["source"], e["target"]) for e in data["edges"]}
    assert (centrum.pk, a.pk) in pary
    assert (a.pk, b.pk) in pary


@pytest.mark.django_db
def test_siec_depth1_to_tylko_pierscien(client):
    centrum = baker.make(Autor, pokazuj=True)
    a = baker.make(Autor, pokazuj=True)
    b = baker.make(Autor, pokazuj=True)
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=a, shared_publications_count=5
    )
    AuthorConnection.objects.create(
        primary_author=a, secondary_author=b, shared_publications_count=3
    )

    url = reverse("bpp:browse_autor_powiazania_siec", args=[centrum.pk])
    data = client.get(url, {"depth": 1}).json()

    ids = {n["id"] for n in data["nodes"]}
    assert centrum.pk in ids and a.pk in ids
    assert b.pk not in ids  # poziom 2 poza zasięgiem depth=1


@pytest.mark.django_db
def test_siec_pomija_ukrytych_autorow(client):
    centrum = baker.make(Autor, pokazuj=True)
    ukryty = baker.make(Autor, pokazuj=False)
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=ukryty, shared_publications_count=5
    )

    url = reverse("bpp:browse_autor_powiazania_siec", args=[centrum.pk])
    data = client.get(url, {"depth": 3}).json()

    assert {n["id"] for n in data["nodes"]} == {centrum.pk}
    assert data["nodes"][0]["level"] == 0


@pytest.mark.django_db
def test_siec_extra_edges_poprzeczne(client):
    centrum = baker.make(Autor, pokazuj=True)
    a = baker.make(Autor, pokazuj=True)
    b = baker.make(Autor, pokazuj=True)
    # trójkąt: centrum-A, centrum-B (drzewo) oraz A-B (krawędź poprzeczna)
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=a, shared_publications_count=5
    )
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=b, shared_publications_count=4
    )
    AuthorConnection.objects.create(
        primary_author=a, secondary_author=b, shared_publications_count=3
    )

    url = reverse("bpp:browse_autor_powiazania_siec", args=[centrum.pk])
    data = client.get(url, {"depth": 2, "topn": 10}).json()

    tree = {tuple(sorted((e["source"], e["target"]))) for e in data["edges"]}
    assert tuple(sorted((centrum.pk, a.pk))) in tree
    assert tuple(sorted((centrum.pk, b.pk))) in tree

    extra = {tuple(sorted((e["source"], e["target"]))) for e in data["extra_edges"]}
    assert tuple(sorted((a.pk, b.pk))) in extra
    # krawędzi drzewa nie ma w poprzecznych
    assert tuple(sorted((centrum.pk, a.pk))) not in extra


@pytest.mark.django_db
def test_siec_404_dla_nieistniejacego_autora(client):
    url = reverse("bpp:browse_autor_powiazania_siec", args=[99999])
    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_siec_filtr_roku(client, jednostka, typy_odpowiedzialnosci):
    from bpp.models import Wydawnictwo_Ciagle

    centrum = baker.make(Autor, imiona="Jan", nazwisko="Centralny", pokazuj=True)
    a_stary = baker.make(Autor, imiona="Adam", nazwisko="Stary", pokazuj=True)
    a_nowy = baker.make(Autor, imiona="Ewa", nazwisko="Nowa", pokazuj=True)

    w1 = baker.make(Wydawnictwo_Ciagle, rok=2005)
    w1.dodaj_autora(centrum, jednostka)
    w1.dodaj_autora(a_stary, jednostka)

    w2 = baker.make(Wydawnictwo_Ciagle, rok=2020)
    w2.dodaj_autora(centrum, jednostka)
    w2.dodaj_autora(a_nowy, jednostka)

    url = reverse("bpp:browse_autor_powiazania_siec", args=[centrum.pk])
    data = client.get(url, {"rok_od": 2018, "rok_do": 2025, "depth": 1}).json()

    ids = {n["id"] for n in data["nodes"]}
    assert centrum.pk in ids
    assert a_nowy.pk in ids  # współautor z 2020 — w zakresie
    assert a_stary.pk not in ids  # współautor z 2005 — poza zakresem
    assert data["rok_min"] == 2005
    assert data["rok_max"] == 2020


@pytest.mark.django_db
def test_siec_filtr_roku_happy_path_mimo_statement_timeout(
    client, jednostka, typy_odpowiedzialnosci
):
    # Aktywny filtr roku owija liczenie BFS/krawędzi w `SET LOCAL
    # statement_timeout`. Sprawdzamy, że happy path (zapytanie mieści się
    # w limicie) nadal zwraca 200 i poprawny payload, mimo owinięcia.
    from bpp.models import Wydawnictwo_Ciagle

    centrum = baker.make(Autor, imiona="Jan", nazwisko="Centralny", pokazuj=True)
    a_nowy = baker.make(Autor, imiona="Ewa", nazwisko="Nowa", pokazuj=True)

    w = baker.make(Wydawnictwo_Ciagle, rok=2020)
    w.dodaj_autora(centrum, jednostka)
    w.dodaj_autora(a_nowy, jednostka)

    url = reverse("bpp:browse_autor_powiazania_siec", args=[centrum.pk])
    resp = client.get(url, {"rok_od": 2018, "rok_do": 2025, "depth": 1})

    assert resp.status_code == 200
    data = resp.json()
    assert data["center_id"] == centrum.pk
    ids = {n["id"] for n in data["nodes"]}
    assert centrum.pk in ids
    assert a_nowy.pk in ids  # współautor z 2020 — w zakresie filtra
    assert "edges" in data
    assert "extra_edges" in data
    assert data["truncated"] is False


@pytest.mark.django_db
def test_siec_filtr_zrodla(client, jednostka, typy_odpowiedzialnosci):
    from bpp.models import Wydawnictwo_Ciagle, Zrodlo

    centrum = baker.make(Autor, imiona="Jan", nazwisko="Centralny", pokazuj=True)
    a_blood = baker.make(Autor, imiona="Adam", nazwisko="Bloodowy", pokazuj=True)
    a_inne = baker.make(Autor, imiona="Ewa", nazwisko="Innawska", pokazuj=True)
    blood = baker.make(Zrodlo, nazwa="Blood")
    inne = baker.make(Zrodlo, nazwa="Inne czasopismo")

    w1 = baker.make(Wydawnictwo_Ciagle, zrodlo=blood, rok=2020)
    w1.dodaj_autora(centrum, jednostka)
    w1.dodaj_autora(a_blood, jednostka)

    w2 = baker.make(Wydawnictwo_Ciagle, zrodlo=inne, rok=2020)
    w2.dodaj_autora(centrum, jednostka)
    w2.dodaj_autora(a_inne, jednostka)

    url = reverse("bpp:browse_autor_powiazania_siec", args=[centrum.pk])
    data = client.get(url, {"zrodlo": blood.pk, "depth": 1}).json()

    ids = {n["id"] for n in data["nodes"]}
    assert a_blood.pk in ids
    assert a_inne.pk not in ids  # współautor tylko z innego źródła


@pytest.mark.django_db
def test_siec_filtr_wiele_zrodel(client, jednostka, typy_odpowiedzialnosci):
    from bpp.models import Wydawnictwo_Ciagle, Zrodlo

    centrum = baker.make(Autor, imiona="Jan", nazwisko="Centralny", pokazuj=True)
    a_blood = baker.make(Autor, imiona="Adam", nazwisko="Bloodowy", pokazuj=True)
    a_hema = baker.make(Autor, imiona="Ewa", nazwisko="Hemowska", pokazuj=True)
    a_inne = baker.make(Autor, imiona="Tom", nazwisko="Innowski", pokazuj=True)
    blood = baker.make(Zrodlo, nazwa="Blood")
    hema = baker.make(Zrodlo, nazwa="Hematologia")
    inne = baker.make(Zrodlo, nazwa="Inne")
    for zr, co in [(blood, a_blood), (hema, a_hema), (inne, a_inne)]:
        w = baker.make(Wydawnictwo_Ciagle, zrodlo=zr, rok=2020)
        w.dodaj_autora(centrum, jednostka)
        w.dodaj_autora(co, jednostka)

    url = reverse("bpp:browse_autor_powiazania_siec", args=[centrum.pk])
    # OR po wielu źródłach: Blood lub Hematologia, ale nie Inne
    data = client.get(url, {"zrodlo": [blood.pk, hema.pk], "depth": 1}).json()

    ids = {n["id"] for n in data["nodes"]}
    assert a_blood.pk in ids
    assert a_hema.pk in ids
    assert a_inne.pk not in ids


@pytest.mark.django_db
def test_dane_filtr_tylko_zatrudnieni(client, jednostka):
    # jednostka.uczelnia jest jedyną (więc domyślną) uczelnią — pracownik
    # liczy się jako "aktualnie zatrudniony", gdy jego aktualna_jednostka
    # należy do tej uczelni.
    centrum = baker.make(Autor, pokazuj=True, aktualna_jednostka=None)
    zatrudniony = baker.make(
        Autor,
        imiona="Anna",
        nazwisko="Nowak",
        pokazuj=True,
        aktualna_jednostka=jednostka,
    )
    obcy = baker.make(
        Autor,
        imiona="Bob",
        nazwisko="Obcy",
        pokazuj=True,
        aktualna_jednostka=None,
    )
    for s in (zatrudniony, obcy):
        AuthorConnection.objects.create(
            primary_author=centrum, secondary_author=s, shared_publications_count=3
        )

    url = reverse("bpp:browse_autor_powiazania_dane", args=[centrum.pk])

    # bez filtra — obaj sąsiedzi widoczni
    bez = client.get(url).json()
    assert {n["label"] for n in bez["neighbors"]} == {"Anna Nowak", "Bob Obcy"}

    # z filtrem — tylko zatrudniony w uczelni; centrum zawsze obecne
    data = client.get(url, {"tylko_zatrudnieni": 1}).json()
    assert [n["label"] for n in data["neighbors"]] == ["Anna Nowak"]
    assert data["center"]["id"] == centrum.pk


@pytest.mark.django_db
def test_siec_filtr_tylko_zatrudnieni_centrum_zawsze(client, jednostka):
    # Centrum NIE jest zatrudnione (aktualna_jednostka=None) — i tak musi
    # zostać korzeniem sieci przy aktywnym filtrze.
    centrum = baker.make(Autor, pokazuj=True, aktualna_jednostka=None)
    zatrudniony = baker.make(Autor, pokazuj=True, aktualna_jednostka=jednostka)
    obcy = baker.make(Autor, pokazuj=True, aktualna_jednostka=None)
    AuthorConnection.objects.create(
        primary_author=centrum,
        secondary_author=zatrudniony,
        shared_publications_count=5,
    )
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=obcy, shared_publications_count=4
    )

    url = reverse("bpp:browse_autor_powiazania_siec", args=[centrum.pk])
    data = client.get(url, {"tylko_zatrudnieni": 1, "depth": 1}).json()

    ids = {n["id"] for n in data["nodes"]}
    assert centrum.pk in ids  # centrum zawsze, mimo braku zatrudnienia
    assert zatrudniony.pk in ids
    assert obcy.pk not in ids


@pytest.mark.django_db
def test_siec_filtr_zatrudnieni_pomija_obca_uczelnie(client, jednostka):
    # Sąsiad zatrudniony, ale w INNEJ uczelni — filtr go pomija (sprawdza,
    # że liczy się dopasowanie uczelni, nie samo "ma aktualną jednostkę").
    from bpp.models import Jednostka, Uczelnia

    obca_uczelnia = baker.make(Uczelnia, nazwa="Obca", skrot="OB")
    obcy_wydzial = baker.make(Jednostka, uczelnia=obca_uczelnia, parent=None)
    obca_jednostka = baker.make(
        Jednostka,
        uczelnia=obca_uczelnia,
        parent=obcy_wydzial,
    )

    centrum = baker.make(Autor, pokazuj=True, aktualna_jednostka=jednostka)
    nasz = baker.make(Autor, pokazuj=True, aktualna_jednostka=jednostka)
    obcy = baker.make(Autor, pokazuj=True, aktualna_jednostka=obca_jednostka)
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=nasz, shared_publications_count=5
    )
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=obcy, shared_publications_count=4
    )

    url = reverse("bpp:browse_autor_powiazania_siec", args=[centrum.pk])
    data = client.get(url, {"tylko_zatrudnieni": 1, "depth": 1}).json()

    ids = {n["id"] for n in data["nodes"]}
    assert centrum.pk in ids
    assert nasz.pk in ids
    assert obcy.pk not in ids


@pytest.mark.django_db
def test_zrodla_json_liczy_prace(client, jednostka, typy_odpowiedzialnosci):
    from bpp.models import Wydawnictwo_Ciagle, Zrodlo

    centrum = baker.make(Autor, imiona="Jan", nazwisko="Centralny", pokazuj=True)
    blood = baker.make(Zrodlo, nazwa="Blood")
    rzadkie = baker.make(Zrodlo, nazwa="Rzadkie czasopismo")
    for _ in range(4):  # >= MIN_PRAC_ZRODLO (4) -> w combobox
        w = baker.make(Wydawnictwo_Ciagle, zrodlo=blood, rok=2020)
        w.dodaj_autora(centrum, jednostka)
    for _ in range(2):  # < 4 -> odfiltrowane jako szum
        w = baker.make(Wydawnictwo_Ciagle, zrodlo=rzadkie, rok=2020)
        w.dodaj_autora(centrum, jednostka)

    url = reverse("bpp:browse_autor_powiazania_zrodla", args=[centrum.pk])
    data = client.get(url).json()

    nazwy = {z["nazwa"]: z["n"] for z in data["zrodla"]}
    assert nazwy.get("Blood") == 4
    assert "Rzadkie czasopismo" not in nazwy  # 2 prace < próg


@pytest.mark.django_db
def test_strona_grafu_renderuje_kontener(client):
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pokazuj=True)
    url = reverse("bpp:browse_autor_powiazania", args=[autor.pk])
    resp = client.get(url)
    assert resp.status_code == 200
    tresc = resp.content.decode("utf-8")
    assert 'id="cytoscape-container"' in tresc
    assert f'data-autor-id="{autor.pk}"' in tresc


@pytest.mark.django_db
def test_strona_grafu_404_dla_nieistniejacego_autora(client):
    url = reverse("bpp:browse_autor_powiazania", args=[99999])
    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_strona_grafu_3d_renderuje_kontener(client):
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pokazuj=True)
    url = reverse("bpp:browse_autor_powiazania_3d", args=[autor.pk])
    resp = client.get(url)
    assert resp.status_code == 200
    tresc = resp.content.decode("utf-8")
    assert 'id="siec3d-container"' in tresc
    assert f'data-autor-id="{autor.pk}"' in tresc
    # lazy bundle 3D (nazwa może być zahashowana przez ManifestStaticFiles)
    assert "three-bundle" in tresc


@pytest.mark.django_db
def test_strona_grafu_3d_404_gdy_siec_wylaczona(client, uczelnia):
    uczelnia.pokazuj_siec_powiazan = False
    uczelnia.save()
    autor = baker.make(Autor, pokazuj=True, pokazuj_siec_powiazan=None)
    url = reverse("bpp:browse_autor_powiazania_3d", args=[autor.pk])
    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_strona_grafu_3d_404_dla_nieistniejacego_autora(client):
    url = reverse("bpp:browse_autor_powiazania_3d", args=[99999])
    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_strona_autora_ma_flage_powiazan_true(client):
    centrum = baker.make(Autor, pokazuj=True)
    sasiad = baker.make(Autor, pokazuj=True)
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=sasiad, shared_publications_count=1
    )
    resp = client.get(reverse("bpp:browse_autor", args=[centrum.pk]))
    assert resp.status_code == 200
    assert resp.context["ma_powiazania"] is True


@pytest.mark.django_db
def test_strona_autora_ma_flage_powiazan_false(client):
    centrum = baker.make(Autor, pokazuj=True)
    resp = client.get(reverse("bpp:browse_autor", args=[centrum.pk]))
    assert resp.context["ma_powiazania"] is False


@pytest.mark.django_db
def test_zrodla_obejmuje_cala_widoczna_siec(client, jednostka, typy_odpowiedzialnosci):
    # Lista źródeł = źródła CAŁEJ widocznej sieci, nie tylko centrum. Źródło,
    # które ma wyłącznie autor z poziomu 2, pojawia się dopiero przy depth=2.
    from bpp.models import Wydawnictwo_Ciagle, Zrodlo

    centrum = baker.make(Autor, imiona="Jan", nazwisko="Centralny", pokazuj=True)
    wspolautor = baker.make(Autor, imiona="Anna", nazwisko="Bliska", pokazuj=True)
    daleki = baker.make(Autor, imiona="Bob", nazwisko="Daleki", pokazuj=True)

    bliskie = baker.make(Zrodlo, nazwa="Bliskie")
    posrednie = baker.make(Zrodlo, nazwa="Pośrednie")
    tylko_dalekie = baker.make(Zrodlo, nazwa="Tylko dalekie")

    # >= MIN_PRAC_ZRODLO (4) prac na źródło, by przejść próg comboboxu
    for _ in range(4):
        w = baker.make(Wydawnictwo_Ciagle, zrodlo=bliskie, rok=2020)
        w.dodaj_autora(centrum, jednostka)
        w.dodaj_autora(wspolautor, jednostka)
    for _ in range(4):
        w = baker.make(Wydawnictwo_Ciagle, zrodlo=posrednie, rok=2020)
        w.dodaj_autora(wspolautor, jednostka)
        w.dodaj_autora(daleki, jednostka)
    for _ in range(4):
        w = baker.make(Wydawnictwo_Ciagle, zrodlo=tylko_dalekie, rok=2020)
        w.dodaj_autora(daleki, jednostka)

    # graf BFS jedzie po AuthorConnection — zbuduj go ręcznie, spójnie z pracami
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=wspolautor, shared_publications_count=4
    )
    AuthorConnection.objects.create(
        primary_author=wspolautor, secondary_author=daleki, shared_publications_count=4
    )

    url = reverse("bpp:browse_autor_powiazania_zrodla", args=[centrum.pk])

    # depth=1: widoczni centrum + wspolautor -> "Tylko dalekie" jeszcze nieobecne
    d1 = client.get(url, {"depth": 1, "topn": 10}).json()
    nazwy1 = {z["nazwa"] for z in d1["zrodla"]}
    assert "Bliskie" in nazwy1
    assert "Pośrednie" in nazwy1
    assert "Tylko dalekie" not in nazwy1

    # depth=2: dochodzi 'daleki' -> jego źródło wchodzi do listy
    d2 = client.get(url, {"depth": 2, "topn": 10}).json()
    nazwy2 = {z["nazwa"] for z in d2["zrodla"]}
    assert "Tylko dalekie" in nazwy2


@pytest.mark.django_db
def test_czy_pokazywac_siec_powiazan_dziedziczy_z_uczelni(uczelnia):
    autor = baker.make(Autor, pokazuj_siec_powiazan=None)
    uczelnia.pokazuj_siec_powiazan = True
    uczelnia.save()
    assert autor.czy_pokazywac_siec_powiazan(uczelnia) is True
    uczelnia.pokazuj_siec_powiazan = False
    uczelnia.save()
    assert autor.czy_pokazywac_siec_powiazan(uczelnia) is False


@pytest.mark.django_db
def test_czy_pokazywac_siec_powiazan_autor_nadpisuje_uczelnie(uczelnia):
    uczelnia.pokazuj_siec_powiazan = False
    uczelnia.save()
    autor_tak = baker.make(Autor, pokazuj_siec_powiazan=True)
    autor_nie = baker.make(Autor, pokazuj_siec_powiazan=False)
    assert autor_tak.czy_pokazywac_siec_powiazan(uczelnia) is True
    assert autor_nie.czy_pokazywac_siec_powiazan(uczelnia) is False


@pytest.mark.django_db
def test_czy_pokazywac_siec_powiazan_bez_uczelni_domyslnie_true():
    autor = baker.make(Autor, pokazuj_siec_powiazan=None)
    assert autor.czy_pokazywac_siec_powiazan(None) is True


@pytest.mark.django_db
def test_siec_404_dla_wszystkich_endpointow_gdy_uczelnia_wylacza(client, uczelnia):
    uczelnia.pokazuj_siec_powiazan = False
    uczelnia.save()
    autor = baker.make(Autor, pokazuj=True, pokazuj_siec_powiazan=None)
    for name in (
        "browse_autor_powiazania",
        "browse_autor_powiazania_dane",
        "browse_autor_powiazania_siec",
        "browse_autor_powiazania_zrodla",
    ):
        url = reverse(f"bpp:{name}", args=[autor.pk])
        assert client.get(url).status_code == 404, name


@pytest.mark.django_db
def test_siec_404_gdy_autor_wylacza_mimo_wlaczonej_uczelni(client, uczelnia):
    # uczelnia domyślnie pokazuje, ale autor jawnie wyłącza
    autor = baker.make(Autor, pokazuj=True, pokazuj_siec_powiazan=False)
    url = reverse("bpp:browse_autor_powiazania", args=[autor.pk])
    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_siec_dostepna_gdy_autor_wlacza_mimo_wylaczonej_uczelni(client, uczelnia):
    uczelnia.pokazuj_siec_powiazan = False
    uczelnia.save()
    autor = baker.make(Autor, pokazuj=True, pokazuj_siec_powiazan=True)
    url = reverse("bpp:browse_autor_powiazania", args=[autor.pk])
    assert client.get(url).status_code == 200


@pytest.mark.django_db
def test_ma_powiazania_false_gdy_siec_wylaczona(client, uczelnia):
    uczelnia.pokazuj_siec_powiazan = False
    uczelnia.save()
    centrum = baker.make(Autor, pokazuj=True, pokazuj_siec_powiazan=None)
    sasiad = baker.make(Autor, pokazuj=True)
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=sasiad, shared_publications_count=1
    )
    resp = client.get(reverse("bpp:browse_autor", args=[centrum.pk]))
    assert resp.context["ma_powiazania"] is False


def test_przelicznik_jest_w_celerybeat():
    from django.conf import settings

    nazwy_taskow = {wpis["task"] for wpis in settings.CELERYBEAT_SCHEDULE.values()}
    assert "powiazania_autorow.calculate_author_connections" in nazwy_taskow
