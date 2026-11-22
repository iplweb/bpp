"""Powiązania od rekordów z kosza nie blokują kosza; przywrócenie rekordu
wskazującego na kosz jest odmawiane (``WskazaniaWKoszu``).

Decyzja właściciela (listopad 2026): autora, którego jedyna praca jest
w koszu, da się wyrzucić do kosza (tak samo słowniki). Spójność trzyma
druga strona — ``restore()`` publikacji (słownika, zgłoszenia…) odmawia,
dopóki to, na co wskazuje (także przez dzieci: autorstwa, promotor, autorzy
zgłoszenia, redakcja źródła, powiązania habilitacji), jest w koszu. Bez
kaskadowego przywracania. ``bpp_autorzy_mat`` nigdy nie zawiera autora
z kosza (migracja ``0525``).
"""

import pytest
from django.db import connection
from django.db.models import ProtectedError
from django.urls import reverse
from model_bakery import baker

from bpp.models import (
    Autor,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Redakcja_Zrodla,
    Wydawca,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Zrodlo,
)
from bpp.models.praca_habilitacyjna import Publikacja_Habilitacyjna
from bpp.models.soft_delete import KonfliktPrzywracania, WskazaniaWKoszu
from zglos_publikacje.models import Zgloszenie_Publikacji, Zgloszenie_Publikacji_Autor


def _url(obj):
    return reverse(
        f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change",
        args=[obj.pk],
    )


def _w_koszu(obj):
    return type(obj).global_objects.get(pk=obj.pk).deleted_at is not None


def _autorzy_mat(autor):
    with connection.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM bpp_autorzy_mat WHERE autor_id = %s", [autor.pk]
        )
        return cur.fetchone()[0]


@pytest.fixture
def praca_z_autorem(bez_celery):
    autor = baker.make(Autor, nazwisko="Koszowy", imiona="Jan")
    praca = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Praca w koszu")
    baker.make(Wydawnictwo_Ciagle_Autor, autor=autor, rekord=praca)
    return autor, praca


# --- kosz: powiązania od rekordów z kosza nie blokują ---------------------


@pytest.mark.django_db
def test_autor_z_jedyna_praca_w_koszu_trafia_do_kosza(praca_z_autorem):
    autor, praca = praca_z_autorem
    praca.delete()

    autor.delete()

    assert _w_koszu(autor)


@pytest.mark.django_db
def test_autor_z_zywa_praca_nadal_zablokowany(praca_z_autorem):
    autor, _ = praca_z_autorem
    with pytest.raises(ProtectedError):
        autor.delete()
    assert not _w_koszu(autor)


@pytest.mark.django_db
def test_autor_z_praca_w_koszu_i_zywa_praca_zablokowany(praca_z_autorem):
    autor, praca = praca_z_autorem
    druga = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Żywa")
    baker.make(Wydawnictwo_Ciagle_Autor, autor=autor, rekord=druga)
    praca.delete()

    with pytest.raises(ProtectedError) as exc:
        autor.delete()
    grupy = {g.etykieta: g for g in exc.value.grupy}
    grupa = grupy["Autorstwa w wydawnictwach ciągłych"]
    assert grupa.liczba == 1
    assert [p.obj for p in grupa.pozycje] == [druga]


@pytest.mark.django_db
def test_powiazania_w_koszu_autora(praca_z_autorem):
    autor, praca = praca_z_autorem
    assert autor.powiazania_w_koszu() == []
    praca.delete()
    grupy = autor.powiazania_w_koszu()
    assert [(g.etykieta, g.liczba) for g in grupy] == [
        ("Autorstwa w wydawnictwach ciągłych", 1)
    ]
    assert grupy[0].pozycje[0].obj == praca


# --- przywracanie: odmowa, gdy wskazuje na kosz -------------------------------


@pytest.mark.django_db
def test_przywrocenie_pracy_z_autorem_w_koszu_odmowa(praca_z_autorem):
    autor, praca = praca_z_autorem
    praca.delete()
    autor.delete()

    with pytest.raises(WskazaniaWKoszu) as exc:
        praca.restore()
    assert isinstance(exc.value, KonfliktPrzywracania)
    assert "Najpierw przywróć z kosza" in str(exc.value)
    assert f"autor „{autor}”" in str(exc.value)
    assert exc.value.obiekty == [Autor.global_objects.get(pk=autor.pk)]
    assert _w_koszu(praca)

    # Po przywróceniu autora — praca wraca.
    Autor.global_objects.get(pk=autor.pk).restore()
    praca.refresh_from_db()
    praca.restore()
    assert not _w_koszu(praca)


@pytest.mark.django_db
def test_zrodlo_z_artykulem_w_koszu(bez_celery):
    zrodlo = baker.make(Zrodlo, nazwa="Źródło z koszem")
    artykul = baker.make(Wydawnictwo_Ciagle, zrodlo=zrodlo)
    with pytest.raises(ProtectedError):
        zrodlo.delete()

    artykul.delete()
    zrodlo.delete()
    assert _w_koszu(zrodlo)

    with pytest.raises(WskazaniaWKoszu) as exc:
        artykul.restore()
    assert "źródło „Źródło z koszem”" in str(exc.value)

    Zrodlo.global_objects.get(pk=zrodlo.pk).restore()
    artykul.refresh_from_db()
    artykul.restore()
    assert not _w_koszu(artykul)


@pytest.mark.django_db
def test_wydawca_z_ksiazka_w_koszu(bez_celery):
    wydawca = baker.make(Wydawca, nazwa="Wydawca z koszem")
    ksiazka = baker.make(Wydawnictwo_Zwarte, wydawca=wydawca)
    with pytest.raises(ProtectedError):
        wydawca.delete()

    ksiazka.delete()
    wydawca.delete()

    with pytest.raises(WskazaniaWKoszu) as exc:
        ksiazka.restore()
    assert "Wydawca z koszem" in str(exc.value)

    Wydawca.global_objects.get(pk=wydawca.pk).restore()
    ksiazka.refresh_from_db()
    ksiazka.restore()
    assert not _w_koszu(ksiazka)


@pytest.mark.django_db
def test_promotor_doktoratu_w_koszu(bez_celery):
    promotor = baker.make(Autor, nazwisko="Promotor")
    doktorat = baker.make(Praca_Doktorska, promotor=promotor)
    with pytest.raises(ProtectedError):
        promotor.delete()

    doktorat.delete()
    promotor.delete()

    with pytest.raises(WskazaniaWKoszu):
        doktorat.restore()


@pytest.mark.django_db
def test_autor_zgloszenia_w_koszu(bez_celery):
    autor = baker.make(Autor, nazwisko="Zgłaszający")
    zgloszenie = baker.make(
        Zgloszenie_Publikacji, email="a@example.com", rok=2024, tytul_oryginalny="Z"
    )
    baker.make(Zgloszenie_Publikacji_Autor, rekord=zgloszenie, autor=autor, rok=2024)
    with pytest.raises(ProtectedError):
        autor.delete()

    zgloszenie.delete()
    autor.delete()

    with pytest.raises(WskazaniaWKoszu):
        zgloszenie.restore()

    Autor.global_objects.get(pk=autor.pk).restore()
    zgloszenie.refresh_from_db()
    zgloszenie.restore()
    assert not _w_koszu(zgloszenie)


@pytest.mark.django_db
def test_redaktor_zrodla_w_koszu(bez_celery):
    """Redakcja źródła żyje ze źródłem (``POLE_RODZICA_KOSZA``)."""
    redaktor = baker.make(Autor, nazwisko="Redaktor")
    zrodlo = baker.make(Zrodlo)
    baker.make(Redakcja_Zrodla, zrodlo=zrodlo, redaktor=redaktor, od_roku=2020)
    with pytest.raises(ProtectedError):
        redaktor.delete()

    zrodlo.delete()
    redaktor.delete()

    with pytest.raises(WskazaniaWKoszu):
        zrodlo.restore()


@pytest.mark.django_db
def test_habilitacja_wskazujaca_publikacje_w_koszu(bez_celery):
    """GenericFK ``Publikacja_Habilitacyjna`` — w obie strony."""
    artykul = baker.make(Wydawnictwo_Ciagle)
    habilitacja = baker.make(Praca_Habilitacyjna)
    baker.make(
        Publikacja_Habilitacyjna, praca_habilitacyjna=habilitacja, publikacja=artykul
    )
    with pytest.raises(ProtectedError):
        artykul.delete()

    habilitacja.delete()
    artykul.delete()
    assert [g.liczba for g in artykul.powiazania_w_koszu()] == [1]

    with pytest.raises(WskazaniaWKoszu):
        habilitacja.restore()


@pytest.mark.django_db
def test_rozdzial_ksiazki_w_koszu(bez_celery):
    ksiazka = baker.make(Wydawnictwo_Zwarte)
    rozdzial = baker.make(Wydawnictwo_Zwarte, wydawnictwo_nadrzedne=ksiazka)
    rozdzial.delete()
    ksiazka.delete()

    with pytest.raises(WskazaniaWKoszu):
        rozdzial.restore()


@pytest.mark.django_db
def test_alias_wydawcy_w_koszu(bez_celery):
    glowny = baker.make(Wydawca, nazwa="Główny")
    alias = baker.make(Wydawca, nazwa="Alias", alias_dla=glowny)
    alias.delete()
    glowny.delete()

    with pytest.raises(WskazaniaWKoszu):
        alias.restore()


@pytest.mark.django_db
def test_przywrocenie_bez_wskazan_w_koszu_dziala(praca_z_autorem):
    _, praca = praca_z_autorem
    praca.delete()
    praca.restore()
    assert not _w_koszu(praca)


# --- admin --------------------------------------------------------------------


@pytest.mark.django_db
def test_admin_przycisk_przywroc_pokazuje_komunikat(superuser_client, praca_z_autorem):
    autor, praca = praca_z_autorem
    praca.delete()
    autor.delete()

    resp = superuser_client.post(
        reverse("admin:bpp_wydawnictwo_ciagle_przywroc", args=[praca.pk]),
        follow=True,
    )
    assert resp.status_code == 200
    tresc = resp.content.decode("utf-8")
    assert "Najpierw przywróć z kosza" in tresc
    assert f'href="{_url(autor)}"' in tresc
    assert _w_koszu(praca)


@pytest.mark.django_db
def test_admin_akcja_przywroc_pokazuje_komunikat(superuser_client, praca_z_autorem):
    autor, praca = praca_z_autorem
    praca.delete()
    autor.delete()

    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist") + "?is_deleted=true"
    resp = superuser_client.post(
        url,
        {"action": "przywroc_zaznaczone", "_selected_action": [str(praca.pk)]},
    )
    assert resp.status_code in (200, 302)
    resp = superuser_client.get(url)
    tresc = resp.content.decode("utf-8")
    assert "Najpierw przywróć z kosza" in tresc
    assert f'href="{_url(autor)}"' in tresc
    assert _w_koszu(praca)


@pytest.mark.django_db
def test_admin_potwierdzenie_kosza_autora_z_praca_w_koszu(
    superuser_client, praca_z_autorem
):
    autor, praca = praca_z_autorem
    praca.delete()

    resp = superuser_client.get(reverse("admin:bpp_autor_delete", args=[autor.pk]))
    assert resp.status_code == 200
    tresc = resp.content.decode("utf-8")
    assert "Tak, przenieś do kosza" in tresc
    assert "Powiązane rekordy w koszu: 1" in tresc
    assert "ich przywrócenie będzie wymagało najpierw przywrócenia" in tresc
    assert f'href="{_url(praca)}"' in tresc

    resp = superuser_client.post(
        reverse("admin:bpp_autor_delete", args=[autor.pk]), {"post": "yes"}
    )
    assert resp.status_code == 302
    assert _w_koszu(autor)


@pytest.mark.django_db
def test_admin_potwierdzenie_kosza_bez_powiazan_w_koszu(superuser_client):
    autor = baker.make(Autor)
    tresc = superuser_client.get(
        reverse("admin:bpp_autor_delete", args=[autor.pk])
    ).content.decode("utf-8")
    assert "Tak, przenieś do kosza" in tresc
    assert "Powiązane rekordy w koszu" not in tresc


# --- bpp_autorzy_mat ------------------------------------------------------------


@pytest.mark.django_db
def test_autorzy_mat_bez_autora_z_kosza_po_przywroceniach(praca_z_autorem):
    autor, praca = praca_z_autorem
    assert _autorzy_mat(autor) == 1

    praca.delete()
    autor.delete()
    assert _autorzy_mat(autor) == 0

    Autor.global_objects.get(pk=autor.pk).restore()
    assert _autorzy_mat(autor) == 0  # praca nadal w koszu
    praca.refresh_from_db()
    praca.restore()
    assert _autorzy_mat(autor) == 1


@pytest.mark.django_db
def test_autorzy_mat_nie_przyjmuje_autora_z_kosza(bez_celery):
    """Siatka SQL (``0525``): nawet gdy kod ominie warstwę Pythona i dopisze
    autora z kosza do żywej publikacji, ``bpp_autorzy_mat`` go nie ma;
    wraca dopiero po przywróceniu autora."""
    autor = baker.make(Autor)
    autor.delete()
    praca = baker.make(Wydawnictwo_Ciagle)

    baker.make(Wydawnictwo_Ciagle_Autor, autor=autor, rekord=praca)
    assert _autorzy_mat(autor) == 0

    Autor.global_objects.get(pk=autor.pk).restore()
    assert _autorzy_mat(autor) == 1


@pytest.mark.django_db
def test_autorzy_mat_przepiecie_autorstwa_na_autora_z_kosza(praca_z_autorem):
    """Upsert (``ON CONFLICT``) na istniejącym wierszu: przepięcie autorstwa
    na autora z kosza kasuje wiersz, a nie zostawia nieaktualnego."""
    autor, praca = praca_z_autorem
    z_kosza = baker.make(Autor)
    z_kosza.delete()

    wca = Wydawnictwo_Ciagle_Autor.objects.get(rekord=praca, autor=autor)
    wca.autor = z_kosza
    wca.save()

    assert _autorzy_mat(autor) == 0
    assert _autorzy_mat(z_kosza) == 0
