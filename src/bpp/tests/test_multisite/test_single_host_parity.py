"""Parytet single-host strony głównej po wprowadzeniu multi-hosted.

Multi-hosted zawęża dane strony głównej "do uczelni oglądającego". W
konfiguracji single-host (dokładnie jedna uczelnia, ``DJANGO_BPP_HOSTNAMES``
nieustawione) to zawężenie MUSI być no-opem — 5 instalacji single-host nie
może zobaczyć cichej regresji względem ``dev``.

Wektor regresji: bespoke filtr ``autorzy__jednostka__in`` w
``get_uczelnia_context_data`` to INNER JOIN. Ponieważ ``Jednostka.uczelnia``
jest NOT NULL, w single-host WSZYSTKIE jednostki należą do jedynej uczelni —
filtr nie zawęża po uczelni, lecz odsiewa rekordy bez ani jednego wiersza
autorstwa (patenty/wydawnictwa wprowadzone bez autorów). Na ``dev`` takie
rekordy są liczone i pokazywane; po multi-hosted znikały. Centralny helper
``scope_rekord_do_uczelni`` ma guard ``tylko_jedna_uczelnia()`` i takiej
regresji nie wywołuje — te testy pilnują, że warstwa strony głównej też
przez niego przechodzi.
"""

import pytest
from model_bakery import baker

from bpp.models import Uczelnia


@pytest.mark.django_db
def test_single_host_licznik_i_lista_obejmuja_rekord_bez_autorow(
    uczelnia, jednostka, wydawnictwo_ciagle, denorms
):
    """Single-host: rekord bez autorstwa jest liczony i widoczny na liście."""
    from bpp.models.cache import Rekord
    from bpp.views.browse import get_uczelnia_context_data

    assert Uczelnia.objects.count() == 1  # scenariusz single-host
    assert not wydawnictwo_ciagle.autorzy_set.exists()  # rekord bez autorów

    denorms.rebuildall()

    # Premisa: rekord materializuje się w cache mimo braku autorstwa.
    rekord = Rekord.objects.get_for_model(wydawnictwo_ciagle)

    get_uczelnia_context_data.invalidate()
    ctx = get_uczelnia_context_data(uczelnia)

    assert ctx["total_rekord_count"] == 1
    assert rekord.pk in [r.pk for r in ctx["recently_updated"]]


@pytest.mark.django_db
def test_single_host_recent_abstracts_obejmuje_streszczenie_bez_autorow(
    uczelnia, jednostka, wydawnictwo_ciagle, denorms
):
    """Single-host: streszczenie rekordu bez autorstwa trafia do listy."""
    from bpp.models import Wydawnictwo_Ciagle_Streszczenie
    from bpp.views.browse import get_uczelnia_context_data

    streszczenie = baker.make(
        Wydawnictwo_Ciagle_Streszczenie,
        rekord=wydawnictwo_ciagle,
        streszczenie="Treść streszczenia rekordu bez autorów.",
    )
    assert not wydawnictwo_ciagle.autorzy_set.exists()

    denorms.rebuildall()

    get_uczelnia_context_data.invalidate()
    ctx = get_uczelnia_context_data(uczelnia)

    assert streszczenie.pk in [s.pk for s in ctx["recent_abstracts"]]
