import pytest
from dbtemplates.models import Template

from bpp.dbtemplates_sync import usun_dbtemplate_i_przebuduj
from bpp.models import Wydawnictwo_Zwarte
from bpp.models.szablondlaopisubibliograficznego import (
    SzablonDlaOpisuBibliograficznego,
)
from pbn_api.models import Publication


@pytest.mark.django_db
def test_usun_guard_nie_kasuje_gdy_brak_pliku_na_dysku():
    """DB-only custom bez pliku na dysku — NIE kasować (inaczej dyndająca
    nazwa -> TemplateDoesNotExist -> opis wybucha przy flushu denorma)."""
    Template.objects.create(name="tylko-w-bazie-xyz.html", content="treść")
    wynik = usun_dbtemplate_i_przebuduj("tylko-w-bazie-xyz.html", [])
    assert wynik is False
    assert Template.objects.filter(name="tylko-w-bazie-xyz.html").exists()


@pytest.mark.django_db
def test_usun_kasuje_gdy_plik_na_dysku_i_odswieza_opis(wydawnictwo_zwarte):
    """opis_bibliograficzny.html JEST na dysku -> kasuj wiersz; po rebuildzie
    opis pokazuje rodzica z PBN object.book (dowód naprawy FD#329)."""
    pbn_pub = Publication.objects.create(
        mongoId="sync-rozdzial",
        versions=[{"current": True, "object": {"book": {"title": "Rodzic Z Dysku"}}}],
    )
    wydawnictwo_zwarte.pbn_uid = pbn_pub
    wydawnictwo_zwarte.wydawnictwo_nadrzedne = None
    wydawnictwo_zwarte.wydawnictwo_nadrzedne_w_pbn = None
    wydawnictwo_zwarte.informacje = ""
    wydawnictwo_zwarte.zrodlo = None
    wydawnictwo_zwarte.save()

    # Funkcja robi template.delete(); w produkcji leci PO usunięciu FK
    # (migracja), więc nic go nie PROTECT-uje. Odwzoruj: usuń zasiane
    # powiązania (seed z 0295/baseline chroni wiersz -> ProtectedError).
    SzablonDlaOpisuBibliograficznego.objects.all().delete()

    Template.objects.update_or_create(
        name="opis_bibliograficzny.html",
        defaults={"content": "STARY-SZABLON-MARKER"},
    )

    wynik = usun_dbtemplate_i_przebuduj(
        "opis_bibliograficzny.html", [Wydawnictwo_Zwarte], flush=True
    )

    assert wynik is True
    assert not Template.objects.filter(name="opis_bibliograficzny.html").exists()
    wydawnictwo_zwarte.refresh_from_db()
    assert "W: Rodzic Z Dysku." in wydawnictwo_zwarte.opis_bibliograficzny_cache
    assert "STARY-SZABLON-MARKER" not in wydawnictwo_zwarte.opis_bibliograficzny_cache
