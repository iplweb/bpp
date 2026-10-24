"""Wykluczanie rekordów o statusach korekty ukrytych dla danego kanału
(oraz autorów ukrytych, ``pokazuj=False``).

Wspólny helper dla publicznych widoków, które listują rekordy (przeglądanie
po latach, strona główna, autocomplete'y). Reguła jest ta sama, co na
stronie rekordu (``PracaViewMixin``): statusy ukryte w kanale (domyślnie
``"podglad"``) są niewidoczne dla wszystkich POZA użytkownikami
z uprawnieniami redaktorskimi (``moze_wprowadzac_dane``).
"""


def ukryte_statusy_dla(request, kanal="podglad", uczelnia=None):
    """Lista PK statusów korekty ukrytych przed oglądającym ``request``.

    Pusta lista, gdy oglądający ma uprawnienia redaktorskie albo gdy nie da
    się ustalić uczelni. ``request=None`` oznacza odbiorcę publicznego
    (np. treść cache'owana wspólnie dla wszystkich).
    """
    from bpp.models import Uczelnia
    from bpp.permissions import moze_wprowadzac_dane

    user = getattr(request, "user", None)
    if user is not None and moze_wprowadzac_dane(user):
        return []

    if uczelnia is None:
        uczelnia = Uczelnia.objects.get_for_request(request)
    if uczelnia is None:
        return []

    return list(uczelnia.ukryte_statusy(kanal))


def wyklucz_ukryte_statusy(
    qs, request, kanal="podglad", uczelnia=None, lookup="status_korekty_id"
):
    """Zwróć ``qs`` bez rekordów o statusach ukrytych przed oglądającym.

    ``lookup`` to ścieżka ORM do PK statusu korekty (np.
    ``"rekord__status_korekty_id"`` dla modeli podrzędnych).
    """
    statusy = ukryte_statusy_dla(request, kanal=kanal, uczelnia=uczelnia)
    if not statusy:
        return qs
    return qs.exclude(**{f"{lookup}__in": statusy})


def ukryte_statusy_eksportu(request, kanal="podglad"):
    """Lista PK statusów korekty wykluczanych z eksportu plików (BibTeX/RIS).

    W odróżnieniu od :func:`ukryte_statusy_dla` reguła jest publiczna dla
    KAŻDEGO, także redaktora: plik wychodzi poza stronę (można go przekazać
    dalej, a plik z zadania w tle jest dostępny po UUID). Gdy nie da się
    ustalić uczelni, nie jest fail-open — zwraca statusy ukryte w danym
    kanale w KTÓREJKOLWIEK uczelni.
    """
    from bpp.models import Uczelnia

    uczelnia = Uczelnia.objects.get_for_request(request)
    if uczelnia is not None:
        return sorted(set(uczelnia.ukryte_statusy(kanal)))
    return statusy_ukryte_w_dowolnej_uczelni(kanal)


def statusy_ukryte_w_dowolnej_uczelni(kanal="podglad"):
    """PK statusów korekty ukrytych w danym kanale w KTÓREJKOLWIEK uczelni.

    Zakres fail-closed na wypadek, gdy uczelni nie da się ustalić.
    """
    from bpp.models import Ukryj_Status_Korekty

    return sorted(
        set(
            Ukryj_Status_Korekty.objects.filter(**{kanal: True}).values_list(
                "status_korekty_id", flat=True
            )
        )
    )


def widoczni_autorzy(qs, request, lookup="pokazuj"):
    """Zwróć ``qs`` zawężony do autorów widocznych dla oglądającego.

    Autor z ``pokazuj=False`` jest ukryty ze stron publicznych — widzi go
    tylko użytkownik z uprawnieniami redaktorskimi (``moze_wprowadzac_dane``);
    dla pozostałych (także ``request=None``) ``qs`` jest filtrowany do
    ``pokazuj=True``. Wspólna reguła dla strony autora, eksportu, sieci
    powiązań i autocomplete'ów.

    ``lookup`` to ścieżka ORM do flagi ``pokazuj`` (np. ``"autor__pokazuj"``
    dla modeli podrzędnych, jak ``Autor_Dyscyplina``).
    """
    from bpp.permissions import moze_wprowadzac_dane

    user = getattr(request, "user", None)
    if user is not None and moze_wprowadzac_dane(user):
        return qs
    return qs.filter(**{lookup: True})
