def uczelnie_rekordu(rec):
    """Zwróć zbiór Uczelni, do których rekord jest afiliowany.

    Dwa kształty:
    - rekordy z autorami przez through-model (`autorzy_set`): bierzemy
      uczelnię z jednostki każdego powiązania autora,
    - rekordy z własnym FK `jednostka` (doktoraty, habilitacje).
    """
    uczelnie = set()

    autorzy_set = getattr(rec, "autorzy_set", None)
    if autorzy_set is not None and hasattr(autorzy_set, "all"):
        qs = autorzy_set.select_related("jednostka__uczelnia").all()
        for powiazanie in qs:
            jednostka = getattr(powiazanie, "jednostka", None)
            if jednostka and jednostka.uczelnia_id:
                uczelnie.add(jednostka.uczelnia)
        if uczelnie:
            return uczelnie

    jednostka = getattr(rec, "jednostka", None)
    if jednostka and getattr(jednostka, "uczelnia_id", None):
        uczelnie.add(jednostka.uczelnia)

    return uczelnie
