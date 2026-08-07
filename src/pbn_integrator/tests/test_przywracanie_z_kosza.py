"""Import z PBN wskrzesza publikacje trafione w koszu i to odnotowuje.

DECYZJA WŁAŚCICIELA (2026-08-08) — ZMIANA wobec decyzji #14 z planu fazy 03.

Plan zakładał „POMIŃ + ZARAPORTUJ", argumentując, że auto-restore pozwoliłby
importowi wskrzeszać rzeczy skasowane celowo. Właściciel systemu rozstrzygnął
inaczej: **PBN jest źródłem prawdy** dla tych publikacji, więc skoro rekord
nadal tam jest, ma wrócić także do BPP.

Ryzyko, na które wskazywała pierwotna decyzja, nie znika — zostaje tylko
przeniesione z „nie róbmy tego" na „róbmy, ale zostaw ślad". Stąd rejestr
``RekordPrzywroconyPrzezImport``: operator, który znajdzie w bazie rekord
skasowany przez siebie tydzień temu, ma gdzie sprawdzić, że wrócił z importu,
kiedy i z którego źródła.
"""

import pytest
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle


@pytest.mark.django_db
def test_przywraca_rekord_z_kosza_i_zapisuje_w_rejestrze():
    from pbn_api.models import Publication
    from pbn_integrator.kosz import przywroc_jesli_w_koszu
    from pbn_integrator.models import RekordPrzywroconyPrzezImport

    publication = baker.make(Publication)
    wc = baker.make(Wydawnictwo_Ciagle, pbn_uid=publication)
    wc.delete()

    assert Wydawnictwo_Ciagle.objects.filter(pk=wc.pk).count() == 0

    przywrocono = przywroc_jesli_w_koszu(wc, publication, "articles")

    assert przywrocono is True
    assert Wydawnictwo_Ciagle.objects.filter(pk=wc.pk).count() == 1, (
        "rekord nie wrocil z kosza"
    )

    wpis = RekordPrzywroconyPrzezImport.objects.get()
    assert wpis.rekord == wc
    assert wpis.pbn_uid_id == publication.pk
    assert wpis.zrodlo_importu == "articles"
    assert wpis.przywrocono is not None


@pytest.mark.django_db
def test_zywy_rekord_nie_trafia_do_rejestru():
    """Wpis w rejestrze ma oznaczać REALNE wskrzeszenie.

    Bez tej asercji rejestr zapełniłby się każdym zwykłym re-importem
    i przestałby cokolwiek znaczyć — a jego jedyną wartością jest to, że
    operator może mu zaufać.
    """
    from pbn_api.models import Publication
    from pbn_integrator.kosz import przywroc_jesli_w_koszu
    from pbn_integrator.models import RekordPrzywroconyPrzezImport

    publication = baker.make(Publication)
    wc = baker.make(Wydawnictwo_Ciagle, pbn_uid=publication)

    assert przywroc_jesli_w_koszu(wc, publication, "articles") is False
    assert not RekordPrzywroconyPrzezImport.objects.exists()


@pytest.mark.django_db
def test_niemodelowy_wynik_matchingu_nie_wywala_helpera():
    """``rekord_w_bpp`` bywa STRINGIEM.

    Przy wielu trafieniach po ``pbn_uid`` zwraca sklejone tytuły (zachowanie
    historyczne, utrzymane w Tasku 2). Helper stoi na ścieżce importu, więc
    musi to przyjąć bez wyjątku — inaczej wywróciłby cały przebieg z powodu,
    który z koszem nie ma nic wspólnego.
    """
    from pbn_api.models import Publication
    from pbn_integrator.kosz import przywroc_jesli_w_koszu

    publication = baker.make(Publication)

    assert przywroc_jesli_w_koszu("Tytul A ;; Tytul B", publication, "books") is False
    assert przywroc_jesli_w_koszu(None, publication, "books") is False
