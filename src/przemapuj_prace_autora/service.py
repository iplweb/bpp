"""Serwis domenowy przemapowania prac autora między jednostkami.

Wyekstrahowany z ``views._wykonaj_przemapowanie`` (§10 D6/D7): bez ``request``,
bez ``messages`` — wołany zarówno przez ręczny widok, jak i przez fazę commit
importu pracowników (``import_pracownikow.pipeline.integrate``).
"""

from django.db import transaction

from bpp.models import Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor

from .models import PrzemapoaniePracAutora


def _historia_prac_ciaglych(prace_ciagle, jednostka_z):
    """Zbuduj historię prac ciągłych PRZED przemapowaniem.

    Zachowuje klucze czytane przez admin/szablon (``id``, ``tytul``, ``rok``,
    ``zrodlo``) i dokłada ``autor_rekord_pk`` (pk Wydawnictwo_Ciagle_Autor) oraz
    ``jednostka_z_pk`` — potrzebne do jednoznacznego undo.
    """
    historia = []
    for praca_autor in prace_ciagle:
        rekord = praca_autor.rekord
        historia.append(
            {
                "id": rekord.id,
                "tytul": rekord.tytul_oryginalny,
                "rok": rekord.rok,
                "zrodlo": (
                    str(rekord.zrodlo)
                    if hasattr(rekord, "zrodlo") and rekord.zrodlo
                    else None
                ),
                "autor_rekord_pk": praca_autor.pk,
                "jednostka_z_pk": jednostka_z.pk,
            }
        )
    return historia


def _historia_prac_zwartych(prace_zwarte, jednostka_z):
    """Zbuduj historię prac zwartych PRZED przemapowaniem (patrz wyżej)."""
    historia = []
    for praca_autor in prace_zwarte:
        rekord = praca_autor.rekord
        historia.append(
            {
                "id": rekord.id,
                "tytul": rekord.tytul_oryginalny,
                "rok": rekord.rok,
                "isbn": (rekord.isbn if hasattr(rekord, "isbn") else None),
                "wydawnictwo": (
                    rekord.wydawnictwo if hasattr(rekord, "wydawnictwo") else None
                ),
                "autor_rekord_pk": praca_autor.pk,
                "jednostka_z_pk": jednostka_z.pk,
            }
        )
    return historia


def przemapuj(autor, jednostka_z, jednostka_do, user, zrodlowy_import=None):
    """Przenieś prace autora afiliowane do ``jednostka_z`` na ``jednostka_do``.

    Zakres (D7): wszystkie prace ze ``jednostka_z``, niezależnie od roku. Zwraca
    utworzony rekord audytu ``PrzemapoaniePracAutora``.
    """
    with transaction.atomic():
        prace_ciagle = Wydawnictwo_Ciagle_Autor.objects.filter(
            autor=autor, jednostka=jednostka_z
        ).select_related("rekord")
        prace_ciagle_historia = _historia_prac_ciaglych(prace_ciagle, jednostka_z)
        liczba_prac_ciaglych = len(prace_ciagle_historia)
        prace_ciagle.update(jednostka=jednostka_do)

        prace_zwarte = Wydawnictwo_Zwarte_Autor.objects.filter(
            autor=autor, jednostka=jednostka_z
        ).select_related("rekord")
        prace_zwarte_historia = _historia_prac_zwartych(prace_zwarte, jednostka_z)
        liczba_prac_zwartych = len(prace_zwarte_historia)
        prace_zwarte.update(jednostka=jednostka_do)

        return PrzemapoaniePracAutora.objects.create(
            autor=autor,
            jednostka_z=jednostka_z,
            jednostka_do=jednostka_do,
            liczba_prac_ciaglych=liczba_prac_ciaglych,
            liczba_prac_zwartych=liczba_prac_zwartych,
            utworzono_przez=user,
            prace_ciagle_historia=prace_ciagle_historia,
            prace_zwarte_historia=prace_zwarte_historia,
            zrodlowy_import=zrodlowy_import,
        )
