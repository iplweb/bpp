"""Sygnał „autor ma odpowiednik w API instytucjonalnym PBN" (``OsobaZInstytucji``).

Wspólne źródło dla wskaźnika PBN-instytucjonalnego w widokach importu
(rezultaty / odpięcia / audyt). ``OsobaZInstytucji.personId`` to OneToOne do
``pbn_api.Scientist``, a ``bpp.Autor.pbn_uid`` to FK do tego samego
``Scientist`` — więc autor ma odpowiednik instytucjonalny, gdy istnieje
``OsobaZInstytucji`` wskazująca na jego ``pbn_uid``.

Preferowana forma to **adnotacja querysetu** (``adnotuj_pbn_instytucjonalny``) —
tabele importu ładują wszystkie wiersze naraz (DataTables bez serwerowego
stronicowania), więc per-obiektowe sprawdzenie dałoby N+1. Wersja
per-autor (``autor_ma_osobe_z_instytucji``) jest dla pojedynczych przypadków.
"""

from django.db.models import Exists, OuterRef

from pbn_api.models import OsobaZInstytucji

# Nazwa adnotacji wystawianej na obiekty querysetu (czytana w szablonach).
FLAGA_PBN_INSTYTUCJONALNY = "autor_z_pbn_inst"


def adnotuj_pbn_instytucjonalny(qs, autor_path="autor"):
    """Dokłada boolean ``autor_z_pbn_inst`` (Exists) do ``qs``.

    ``autor_path`` to ścieżka ORM od modelu querysetu do ``bpp.Autor``
    (np. ``"autor"`` dla wiersza importu, ``"autor_jednostka__autor"`` dla
    odpięcia). Subquery porównuje ``OsobaZInstytucji.personId`` z
    ``<autor_path>__pbn_uid`` wiersza — bez N+1.
    """
    return qs.annotate(
        **{
            FLAGA_PBN_INSTYTUCJONALNY: Exists(
                OsobaZInstytucji.objects.filter(
                    personId=OuterRef(f"{autor_path}__pbn_uid")
                )
            )
        }
    )


def autor_ma_osobe_z_instytucji(autor) -> bool:
    """Czy pojedynczy ``autor`` ma odpowiednik w API instytucjonalnym PBN.

    Jedno zapytanie — do użycia poza listami (listy adnotuj przez
    ``adnotuj_pbn_instytucjonalny``, by uniknąć N+1).
    """
    if autor is None or not autor.pbn_uid_id:
        return False
    return OsobaZInstytucji.objects.filter(personId_id=autor.pbn_uid_id).exists()
