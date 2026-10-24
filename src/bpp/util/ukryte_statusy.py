"""Wykluczanie rekordów o statusach korekty ukrytych dla danego kanału.

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


def wyklucz_ukrytych_autorow(qs, request):
    """Zwróć queryset ``Autor`` bez autorów ukrytych przed oglądającym.

    Autor z ``pokazuj=False`` jest niewidoczny na stronach publicznych dla
    wszystkich POZA użytkownikami z uprawnieniami redaktorskimi
    (``moze_wprowadzac_dane``). ``request=None`` = odbiorca publiczny.
    Ta sama reguła obowiązuje na stronie autora (``AutorView``) i w eksporcie
    jego prac.
    """
    from bpp.permissions import moze_wprowadzac_dane

    user = getattr(request, "user", None)
    if user is not None and moze_wprowadzac_dane(user):
        return qs
    return qs.filter(pokazuj=True)
