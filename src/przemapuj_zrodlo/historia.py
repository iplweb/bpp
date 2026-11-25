"""Opis źródła we wpisach historii przemapowań (FD#508)."""


def opis_zrodla(zrodlo, *, pbn_uid=False):
    """„Nazwa” (ID …) — nazwa z identyfikatorem BPP, bo dwa źródła mogą
    nazywać się tak samo (scalanie duplikatów dałoby „Gazeta” → „Gazeta”).
    ``pbn_uid=True`` dokłada UID czasopisma w PBN.
    """
    if zrodlo is None:
        return "[źródło usunięte]"
    dopisek = f"ID {zrodlo.pk}"
    if pbn_uid and zrodlo.pbn_uid_id:
        dopisek += f", PBN UID {zrodlo.pbn_uid_id}"
    return f"„{zrodlo}” ({dopisek})"
