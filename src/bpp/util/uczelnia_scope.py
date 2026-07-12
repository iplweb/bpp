"""Zawężanie querysetów Rekordów do uczelni oglądającego (multi-hosted, read-side).

Jedno źródło reguły rekordowej + guard single-install. Reguła atrybucji =
strona główna (``get_uczelnia_context_data``): rekord należy do uczelni, gdy
którakolwiek z jednostek zapisanych na autorstwie należy do tej uczelni.
BEZ ``skupia_pracownikow`` (włącznie z obcą jednostką) — świadoma decyzja
(spec R3a).
"""


def tylko_jedna_uczelnia() -> bool:
    """True, gdy w systemie jest dokładnie jedna uczelnia.

    Fast-track jak ``IPunktacjaCacher._uczelnie_do_przeliczenia``: przy jednej
    uczelni filtr per-uczelnia jest no-op, więc pomijamy go (i kosztowny JOIN).
    """
    from bpp.models import Uczelnia

    return Uczelnia.objects.count() == 1


def scope_rekord_do_uczelni(qs, uczelnia):
    """Zawęź queryset ``Rekord`` do uczelni oglądającego.

    No-op (zwraca ten sam qs) gdy brak uczelni (brak mapowania Site→Uczelnia)
    albo gdy w systemie jest dokładnie jedna uczelnia — wynik identyczny,
    a unikamy JOIN-a przez M2M ``autorzy`` + ``DISTINCT``.
    """
    if uczelnia is None or tylko_jedna_uczelnia():
        return qs
    return qs.filter(autorzy__jednostka__uczelnia=uczelnia).distinct()


def scope_autor_do_uczelni(qs, uczelnia):
    """Zawęź queryset ``Autor`` do uczelni oglądającego (multi-hosted).

    Atrybucja jak ``AutorQuerySet.kiedykolwiek_zwiazani``: autor należy do
    uczelni, gdy jego aktualna LUB którakolwiek historyczna jednostka
    (``autor_jednostka``) należy do tej uczelni.

    No-op (zwraca ten sam qs) gdy brak uczelni (brak mapowania Site→Uczelnia)
    albo gdy w systemie jest dokładnie jedna uczelnia — spójnie z resztą API
    (żaden filtr izolacji nie „gryzie" w single-install).
    """
    if uczelnia is None or tylko_jedna_uczelnia():
        return qs
    from django.db.models import Q

    return qs.filter(
        Q(aktualna_jednostka__uczelnia=uczelnia)
        | Q(autor_jednostka__jednostka__uczelnia=uczelnia)
    ).distinct()


def scope_autorzy_do_uczelni(qs, uczelnia):
    """Zawęź queryset ``Autorzy`` (mat-view autorstwa) do uczelni oglądającego.

    Atrybucja przez jednostkę zapisaną na autorstwie (``jednostka__uczelnia``).
    Autorstwa bez jednostki nie dają się przypisać do żadnej uczelni → w
    trybie multi-host wypadają (fail-closed: lepiej ukryć nieprzypisane niż
    wyciekać cudzą uczelnię).

    No-op (zwraca ten sam qs) gdy brak uczelni albo gdy w systemie jest
    dokładnie jedna uczelnia.
    """
    if uczelnia is None or tylko_jedna_uczelnia():
        return qs
    return qs.filter(jednostka__uczelnia=uczelnia)


def scope_jednostki_do_uczelni(qs, uczelnia):
    """Zawęź queryset ``Jednostka`` do uczelni oglądającego (multi-hosted).

    Atrybucja przez bezpośredni FK ``Jednostka.uczelnia``. Constraint w
    ``Jednostka.uczelnia`` jest źródłem prawdy atrybucji; historyczna metryczka
    ``Jednostka_Rodzic`` nie waliduje już równości uczelni (federacja, #438),
    więc dla jednostek z wydziałem wynik jest tożsamy z filtrem po wydziale;
    jednostki bez wydziału, należące do uczelni, pozostają widoczne.

    No-op (zwraca ten sam qs) gdy brak uczelni (brak mapowania Site→Uczelnia)
    albo gdy w systemie jest dokładnie jedna uczelnia — wynik identyczny.
    """
    if uczelnia is None or tylko_jedna_uczelnia():
        return qs
    return qs.filter(uczelnia=uczelnia)
