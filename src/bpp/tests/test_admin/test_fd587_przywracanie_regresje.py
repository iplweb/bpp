"""FD#587: regresje przywracania wersji (przegląd adwersaryjny).

- plik repozytorium przeniesiony do kosza NIE wraca przy przywróceniu
  wersji publikacji (wcześniej zapis surowy zerował ``deleted_at``),
- autor usunięty i dodany ponownie nie blokuje przywrócenia (kolizja
  unikalności (rekord, autor, typ odpowiedzialności)),
- błąd przeliczania punktacji cofa całe przywrócenie,
- przywrócenie dawnego rodzica jednostki nie może zapętlić drzewa.
"""

import sys

import pytest
import reversion
from django.urls import reverse
from model_bakery import baker
from reversion.models import Version

from bpp.const import TRYB_DOSTEPU
from bpp.models import Element_Repozytorium, Jednostka, Wydawnictwo_Ciagle_Autor
from bpp.models.sloty.core import IPunktacjaCacher

pytestmark = pytest.mark.django_db


def _zapisz_wersje(obj):
    with reversion.create_revision():
        obj.save()
    return Version.objects.get_for_object(obj).first()


def _url_wersji(obj, wersja):
    opts = obj._meta
    return reverse(
        f"admin:{opts.app_label}_{opts.model_name}_revision",
        args=(obj.pk, wersja.pk),
    )


def test_przywrocenie_wersji_nie_wyjmuje_pliku_z_kosza(
    admin_client, wydawnictwo_ciagle
):
    element = baker.make(
        Element_Repozytorium,
        rekord=wydawnictwo_ciagle,
        nazwa_pliku="omylkowo-jawny.pdf",
        tryb_dostepu=TRYB_DOSTEPU.JAWNY.value,
        plik=None,
    )
    stara = _zapisz_wersje(wydawnictwo_ciagle)

    element.delete()  # do kosza
    wydawnictwo_ciagle.tytul_oryginalny = "Tytuł po zmianie FD587"
    _zapisz_wersje(wydawnictwo_ciagle)

    url = _url_wersji(wydawnictwo_ciagle, stara)
    podglad = admin_client.get(url).content.decode()
    assert "Nie zostaną przywrócone — są w koszu" in podglad
    assert "♻️ Przywróć tę wersję" in podglad

    res = admin_client.post(url, follow=True)
    assert res.status_code == 200
    assert "Nie przywrócono pozycji usuniętych do kosza" in res.content.decode()

    element = Element_Repozytorium.deleted_objects.get(pk=element.pk)
    assert element.deleted_at is not None
    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.tytul_oryginalny != "Tytuł po zmianie FD587"


def test_przywrocenie_wersji_z_autorem_usunietym_i_dodanym_ponownie(
    admin_client, wydawnictwo_ciagle, autor_jan_nowak, jednostka
):
    """Ponownie dodany autor ma nowy wiersz zajmujący unikalne (rekord,
    autor, typ) — odtworzenie starego wiersza wywalało się na bazie."""
    stary_pk = wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka).pk
    stara = _zapisz_wersje(wydawnictwo_ciagle)

    Wydawnictwo_Ciagle_Autor.objects.get(pk=stary_pk).delete()
    nowy_wiersz = wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)
    assert nowy_wiersz.pk != stary_pk
    wydawnictwo_ciagle.tytul_oryginalny = "Tytuł po zmianie FD587"
    _zapisz_wersje(wydawnictwo_ciagle)

    res = admin_client.post(_url_wersji(wydawnictwo_ciagle, stara))
    assert res.status_code == 302
    assert res.url.endswith(f"/{wydawnictwo_ciagle.pk}/change/")

    wiersze = Wydawnictwo_Ciagle_Autor.objects.filter(rekord=wydawnictwo_ciagle)
    assert list(wiersze.values_list("pk", "autor_id")) == [
        (stary_pk, autor_jan_nowak.pk)
    ]


def test_blad_przeliczania_punktacji_cofa_przywrocenie(
    admin_client, wydawnictwo_ciagle, monkeypatch
):
    stary_tytul = wydawnictwo_ciagle.tytul_oryginalny
    stara = _zapisz_wersje(wydawnictwo_ciagle)
    wydawnictwo_ciagle.tytul_oryginalny = "Tytuł po zmianie FD587"
    _zapisz_wersje(wydawnictwo_ciagle)
    url = _url_wersji(wydawnictwo_ciagle, stara)

    class AwariaPunktacji(Exception):
        pass

    oryginal = IPunktacjaCacher.rebuildEntries

    def awaria(self):
        # Punktację liczy też sam ``save()`` (denorm ``cached_punkty_
        # dyscyplin``) — ten przebieg przepuszczamy. Wywalamy jawne
        # przeliczenie przy przywracaniu, które dawniej szło PO
        # zatwierdzeniu transakcji.
        if sys._getframe(1).f_code.co_name == "przelicz_punkty_dyscyplin":
            return oryginal(self)
        raise AwariaPunktacji

    monkeypatch.setattr(IPunktacjaCacher, "canAdapt", lambda self: True)
    monkeypatch.setattr(IPunktacjaCacher, "rebuildEntries", awaria)
    with pytest.raises(AwariaPunktacji):
        admin_client.post(url)

    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.tytul_oryginalny == "Tytuł po zmianie FD587"
    assert Version.objects.get_for_object(wydawnictwo_ciagle).count() == 2

    # Ponowna próba (już bez awarii) przywraca — nie trafia w „bez zmian”.
    monkeypatch.undo()
    res = admin_client.post(url)
    assert res.status_code == 302
    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.tytul_oryginalny == stary_tytul


def test_przywrocenie_rodzica_jednostki_nie_tworzy_cyklu(admin_client, uczelnia):
    a = baker.make(Jednostka, nazwa="Jednostka A", uczelnia=uczelnia, parent=None)
    b = baker.make(Jednostka, nazwa="Jednostka B", uczelnia=uczelnia, parent=None)
    a.parent = b
    a.save()
    stara = _zapisz_wersje(a)

    # Reorganizacja: A na najwyższy poziom, B pod A.
    a = Jednostka.objects.get(pk=a.pk)
    a.parent = None
    a.save()
    _zapisz_wersje(a)
    b = Jednostka.objects.get(pk=b.pk)
    b.parent = a
    b.save()

    url = _url_wersji(a, stara)
    podglad = admin_client.get(url).content.decode()
    assert "zapętliłoby strukturę" in podglad
    assert "♻️ Przywróć tę wersję" not in podglad

    res = admin_client.post(url)
    assert res.status_code == 302
    assert res.url.endswith(f"/{a.pk}/history/")
    a.refresh_from_db()
    b.refresh_from_db()
    assert a.parent_id is None
    assert b.parent_id == a.pk


def test_przywrocenie_rodzica_jednostki_bez_cyklu_dziala(admin_client, uczelnia):
    a = baker.make(Jednostka, nazwa="Jednostka A", uczelnia=uczelnia, parent=None)
    b = baker.make(Jednostka, nazwa="Jednostka B", uczelnia=uczelnia, parent=None)
    a.parent = b
    a.save()
    stara = _zapisz_wersje(a)
    a = Jednostka.objects.get(pk=a.pk)
    a.parent = None
    a.save()
    _zapisz_wersje(a)

    res = admin_client.post(_url_wersji(a, stara))
    assert res.status_code == 302
    a.refresh_from_db()
    assert a.parent_id == b.pk


def test_przeszkody_sprawdzane_ponownie_w_transakcji(
    admin_client, uczelnia, monkeypatch
):
    """Równoległy zapis między podglądem a zapisem: druga kontrola (pod
    blokadą, w transakcji) przerywa przywrócenie."""
    from bpp.admin.jednostka import JednostkaAdmin

    a = baker.make(Jednostka, nazwa="Jednostka A", uczelnia=uczelnia, parent=None)
    b = baker.make(Jednostka, nazwa="Jednostka B", uczelnia=uczelnia, parent=None)
    a.parent = b
    a.save()
    stara = _zapisz_wersje(a)
    a = Jednostka.objects.get(pk=a.pk)
    a.parent = None
    a.save()
    _zapisz_wersje(a)

    wywolania = []

    def przeszkody(self, obj, wersja):
        wywolania.append(1)
        return [] if len(wywolania) == 1 else ["Zmieniono równolegle."]

    monkeypatch.setattr(JednostkaAdmin, "przeszkody_przywrocenia", przeszkody)
    res = admin_client.post(_url_wersji(a, stara), follow=True)
    assert "Zmieniono równolegle." in res.content.decode()
    a.refresh_from_db()
    assert a.parent_id is None
