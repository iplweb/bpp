"""Raporty metryk per autor a autorzy spoza uczelni (FD#640).

Raport slotów autora, raport autora (``nowe_raporty``) i podobne widoki
w publicznej części serwisu liczą sumy punktów / slotów / metryk dla
konkretnego autora. Dla autora spoza uczelni (``Autor.jest_spoza_uczelni``)
takich sum nie liczymy — formularze go nie przyjmują, a wejście wprost
z adresu (zakładka, stara sesja) jest odrzucane.
"""

from django.core.exceptions import ValidationError

KOMUNIKAT_RAPORT_AUTORA_SPOZA_UCZELNI = (
    "{autor} jest autorem spoza uczelni (jednostka obca) — raportów "
    "z punktacją, slotami i metrykami dla autorów spoza uczelni nie "
    "przygotowujemy."
)


def sprawdz_autora_raportu(autor, uczelnia):
    """``ValidationError`` z czytelnym komunikatem, gdy ``autor`` jest spoza
    ``uczelnia``; ``uczelnia=None`` przepuszcza (nikt nie jest obcy)."""
    if autor is not None and autor.jest_spoza_uczelni(uczelnia):
        raise ValidationError(
            KOMUNIKAT_RAPORT_AUTORA_SPOZA_UCZELNI.format(autor=autor),
            code="autor_spoza_uczelni",
        )
    return autor
