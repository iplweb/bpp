import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.db import connection
from model_bakery import baker

from bpp.models import (
    Grant,
    Grant_Rekordu,
    OplatyPublikacjiLog,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Ciagle_Streszczenie,
    Wydawnictwo_Ciagle_Tytul,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
    Wydawnictwo_Zwarte_Streszczenie,
    Wydawnictwo_Zwarte_Tytul,
)


def _confirm_db():
    return f"--confirm-db={connection.settings_dict['NAME']}"


@pytest.mark.django_db(transaction=True)
def test_wyczysc_publikacje_importu_deletes_publications_and_children():
    ciagle = baker.make(Wydawnictwo_Ciagle)
    zwarte = baker.make(Wydawnictwo_Zwarte)
    child = baker.make(Wydawnictwo_Zwarte, wydawnictwo_nadrzedne=zwarte)

    baker.make(Wydawnictwo_Ciagle_Autor, rekord=ciagle)
    baker.make(Wydawnictwo_Zwarte_Autor, rekord=zwarte)
    baker.make(Wydawnictwo_Zwarte_Autor, rekord=child)
    baker.make(Wydawnictwo_Ciagle_Streszczenie, rekord=ciagle)
    baker.make(Wydawnictwo_Zwarte_Streszczenie, rekord=zwarte)
    baker.make(Wydawnictwo_Ciagle_Tytul, rekord=ciagle, kod_jezyka_pbn="en")
    baker.make(Wydawnictwo_Zwarte_Tytul, rekord=zwarte, kod_jezyka_pbn="en")

    content_type = ContentType.objects.get_for_model(ciagle)
    grant = baker.make(Grant, numer_projektu="TEST-RESET-1")
    Grant_Rekordu.objects.create(
        content_type=content_type,
        object_id=ciagle.pk,
        grant=grant,
    )
    OplatyPublikacjiLog.objects.create(
        content_type=content_type,
        object_id=ciagle.pk,
        changed_by="test",
    )

    call_command(
        "wyczysc_publikacje_importu",
        "--yes-i-am-sure",
        _confirm_db(),
    )

    assert Wydawnictwo_Ciagle.objects.count() == 0
    assert Wydawnictwo_Zwarte.objects.count() == 0
    assert Wydawnictwo_Ciagle_Autor.objects.count() == 0
    assert Wydawnictwo_Zwarte_Autor.objects.count() == 0
    assert Wydawnictwo_Ciagle_Streszczenie.objects.count() == 0
    assert Wydawnictwo_Zwarte_Streszczenie.objects.count() == 0
    assert Wydawnictwo_Ciagle_Tytul.objects.count() == 0
    assert Wydawnictwo_Zwarte_Tytul.objects.count() == 0
    assert Grant.objects.filter(pk=grant.pk).exists()
    assert Grant_Rekordu.objects.count() == 0
    assert OplatyPublikacjiLog.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_wyczysc_publikacje_importu_dry_run_does_not_delete():
    baker.make(Wydawnictwo_Ciagle)

    call_command("wyczysc_publikacje_importu", "--dry-run")

    assert Wydawnictwo_Ciagle.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_wyczysc_publikacje_importu_can_clean_only_ciagle():
    baker.make(Wydawnictwo_Ciagle)
    zwarte = baker.make(Wydawnictwo_Zwarte)

    call_command(
        "wyczysc_publikacje_importu",
        "--ciagle",
        "--yes-i-am-sure",
        _confirm_db(),
    )

    assert Wydawnictwo_Ciagle.objects.count() == 0
    assert list(Wydawnictwo_Zwarte.objects.values_list("pk", flat=True)) == [zwarte.pk]
