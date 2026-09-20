"""Task 3c: warunkowy ``UniqueConstraint`` (``condition=deleted_at__isnull``)
na ``*_Autor`` zamiast ``unique_together``.

Regresja (Task 2->3): odkąd ``*_Autor`` jest soft-delete, ``.delete()``
zostawia wiersz fizycznie w bazie. Klasyczny wzorzec "skasuj autorstwa i
wstaw od nowa" (re-import, korekta kolejności, edycja inline w adminie)
wywala się na ``unique_together``, bo widzi skasowany-miękko wiersz jako
kolizję. Constraint musi więc ignorować wiersze z ``deleted_at`` ustawionym.
"""

import pytest

from bpp.models import Typ_Odpowiedzialnosci
from bpp.models.patent import Patent_Autor
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte_Autor


@pytest.mark.django_db
def test_reinsert_autorstwa_po_soft_delete_patent(
    patent, autor_jan_kowalski, jednostka, typy_odpowiedzialnosci
):
    """Wzorzec "skasuj autorstwa i wstaw od nowa" MUSI działać po soft-delete."""
    Patent_Autor.objects.create(
        rekord=patent,
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.get(skrot="aut."),
        kolejnosc=0,
        zapisany_jako="Kowalski Jan",
    )
    patent.autorzy_set.all().delete()  # soft
    Patent_Autor.objects.create(  # ten sam (rekord, autor, kolejnosc)
        rekord=patent,
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.get(skrot="aut."),
        kolejnosc=0,
        zapisany_jako="Kowalski Jan",
    )
    assert Patent_Autor.objects.filter(rekord=patent).count() == 1
    assert Patent_Autor.global_objects.filter(rekord=patent).count() == 2


@pytest.mark.django_db
def test_reinsert_autorstwa_po_soft_delete_wydawnictwo_ciagle(
    wydawnictwo_ciagle, autor_jan_kowalski, jednostka, typy_odpowiedzialnosci
):
    Wydawnictwo_Ciagle_Autor.objects.create(
        rekord=wydawnictwo_ciagle,
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.get(skrot="aut."),
        kolejnosc=0,
        zapisany_jako="Kowalski Jan",
    )
    wydawnictwo_ciagle.autorzy_set.all().delete()  # soft
    Wydawnictwo_Ciagle_Autor.objects.create(  # ten sam (rekord, autor, kolejnosc)
        rekord=wydawnictwo_ciagle,
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.get(skrot="aut."),
        kolejnosc=0,
        zapisany_jako="Kowalski Jan",
    )
    qs = Wydawnictwo_Ciagle_Autor.objects.filter(rekord=wydawnictwo_ciagle)
    assert qs.count() == 1
    global_manager = Wydawnictwo_Ciagle_Autor.global_objects
    assert global_manager.filter(rekord=wydawnictwo_ciagle).count() == 2


@pytest.mark.django_db
def test_reinsert_autorstwa_po_soft_delete_wydawnictwo_zwarte(
    wydawnictwo_zwarte, autor_jan_kowalski, jednostka, typy_odpowiedzialnosci
):
    Wydawnictwo_Zwarte_Autor.objects.create(
        rekord=wydawnictwo_zwarte,
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.get(skrot="aut."),
        kolejnosc=0,
        zapisany_jako="Kowalski Jan",
    )
    wydawnictwo_zwarte.autorzy_set.all().delete()  # soft
    Wydawnictwo_Zwarte_Autor.objects.create(  # ten sam (rekord, autor, kolejnosc)
        rekord=wydawnictwo_zwarte,
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.get(skrot="aut."),
        kolejnosc=0,
        zapisany_jako="Kowalski Jan",
    )
    qs = Wydawnictwo_Zwarte_Autor.objects.filter(rekord=wydawnictwo_zwarte)
    assert qs.count() == 1
    global_manager = Wydawnictwo_Zwarte_Autor.global_objects
    assert global_manager.filter(rekord=wydawnictwo_zwarte).count() == 2


@pytest.mark.django_db
def test_wciaz_blokuje_prawdziwa_kolizje_niekasowanych_wierszy(
    patent, autor_jan_kowalski, jednostka, typy_odpowiedzialnosci
):
    """Constraint dalej musi łapać kolizję DWÓCH ŻYWYCH wierszy — to nie jest
    zniesienie unikalności, tylko uwzględnienie soft-delete. Ten sam autor,
    ten sam typ odpowiedzialności, dwa różne wiersze -> kolizja na
    (rekord, autor, typ_odpowiedzialnosci)."""
    from django.db import IntegrityError, transaction

    Patent_Autor.objects.create(
        rekord=patent,
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.get(skrot="aut."),
        kolejnosc=0,
        zapisany_jako="Kowalski Jan",
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Patent_Autor.objects.create(
                rekord=patent,
                autor=autor_jan_kowalski,
                jednostka=jednostka,
                typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.get(skrot="aut."),
                kolejnosc=1,  # inna kolejnosc, ale ten sam (rekord, autor, typ)
                zapisany_jako="Kowalski Jan",
            )
