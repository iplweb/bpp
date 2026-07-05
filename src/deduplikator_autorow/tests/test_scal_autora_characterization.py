"""Charakteryzacyjne testy dla scal_autora.

Pinują AKTUALNE zachowanie funkcji scalania duplikatu autora na głównego
autora przed refaktoryzacją (zdjęcie C901). Pokrywają gałęzie
napędzające złożoność: przenoszenie poszczególnych typów relacji (ciągłe,
zwarte, patenty, prace dokt./hab.), transfer dyscyplin, kolizję istniejącej
publikacji, usuwanie dyscypliny przy braku u głównego, kolejkę PBN i
końcowe usunięcie duplikatu.
"""

import pytest
from model_bakery import baker

from bpp.models import (
    Autor_Dyscyplina,
    Patent_Autor,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
)
from deduplikator_autorow.utils.merge import scal_autora
from pbn_export_queue.models import PBN_Export_Queue


@pytest.fixture
def user(db):
    return baker.make("bpp.BppUser")


@pytest.fixture
def main_dup(autor_maker, tytuly):
    glowny = autor_maker(imiona="Jan", nazwisko="Kowalski")
    duplikat = autor_maker(imiona="Jan", nazwisko="Kowalski-Duplikat")
    return glowny, duplikat


def test_scal_autora_reassigns_wydawnictwo_ciagle(
    main_dup, user, wydawnictwo_ciagle, jednostka
):
    """Wydawnictwo_Ciagle_Autor duplikatu przechodzi na głównego autora."""
    glowny, duplikat = main_dup
    dup_pk = duplikat.pk
    wydawnictwo_ciagle.dodaj_autora(duplikat, jednostka)

    result = scal_autora(glowny, duplikat, user, skip_pbn=True)

    assert result["success"] is True
    assert result["total_updated"] == 1
    assert Wydawnictwo_Ciagle_Autor.objects.filter(
        rekord=wydawnictwo_ciagle, autor=glowny
    ).exists()
    assert not Wydawnictwo_Ciagle_Autor.objects.filter(autor_id=dup_pk).exists()
    # Duplikat usunięty na końcu operacji
    assert not type(glowny).objects.filter(pk=dup_pk).exists()
    assert any("Wydawnictwo_Ciagle_Autor" in r for r in result["updated_records"])


def test_scal_autora_reassigns_wydawnictwo_zwarte(
    main_dup, user, wydawnictwo_zwarte, jednostka
):
    """Wydawnictwo_Zwarte_Autor duplikatu przechodzi na głównego autora."""
    glowny, duplikat = main_dup
    wydawnictwo_zwarte.dodaj_autora(duplikat, jednostka)

    result = scal_autora(glowny, duplikat, user, skip_pbn=True)

    assert result["success"] is True
    assert result["total_updated"] == 1
    assert Wydawnictwo_Zwarte_Autor.objects.filter(
        rekord=wydawnictwo_zwarte, autor=glowny
    ).exists()
    assert any("Wydawnictwo_Zwarte_Autor" in r for r in result["updated_records"])


def test_scal_autora_reassigns_patent(main_dup, user, patent, jednostka):
    """Patent_Autor duplikatu przechodzi na głównego autora."""
    glowny, duplikat = main_dup
    patent.dodaj_autora(duplikat, jednostka)

    result = scal_autora(glowny, duplikat, user, skip_pbn=True)

    assert result["success"] is True
    assert result["total_updated"] == 1
    assert Patent_Autor.objects.filter(rekord=patent, autor=glowny).exists()
    assert any("Patent_Autor" in r for r in result["updated_records"])


def test_scal_autora_reassigns_praca_habilitacyjna(main_dup, user, habilitacja):
    """Praca_Habilitacyjna duplikatu przechodzi na głównego autora."""
    glowny, duplikat = main_dup
    habilitacja.autor = duplikat
    habilitacja.save()

    result = scal_autora(glowny, duplikat, user, skip_pbn=True)

    assert result["success"] is True
    assert result["total_updated"] == 1
    habilitacja.refresh_from_db()
    assert habilitacja.autor == glowny
    assert any("Praca_Habilitacyjna" in r for r in result["updated_records"])


def test_scal_autora_reassigns_praca_doktorska(main_dup, user, doktorat):
    """Praca_Doktorska duplikatu przechodzi na głównego autora."""
    glowny, duplikat = main_dup
    doktorat.autor = duplikat
    doktorat.save()

    result = scal_autora(glowny, duplikat, user, skip_pbn=True)

    assert result["success"] is True
    assert result["total_updated"] == 1
    doktorat.refresh_from_db()
    assert doktorat.autor == glowny
    assert any("Praca_Doktorska" in r for r in result["updated_records"])


def test_scal_autora_transfers_disciplines(
    main_dup, user, dyscyplina1, rok, rodzaj_autora_n
):
    """Autor_Dyscyplina duplikatu jest kopiowana do głównego autora."""
    glowny, duplikat = main_dup
    Autor_Dyscyplina.objects.create(
        autor=duplikat,
        rok=rok,
        dyscyplina_naukowa=dyscyplina1,
        rodzaj_autora=rodzaj_autora_n,
    )

    result = scal_autora(glowny, duplikat, user, skip_pbn=True)

    assert result["success"] is True
    assert len(result["disciplines_transferred"]) == 1
    assert Autor_Dyscyplina.objects.filter(
        autor=glowny, rok=rok, dyscyplina_naukowa=dyscyplina1
    ).exists()


def test_scal_autora_does_not_duplicate_existing_discipline(
    main_dup, user, dyscyplina1, rok, rodzaj_autora_n
):
    """Gdy główny autor ma już dyscyplinę na dany rok, nie jest kopiowana."""
    glowny, duplikat = main_dup
    Autor_Dyscyplina.objects.create(
        autor=glowny,
        rok=rok,
        dyscyplina_naukowa=dyscyplina1,
        rodzaj_autora=rodzaj_autora_n,
    )
    Autor_Dyscyplina.objects.create(
        autor=duplikat,
        rok=rok,
        dyscyplina_naukowa=dyscyplina1,
        rodzaj_autora=rodzaj_autora_n,
    )

    result = scal_autora(glowny, duplikat, user, skip_pbn=True)

    assert result["success"] is True
    assert result["disciplines_transferred"] == []
    assert (
        Autor_Dyscyplina.objects.filter(
            autor=glowny, rok=rok, dyscyplina_naukowa=dyscyplina1
        ).count()
        == 1
    )


def test_scal_autora_existing_publication_conflict_deletes_duplicate_record(
    main_dup, user, wydawnictwo_ciagle, jednostka
):
    """Gdy główny ma już tę publikację z tym typem odpowiedzialności,
    rekord duplikatu jest usuwany (nie przemapowany) i dodawane ostrzeżenie."""
    glowny, duplikat = main_dup
    wydawnictwo_ciagle.dodaj_autora(glowny, jednostka)
    wydawnictwo_ciagle.dodaj_autora(duplikat, jednostka)

    result = scal_autora(glowny, duplikat, user, skip_pbn=True)

    assert result["success"] is True
    # Rekord duplikatu usunięty, nie przemapowany -> total_updated == 0
    assert result["total_updated"] == 0
    assert any("już ma publikację" in w for w in result["warnings"])
    # Główny autor wciąż ma dokładnie jeden rekord dla tej publikacji
    assert (
        Wydawnictwo_Ciagle_Autor.objects.filter(
            rekord=wydawnictwo_ciagle, autor=glowny
        ).count()
        == 1
    )


def test_scal_autora_removes_discipline_when_main_lacks_it(
    main_dup, user, wydawnictwo_ciagle, jednostka, dyscyplina1
):
    """Gdy rekord duplikatu ma dyscyplinę, której główny nie posiada
    (brak Autor_Dyscyplina), dyscyplina jest usuwana z rekordu + ostrzeżenie."""
    glowny, duplikat = main_dup
    # Ustaw dyscyplinę bezpośrednio (omijając full_clean), bo duplikat nie ma
    # przypisania Autor_Dyscyplina — to właśnie wymusza ścieżkę usunięcia
    # dyscypliny przy braku jej u głównego autora.
    wca = wydawnictwo_ciagle.dodaj_autora(duplikat, jednostka)
    Wydawnictwo_Ciagle_Autor.objects.filter(pk=wca.pk).update(
        dyscyplina_naukowa=dyscyplina1
    )

    result = scal_autora(glowny, duplikat, user, skip_pbn=True)

    assert result["success"] is True
    assert result["total_updated"] == 1
    wca = Wydawnictwo_Ciagle_Autor.objects.get(rekord=wydawnictwo_ciagle, autor=glowny)
    assert wca.dyscyplina_naukowa is None
    assert any("nie ma dyscypliny" in w for w in result["warnings"])


def test_scal_autora_queues_pbn_when_not_skipped(
    main_dup, user, wydawnictwo_ciagle, jednostka
):
    """skip_pbn=False dodaje publikację do kolejki eksportu PBN."""
    glowny, duplikat = main_dup
    wydawnictwo_ciagle.dodaj_autora(duplikat, jednostka)
    before = PBN_Export_Queue.objects.count()

    result = scal_autora(glowny, duplikat, user, skip_pbn=False)

    assert result["success"] is True
    assert len(result["publications_queued_for_pbn"]) == 1
    assert PBN_Export_Queue.objects.count() == before + 1


def test_scal_autora_skip_pbn_does_not_queue(
    main_dup, user, wydawnictwo_ciagle, jednostka
):
    """skip_pbn=True nie dodaje nic do kolejki PBN."""
    glowny, duplikat = main_dup
    wydawnictwo_ciagle.dodaj_autora(duplikat, jednostka)
    before = PBN_Export_Queue.objects.count()

    result = scal_autora(glowny, duplikat, user, skip_pbn=True)

    assert result["success"] is True
    assert result["publications_queued_for_pbn"] == []
    assert PBN_Export_Queue.objects.count() == before


def test_scal_autora_no_relations_just_deletes_duplicate(main_dup, user):
    """Bez żadnych relacji: sukces, total_updated 0, duplikat usunięty."""
    glowny, duplikat = main_dup
    dup_pk = duplikat.pk

    result = scal_autora(glowny, duplikat, user, skip_pbn=True)

    assert result["success"] is True
    assert result["total_updated"] == 0
    assert result["updated_records"] == []
    assert not type(glowny).objects.filter(pk=dup_pk).exists()


def test_scal_autora_result_dict_shape(main_dup, user):
    """Kształt zwracanego słownika jest stabilny."""
    glowny, duplikat = main_dup

    result = scal_autora(glowny, duplikat, user, skip_pbn=True)

    for key in (
        "success",
        "warnings",
        "updated_records",
        "total_updated",
        "publications_queued_for_pbn",
        "disciplines_transferred",
    ):
        assert key in result
