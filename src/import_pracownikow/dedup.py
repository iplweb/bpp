"""Kierowanie operacji zatrudnienia na rekord ORYGINALNY/GŁÓWNY autora.

Gdy dopasowanie po nazwisku trafia na rekord-DUPLIKAT, import ma podpiąć
zatrudnienie (``Autor_Jednostka``: jednostka, miejsce pracy, przepięcia) do
rekordu ORYGINALNEGO — tego z odpowiednikiem w API instytucjonalnym PBN
(``OsobaZInstytucji`` → ``Scientist`` → ``rekord_w_bpp``), a więc z ORCID i
tytułem. **Żaden rekord nie jest scalany ani usuwany** — zmieniamy wyłącznie,
DO KTÓREGO autora podpięte zostaje zatrudnienie.

Źródło prawdy o parach duplikat→oryginał to zmaterializowana tabela skanu
deduplikatora ``deduplikator_autorow.DuplicateCandidate`` (tańsze i przeglądane
przez operatora niż liczenie ``analiza_duplikatow`` per wiersz). Warunki
przekierowania:

- para ``duplicate_autor == <trafiony autor>`` istnieje w skanie,
- ``main_osoba_z_instytucji`` ustawione (oryginał pochodzi z API
  instytucjonalnego PBN — spełnia wymóg „z odpowiedniego API"),
- ``confidence_percent >= PROG_KANONICZNY`` (konserwatywnie, wyżej niż próg
  wyświetlania deduplikatora ``MIN_PEWNOSC_DO_WYSWIETLENIA`` = 0.5),
- para NIE oznaczona jako ``NOT_DUPLICATE``,
- autor NIE ma weta ``NotADuplicate``.

Brak pasującej pary → funkcja jest **no-opem** (zwraca wejściowego autora),
więc import bez uruchomionego skanu działa jak dotąd.
"""

from deduplikator_autorow.models import DuplicateCandidate, NotADuplicate

# Minimalny confidence_percent (0.0–1.0) pary duplikat→oryginał, przy którym
# ufamy relacji na tyle, by przekierować zatrudnienie na oryginał. Wyżej niż
# próg WYŚWIETLANIA deduplikatora (0.5) — auto-decyzja musi być pewniejsza.
PROG_KANONICZNY = 0.80


def kanoniczny_autor(autor):
    """Zwraca rekord ORYGINALNY dla ``autor`` albo ``autor`` (no-op).

    Idempotentne: dla rekordu, który nie występuje jako ``duplicate_autor``
    pewnej pary (np. sam jest oryginałem), zwraca wejściowego autora.
    """
    if autor is None:
        return autor
    # Weto operatora — świadomie oznaczony jako NIE-duplikat.
    if NotADuplicate.objects.filter(autor=autor).exists():
        return autor
    kandydat = (
        DuplicateCandidate.objects.filter(
            duplicate_autor=autor,
            # oryginał MUSI mieć odpowiednik w API instytucjonalnym PBN
            main_osoba_z_instytucji__isnull=False,
            confidence_percent__gte=PROG_KANONICZNY,
        )
        .exclude(status=DuplicateCandidate.Status.NOT_DUPLICATE)
        .exclude(main_autor=autor)  # nie kieruj rekordu na samego siebie
        .select_related("main_autor")
        .order_by("-confidence_percent")
        .first()
    )
    if kandydat is None:
        return autor
    return kandydat.main_autor
