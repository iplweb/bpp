"""Klasyfikacja tytułów naukowych/zawodowych z importu pracowników.

Wzorzec: ``import_common/core/jednostka.py`` (``sklasyfikuj_jednostke``).
Różnice względem jednostek:

- matchujemy po WSZYSTKICH ``bpp.Tytul`` (brak odpowiednika „puli afiliacyjnej"
  — każdy tytuł to poprawny cel dopasowania);
- dopasowanie DOKŁADNE liczymy po ``normalize_tytul`` OBU stron
  (``Tytul.nazwa``/``Tytul.skrot`` vs string z Excela), bo formy zapisu tytułu
  różnią się kropkami i wielkością liter (``"dr hab."`` == ``"Dr. Hab"`` ==
  ``"dr hab"``) — czego zwykły ``iexact`` w SQL nie złapie;
- próg zgadywania jest WYŻSZY (0.85) niż dla jednostek: tytuły to krótkie
  stringi, na których trigram łatwo daje fałszywe trafienia.
"""

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models.functions import Greatest

from bpp.models import Tytul

# Próg podobieństwa trigramowego, powyżej którego niedopasowany dokładnie tytuł
# uznajemy za „bardzo zbliżony" i wybieramy automatycznie (status
# ``zgadywanie``). Wyższy niż dla jednostek — tytuły są krótkie, więc trigram
# szybciej myli. Strojony w jednym miejscu.
PROG_ZGADYWANIA_TYTULU = 0.85

# Statusy klasyfikacji tytułu. Wartości CELOWO identyczne z
# ``import_pracownikow.pewnosc.STATUS_*`` (wspólne słownictwo), ale definiujemy
# je lokalnie: ``import_common`` to warstwa NIŻSZA i nie może importować w górę
# do ``import_pracownikow`` (cykl importów).
STATUS_TYTUL_TWARDY = "twardy"
STATUS_TYTUL_ZGADYWANIE = "zgadywanie"
STATUS_TYTUL_BRAK = "brak"


def normalize_tytul(s):
    """Kanonikalizacja tytułu DO PORÓWNANIA (nie zmienia zapisu w bazie).

    ``lower`` + ``strip`` + zwinięcie białych znaków (``" ".join(split())``) +
    usunięcie kropek. Dzięki temu ``"dr hab."``, ``"Dr. Hab"`` i ``"dr hab"``
    dają ten sam klucz porównawczy ``"dr hab"``. ``None``/pusty → ``""``.
    """
    if not s:
        return ""
    return " ".join(s.lower().replace(".", "").split())


def sklasyfikuj_tytul(tytul_str, *, prog=PROG_ZGADYWANIA_TYTULU):
    """Klasyfikuje tytuł z pliku BEZ rzucania wyjątków.

    Zwraca ``(tytul|None, status, similarity|None)``:

    - pusty/``None`` ``tytul_str`` → ``(None, "brak", None)``. To NORMALNY
      przypadek (wielu pracowników nie ma tytułu) — NIE tworzy decyzji ani nie
      jest liczony na kafelku; dlatego zwracamy BRAK od razu, jeszcze przed
      dotknięciem bazy.
    - dokładne dopasowanie po ``normalize_tytul`` (``Tytul.nazwa`` LUB
      ``Tytul.skrot``) → ``(t, "twardy", None)``;
    - inaczej najbliższy trigramowo (Greatest z nazwy i skrótu) ≥ ``prog`` →
      ``(best, "zgadywanie", sim)`` — auto-wybór do weryfikacji;
    - inaczej → ``(None, "brak", None)``.
    """
    if not tytul_str:
        return None, STATUS_TYTUL_BRAK, None
    norm = normalize_tytul(tytul_str)
    if not norm:
        return None, STATUS_TYTUL_BRAK, None

    # Dopasowanie DOKŁADNE po znormalizowanych OBU stronach. Robimy to w Pythonie
    # (a nie ``iexact`` w SQL), bo ``normalize_tytul`` usuwa kropki i zwija
    # spacje — czego Postgres ``iexact`` nie odwzorowuje. Tabela ``Tytul`` to
    # mały słownik kontrolowany (kilkadziesiąt wierszy), więc pętla jest tania.
    for t in Tytul.objects.all():
        if norm in (normalize_tytul(t.nazwa), normalize_tytul(t.skrot)):
            return t, STATUS_TYTUL_TWARDY, None

    # Brak trafienia dokładnego → najbliższy trigramowo spośród WSZYSTKICH
    # tytułów (bez „puli afiliacyjnej" — każdy tytuł to poprawny cel).
    best = (
        Tytul.objects.annotate(
            sim=Greatest(
                TrigramSimilarity("nazwa", norm),
                TrigramSimilarity("skrot", norm),
            )
        )
        .order_by("-sim")
        .first()
    )
    if best is not None and best.sim is not None and best.sim >= prog:
        return best, STATUS_TYTUL_ZGADYWANIE, float(best.sim)
    return None, STATUS_TYTUL_BRAK, None


def zaproponuj_skrot_tytulu(s):
    """Domyślna propozycja skrótu nowego tytułu: przycięta do ``max_length``
    pola ``Tytul.skrot`` (128) forma źródłowa. Excel podaje zwykle jedną formę
    (np. skrót ``"dr hab."``), a wartość jest edytowalna na ekranie decyzji.
    ``None``/pusty → ``""``.
    """
    return (s or "").strip()[:128]
