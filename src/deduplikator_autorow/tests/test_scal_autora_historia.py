"""Scalanie autorów zostawia ślad w historii admina (``LogEntry`` + wersja)."""

import pytest
from django.contrib.admin.models import CHANGE, DELETION, LogEntry
from django.urls import reverse
from reversion.models import Version

from deduplikator_autorow.utils.merge import scal_autora


def _wpisy(model_name, pk):
    return LogEntry.objects.filter(
        content_type__model=model_name, object_id=str(pk)
    )


@pytest.mark.django_db
def test_scal_autora_zapisuje_historie(
    autor_maker, tytuly, wydawnictwo_ciagle, jednostka, admin_user, admin_client
):
    glowny = autor_maker(imiona="Jan", nazwisko="Kowalski")
    duplikat = autor_maker(imiona="Jan", nazwisko="Kowalski-Duplikat")
    dup_pk = duplikat.pk
    wydawnictwo_ciagle.dodaj_autora(duplikat, jednostka)

    result = scal_autora(glowny, duplikat, admin_user, skip_pbn=True)
    assert result["success"] is True

    # Autor główny: CHANGE + wersja początkowa i wersja po scaleniu.
    wpis = _wpisy("autor", glowny.pk).get()
    assert wpis.action_flag == CHANGE
    assert wpis.user == admin_user
    assert f"(ID {dup_pk})" in wpis.change_message
    assert "Przeniesiono rekordów: 1" in wpis.change_message
    assert Version.objects.get_for_object(glowny).count() == 2
    resp = admin_client.get(reverse("admin:bpp_autor_history", args=[glowny.pk]))
    assert "Scalono z duplikatem" in resp.content.decode()

    # Praca: CHANGE o zamianie autora.
    wpis = _wpisy("wydawnictwo_ciagle", wydawnictwo_ciagle.pk).get()
    assert wpis.action_flag == CHANGE
    assert "zastąpiony przez" in wpis.change_message

    # Duplikat: DELETION przed usunięciem.
    wpis = _wpisy("autor", dup_pk).get()
    assert wpis.action_flag == DELETION
    assert wpis.user == admin_user


@pytest.mark.django_db
def test_nieudane_scalenie_nie_zostawia_historii(
    autor_maker, tytuly, admin_user, monkeypatch
):
    """Błąd w trakcie scalania wycofuje też wpisy historii (jedna transakcja)."""
    from deduplikator_autorow.utils import merge

    glowny = autor_maker(imiona="Jan", nazwisko="Nowak")
    duplikat = autor_maker(imiona="Jan", nazwisko="Nowak-Duplikat")

    def wybuch(*args, **kwargs):
        raise RuntimeError("bum")

    monkeypatch.setattr(merge, "_transfer_disciplines", wybuch)
    assert scal_autora(glowny, duplikat, admin_user)["success"] is False
    assert not LogEntry.objects.exists()
    assert not Version.objects.get_for_object(glowny).exists()
