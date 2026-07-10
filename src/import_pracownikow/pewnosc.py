"""Status pewności dopasowania autora (§8 spec).

Czysta funkcja ``oblicz_status_pewnosci`` liczy status WPROST z listy kandydatów
zwróconej przez ``import_common.core.autor.znajdz_kandydatow_autora`` (posortowanej
malejąco po ``pewnosc``) — NIE z ``matchuj_autora`` (poza priorytetową ścieżką po
ID, sygnalizowaną ``match_po_id``). Stałe ``STATUS_*`` mieszkają tutaj, a nie na
modelu, żeby model, pipeline i widoki dzieliły jedno źródło prawdy bez importu ORM
w warstwie logiki.
"""

from import_common.core.autor import PEWNOSC_IEXACT, PEWNOSC_MIN_AUTOMATYCZNA

STATUS_TWARDY = "twardy"
STATUS_ZGADYWANIE = "zgadywanie"
STATUS_WIELU = "wielu"
STATUS_BRAK = "brak"

STATUS_CHOICES = [
    (STATUS_TWARDY, "twardy match"),
    (STATUS_ZGADYWANIE, "zgadywanie"),
    (STATUS_WIELU, "wielu kandydatów"),
    (STATUS_BRAK, "brak dopasowania"),
]

# status → (klasa Foundation label, ikona Foundation-Icons, etykieta). Foundation
# labels (success/warning/primary/secondary) są w built-in CSS — bez SCSS/grunt.
STATUS_DISPLAY = {
    STATUS_TWARDY: ("success", "fi-check", "twardy match"),
    STATUS_ZGADYWANIE: ("warning", "fi-flag", "zgadywanie"),
    STATUS_WIELU: ("primary", "fi-page-multiple", "wielu kandydatów"),
    STATUS_BRAK: ("secondary", "fi-minus-circle", "brak dopasowania"),
}


def oblicz_status_pewnosci(kandydaci, *, match_po_id):
    """Zwraca jeden ze ``STATUS_*`` dla listy ``KandydatAutora`` (DESC po
    ``pewnosc``). Reguła „czystego zwycięzcy": ``twardy``/``zgadywanie`` wymaga
    DOKŁADNIE jednego kandydata na najwyższym tierze; remis → ``wielu``."""
    if match_po_id:
        return STATUS_TWARDY
    if not kandydaci:
        return STATUS_BRAK

    najwyzsza = kandydaci[0].pewnosc
    top_tier = [k for k in kandydaci if k.pewnosc == najwyzsza]

    if len(top_tier) >= 2:
        return STATUS_WIELU
    if najwyzsza < PEWNOSC_MIN_AUTOMATYCZNA:
        return STATUS_WIELU
    if najwyzsza == PEWNOSC_IEXACT:
        return STATUS_TWARDY
    return STATUS_ZGADYWANIE


def wybierz_autora_z_kandydatow(kandydaci, status):
    """Autor materializowany z listy kandydatów dla statusu twardy/zgadywanie
    (pierwszy = najpewniejszy, lista DESC po ``pewnosc``). Dla ``wielu``/``brak``
    → ``None`` (decyzję podejmuje user). Wspólne źródło reguły dla analizy (T7)
    i re-matchu inline (T10), żeby ``kandydaci[0].autor if status in {...}`` nie
    było powielone w dwóch miejscach."""
    if status in (STATUS_TWARDY, STATUS_ZGADYWANIE) and kandydaci:
        return kandydaci[0].autor
    return None


def odtworz_autor_jednostka(row, autor):
    """Po zmianie autora wiersza (wybór kandydata T9 / korekta inline T10)
    ustawia powiązanie ``Autor_Jednostka`` i porządkuje ``diff_do_utworzenia``:

    - ZAWSZE zdejmuje ewentualny nieaktualny wpis ``autor_jednostka`` (odłożony
      dla POPRZEDNIEGO autora) — inaczej integracja (``_materializuj_diff``)
      utworzyłaby AJ dla już-nie-autora wiersza i nadpisała ``row.autor_jednostka``
      (korupcja danych: dane zatrudnienia nowego autora lądują u starego),
    - gdy AJ ``(autor, jednostka)`` istnieje: podpina je i przelicza
      ``zmiany_potrzebne`` z realnej różnicy (``check_if_integration_needed`` czyta
      ``self.autor_jednostka``, więc nie może zostać ``None``),
    - gdy AJ brak: odkłada create w ``diff_do_utworzenia`` i ustawia
      ``zmiany_potrzebne=True`` (integracja zmaterializuje AJ przez ``get_or_create``).

    NIE zapisuje wiersza — caller składa ``save``/``update_fields``. Caller MUSI
    ustawić ``row.autor = autor`` PRZED wywołaniem (``check_if_integration_needed``
    czyta ``self.autor``). Jedyna funkcja w module sięgająca ORM: import
    ``Autor_Jednostka`` jest LAZY (w ciele), więc ładowanie modułu pozostaje
    ORM-free i ``models.py`` dalej może importować ``STATUS_*``.
    """
    from bpp.models import Autor_Jednostka

    row.diff_do_utworzenia.pop("autor_jednostka", None)
    aj = Autor_Jednostka.objects.filter(autor=autor, jednostka=row.jednostka).first()
    row.autor_jednostka = aj
    if aj is None:
        row.diff_do_utworzenia["autor_jednostka"] = {
            "autor": autor.pk,
            "jednostka": row.jednostka_id,
        }
        row.zmiany_potrzebne = True
    else:
        row.zmiany_potrzebne = bool(row.diff_do_utworzenia) or (
            row.check_if_integration_needed()
        )
