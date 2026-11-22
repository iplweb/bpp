"""Wersjonowanie zgłoszeń publikacji (django-reversion, FD#587).

Razem ze zgłoszeniem wersjonowani są zgłoszeni autorzy i załączniki
(wiersze załączników — sama treść pliku nie jest częścią wersji).
"""

from bpp.wersjonowanie import zarejestruj_wersjonowanie
from zglos_publikacje.models import Zgloszenie_Publikacji

zarejestruj_wersjonowanie(
    Zgloszenie_Publikacji, follow=("zgloszenie_publikacji_autor_set", "zalaczniki")
)
