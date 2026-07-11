import pytest
from model_bakery import baker

from import_sqlite.handlers.patent import PatentData, apply_patent, build_context


@pytest.fixture
def ctx(db, status_korekty):
    uczelnia = baker.make("bpp.Uczelnia", nazwa="UML", skrot="UML")
    obca = baker.make(
        "bpp.Jednostka",
        nazwa="Obca jednostka",
        uczelnia=uczelnia,
        skupia_pracownikow=False,
    )
    uczelnia.obca_jednostka = obca
    uczelnia.save()
    return build_context()


def _pd(**kw):
    base = dict(
        source_id="UML1",
        source_url="http://x/1",
        tytul="T",
        rok=2023,
        numer_zgloszenia="P.1",
        data_zgloszenia=None,
        numer_prawa="Pat.1",
        data_decyzji=None,
        szczegoly="",
        adnotacje="",
        inventors=["Anna Wawruszak"],
    )
    base.update(kw)
    return PatentData(**base)


@pytest.mark.django_db
def test_apply_creates_patent_with_matched_author(
    ctx, typ_odpowiedzialnosci_aut, charakter_pat, jezyk_polski
):
    from bpp.models import Patent

    jedn = baker.make("bpp.Jednostka", uczelnia=ctx.uczelnia, skupia_pracownikow=True)
    a = baker.make(
        "bpp.Autor", nazwisko="Wawruszak", imiona="Anna", aktualna_jednostka=jedn
    )
    status, _ = apply_patent(_pd(), {"Anna Wawruszak": str(a.pk)}, ctx)
    assert status == "UTWORZONY"
    p = Patent.objects.get(numer_prawa_wylacznego="Pat.1")
    assert p.rok == 2023
    assert p.wydzial_id == jedn.pk  # 1. twórca z skupia_pracownikow=True
    pa = p.autorzy_set.get()
    assert pa.autor_id == a.pk and pa.afiliuje is True


@pytest.mark.django_db
def test_apply_nowy_creates_author_unaffiliated(
    ctx, typ_odpowiedzialnosci_aut, charakter_pat, jezyk_polski
):
    from bpp.models import Autor, Patent

    status, _ = apply_patent(_pd(), {"Anna Wawruszak": "NOWY"}, ctx)
    assert status == "UTWORZONY"
    a = Autor.objects.get(nazwisko="Wawruszak", imiona="Anna")
    pa = Patent.objects.get(numer_prawa_wylacznego="Pat.1").autorzy_set.get()
    assert pa.autor_id == a.pk and pa.afiliuje is False


@pytest.mark.django_db
def test_apply_holds_on_unresolved_author(
    ctx, typ_odpowiedzialnosci_aut, charakter_pat, jezyk_polski
):
    from bpp.models import Patent

    status, powod = apply_patent(_pd(), {"Anna Wawruszak": ""}, ctx)
    assert status == "WSTRZYMANY"
    assert "Anna Wawruszak" in powod
    assert not Patent.objects.filter(numer_prawa_wylacznego="Pat.1").exists()


@pytest.mark.django_db
def test_apply_dedupes_same_author_twice(
    ctx, typ_odpowiedzialnosci_aut, charakter_pat, jezyk_polski
):
    from bpp.models import Patent

    a = baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    pd = _pd(inventors=["Jan Kowalski", "Jan Kovalski"])
    decisions = {"Jan Kowalski": str(a.pk), "Jan Kovalski": str(a.pk)}
    status, _ = apply_patent(pd, decisions, ctx)
    assert status == "UTWORZONY"
    p = Patent.objects.get(numer_prawa_wylacznego="Pat.1")
    assert p.autorzy_set.count() == 1  # zdeduplikowane, brak IntegrityError


@pytest.mark.django_db
def test_apply_idempotent_update(
    ctx, typ_odpowiedzialnosci_aut, charakter_pat, jezyk_polski
):
    from bpp.models import Patent

    a = baker.make("bpp.Autor", nazwisko="Wawruszak", imiona="Anna")
    apply_patent(_pd(), {"Anna Wawruszak": str(a.pk)}, ctx)
    status, _ = apply_patent(
        _pd(tytul="Nowy tytuł"), {"Anna Wawruszak": str(a.pk)}, ctx
    )
    assert status == "ZAKTUALIZOWANY"
    assert Patent.objects.filter(numer_prawa_wylacznego="Pat.1").count() == 1
    assert (
        Patent.objects.get(numer_prawa_wylacznego="Pat.1").tytul_oryginalny
        == "Nowy tytuł"
    )
