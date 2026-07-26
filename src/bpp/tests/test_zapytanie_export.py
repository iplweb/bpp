import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from bpp.const import GR_WPROWADZANIE_DANYCH


def url(export_format, **params):
    return (
        reverse("bpp:zapytanie_eksport", kwargs={"export_format": export_format})
        + "?"
        + "&".join(f"{k}={v}" for k, v in params.items())
    )


@pytest.fixture
def redaktor(client, admin_user):
    client.force_login(admin_user)
    return client


@pytest.mark.django_db
def test_eksport_csv_ma_naglowek_i_wiersz(redaktor, wydawnictwo_ciagle, denorms):
    # Rekord to zdenormalizowany cache — bez flush() queryset byłby pusty i
    # test przeszedłby "fałszywie" (patrz sekcja o konwencjach testowych).
    denorms.flush()

    res = redaktor.get(
        url("csv", model="rekord", query=f"rok+%3D+{wydawnictwo_ciagle.rok}")
    )

    assert res.status_code == 200
    assert res["Content-Type"].startswith("text/csv")
    assert b"tytul_oryginalny" in res.content
    assert wydawnictwo_ciagle.tytul_oryginalny.encode() in res.content


@pytest.mark.django_db
def test_eksport_xlsx(redaktor, wydawnictwo_ciagle, denorms):
    denorms.flush()

    res = redaktor.get(
        url("xlsx", model="rekord", query=f"rok+%3D+{wydawnictwo_ciagle.rok}")
    )

    assert "spreadsheetml" in res["Content-Type"]


@pytest.mark.django_db
def test_eksport_html_z_postaci_lista(redaktor, wydawnictwo_ciagle, denorms):
    denorms.flush()

    res = redaktor.get(
        url(
            "html",
            model="rekord",
            query=f"rok+%3D+{wydawnictwo_ciagle.rok}",
            postac="list",
        )
    )

    assert res["Content-Type"].startswith("text/html")
    # sanitize_export_html (nh3) zdejmuje atrybut class — "multiseek-list-
    # report" istnieje tylko w renderze na stronie, nie w eksporcie.
    # Asercja na strukturze (<ol>, nie <table>) i realnej treści rekordu.
    assert b"<ol" in res.content
    assert b"<table" not in res.content
    assert wydawnictwo_ciagle.tytul_oryginalny.encode() in res.content


@pytest.mark.django_db
def test_eksport_bib_tylko_przy_postaci_bibtex(redaktor, wydawnictwo_ciagle, denorms):
    denorms.flush()

    zle = redaktor.get(
        url(
            "bib",
            model="rekord",
            query=f"rok+%3D+{wydawnictwo_ciagle.rok}",
            postac="list",
        )
    )
    assert zle.status_code == 400

    dobrze = redaktor.get(
        url(
            "bib",
            model="rekord",
            query=f"rok+%3D+{wydawnictwo_ciagle.rok}",
            postac="bibtex",
        )
    )
    assert dobrze.status_code == 200
    assert "bibtex" in dobrze["Content-Type"]
    assert b"@" in dobrze.content


@pytest.mark.django_db
def test_eksport_nieznany_format_400(redaktor):
    res = redaktor.get(url("pdf", model="rekord", query="rok+%3D+2024"))
    assert res.status_code == 400


@pytest.mark.django_db
def test_eksport_bledne_zapytanie_400(redaktor):
    res = redaktor.get(url("csv", model="rekord", query="rok+%3D%3D%3D"))
    assert res.status_code == 400


@pytest.mark.django_db
def test_eksport_anonim_403(client, wydawnictwo_ciagle):
    res = client.get(url("csv", model="rekord", query="rok+%3D+2024"))
    assert res.status_code in (302, 403)


@pytest.mark.django_db
def test_eksport_staff_poza_grupa_403(client, django_user_model):
    user = django_user_model.objects.create_user(
        username="staff", password="x", is_staff=True
    )
    client.force_login(user)
    res = client.get(url("csv", model="rekord", query="rok+%3D+2024"))
    assert res.status_code == 403


@pytest.mark.django_db
def test_eksport_staff_w_grupie_ma_dostep(
    client, django_user_model, wydawnictwo_ciagle, denorms
):
    denorms.flush()
    user = django_user_model.objects.create_user(
        username="redaktor2", password="x", is_staff=True
    )
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(group)
    client.force_login(user)

    res = client.get(
        url("csv", model="rekord", query=f"rok+%3D+{wydawnictwo_ciagle.rok}")
    )
    assert res.status_code == 200


@pytest.mark.django_db
def test_eksport_sanityzuje_tytul_w_naglowku(redaktor, wydawnictwo_ciagle, denorms):
    """Tytuł jest w pełni user-controlled i trafia do Content-Disposition."""
    denorms.flush()

    res = redaktor.get(
        reverse("bpp:zapytanie_eksport", kwargs={"export_format": "csv"}),
        {
            "model": "rekord",
            "query": f"rok = {wydawnictwo_ciagle.rok}",
            "tytul": 'zły"tytuł\n../etc/passwd',
        },
    )

    disposition = res["Content-Disposition"]
    assert "\n" not in disposition
    assert "../" not in disposition


@pytest.mark.django_db
def test_eksport_dokumentu_powyzej_capu_400(
    redaktor, wydawnictwo_ciagle, denorms, monkeypatch
):
    from bpp.views import zapytanie_export

    # Denorms.flush() jest tu defensywny (patrz task-4-report.md — pole
    # "rok" jest synchronizowane triggerem SQL, nie wymaga flush), ale
    # zostaje dla zgodności z konwencją repo i odporności na przyszłe
    # zmiany zapytania na pole zależne od Pythonowego denorm.
    denorms.flush()
    monkeypatch.setattr(zapytanie_export, "ZAPYTANIE_EXPORT_MAX_DOKUMENT", 0)

    res = redaktor.get(
        url(
            "html",
            model="rekord",
            query=f"rok+%3D+{wydawnictwo_ciagle.rok}",
            postac="list",
        )
    )
    assert res.status_code == 400
    # Komunikat czyta limit ze stałej modułu (monkeypatch = 0), więc nie może
    # być zaszytego „5000" w tekście.
    assert b"maksymalnie 0 rekord" in res.content
