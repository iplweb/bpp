import pytest
from model_bakery import baker

from pbn_api.integrator import (
    wydawnictwa_ciagle_do_synchronizacji,
    wydawnictwa_zwarte_do_synchronizacji,
)

from bpp.const import PBN_MIN_ROK
from bpp.models import (
    Charakter_Formalny,
    Jezyk,
    Status_Korekty,
    Typ_KBN,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)


@pytest.mark.django_db
def test_wydawnictwa_zwarte_do_synchronizacji(pbn_charakter_formalny, pbn_jezyk):
    wejda = []
    nie_wejda = []

    required = {
        "status_korekty": baker.make(Status_Korekty),
        "typ_kbn": baker.make(Typ_KBN),
    }

    wejda.append(
        Wydawnictwo_Zwarte.objects.create(
            tytul_oryginalny="A",
            e_isbn="jest",
            doi="jest",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required
        )
    )

    wejda.append(
        Wydawnictwo_Zwarte.objects.create(
            tytul_oryginalny="B",
            isbn="jest",
            doi="jest",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required
        )
    )

    nadrzedne_www = Wydawnictwo_Zwarte.objects.create(
        tytul_oryginalny="C",
        rok=PBN_MIN_ROK,
        www="jest",
        charakter_formalny=pbn_charakter_formalny,
        jezyk=pbn_jezyk,
        **required
    )
    nadrzedne_public_www = Wydawnictwo_Zwarte.objects.create(
        rok=PBN_MIN_ROK,
        www="jest",
        charakter_formalny=pbn_charakter_formalny,
        jezyk=pbn_jezyk,
        **required
    )

    wejda.append(
        Wydawnictwo_Zwarte.objects.create(
            tytul_oryginalny="D",
            isbn="jest",
            rok=PBN_MIN_ROK,
            wydawnictwo_nadrzedne=nadrzedne_www,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required
        )
    )
    wejda.append(
        Wydawnictwo_Zwarte.objects.create(
            tytul_oryginalny="E",
            isbn="jest",
            rok=PBN_MIN_ROK,
            wydawnictwo_nadrzedne=nadrzedne_public_www,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required
        )
    )

    nie_wejda.append(
        # Charakter formalny bez odpowiednika
        Wydawnictwo_Zwarte.objects.create(
            tytul_oryginalny="F",
            doi="jest",
            isbn="jest",
            rok=PBN_MIN_ROK,
            charakter_formalny=baker.make(Charakter_Formalny, rodzaj_pbn=None),
            jezyk=pbn_jezyk,
            **required
        )
    )

    nie_wejda.append(
        # Brak ISBN oraz E-ISBN
        Wydawnictwo_Zwarte.objects.create(
            tytul_oryginalny="G",
            doi="jest",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required
        )
    )

    nie_wejda.append(
        # Brak www oraz public_www oraz DOI
        Wydawnictwo_Zwarte.objects.create(
            tytul_oryginalny="H",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            isbn="jest",
            jezyk=pbn_jezyk,
            **required
        )
    )

    nie_wejda.append(
        # Jezyk bez odpowiednika w PBN
        Wydawnictwo_Zwarte.objects.create(
            tytul_oryginalny="I",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            isbn="jest",
            jezyk=baker.make(Jezyk, pbn_uid=None),
            **required
        )
    )

    nie_wejda.append(
        Wydawnictwo_Zwarte.objects.create(
            # Rok za wczesny
            tytul_oryginalny="J",
            e_isbn="jest",
            doi="jest",
            rok=PBN_MIN_ROK - 10,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required
        )
    )

    res = list(wydawnictwa_zwarte_do_synchronizacji())
    for elem in wejda:
        assert elem in res, elem.tytul_oryginalny
    for elem in nie_wejda:
        assert elem not in res, elem.tytul_oryginalny


@pytest.mark.django_db
def test_wydawnictwa_ciagle_do_synchronizacji(pbn_charakter_formalny, pbn_jezyk):
    wejda = []
    nie_wejda = []

    required = {
        "status_korekty": baker.make(Status_Korekty),
        "typ_kbn": baker.make(Typ_KBN),
    }

    wejda.append(
        Wydawnictwo_Ciagle.objects.create(
            tytul_oryginalny="A",
            doi="jest",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required
        )
    )

    wejda.append(
        Wydawnictwo_Ciagle.objects.create(
            tytul_oryginalny="B",
            www="jest",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required
        )
    )
    wejda.append(
        Wydawnictwo_Ciagle.objects.create(
            tytul_oryginalny="B",
            public_www="jest",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required
        )
    )

    nie_wejda.append(
        # Charakter formalny bez odpowiednika
        Wydawnictwo_Ciagle.objects.create(
            tytul_oryginalny="F",
            doi="jest",
            rok=PBN_MIN_ROK,
            charakter_formalny=baker.make(Charakter_Formalny, rodzaj_pbn=None),
            jezyk=pbn_jezyk,
            **required
        )
    )

    nie_wejda.append(
        # Brak www oraz public_www oraz DOI
        Wydawnictwo_Ciagle.objects.create(
            tytul_oryginalny="H",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required
        )
    )

    nie_wejda.append(
        # Jezyk bez odpowiednika w PBN
        Wydawnictwo_Ciagle.objects.create(
            tytul_oryginalny="I",
            rok=PBN_MIN_ROK,
            charakter_formalny=pbn_charakter_formalny,
            doi="jest",
            jezyk=baker.make(Jezyk, pbn_uid=None),
            **required
        )
    )

    nie_wejda.append(
        Wydawnictwo_Ciagle.objects.create(
            # Rok za wczesny
            tytul_oryginalny="J",
            rok=PBN_MIN_ROK - 10,
            doi="jest",
            charakter_formalny=pbn_charakter_formalny,
            jezyk=pbn_jezyk,
            **required
        )
    )

    res = list(wydawnictwa_ciagle_do_synchronizacji())
    for elem in wejda:
        assert elem in res, elem.tytul_oryginalny
    for elem in nie_wejda:
        assert elem not in res, elem.tytul_oryginalny
