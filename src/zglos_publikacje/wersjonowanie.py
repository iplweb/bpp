"""Wersjonowanie zgłoszeń publikacji (django-reversion, FD#587).

Razem ze zgłoszeniem wersjonowani są zgłoszeni autorzy. Załączniki (pliki)
NIE są śledzone — przywrócenie wersji nie przywraca usuniętych plików.
"""

from bpp.wersjonowanie import zarejestruj_wersjonowanie
from zglos_publikacje.models import Zgloszenie_Publikacji

zarejestruj_wersjonowanie(
    Zgloszenie_Publikacji, follow=("zgloszenie_publikacji_autor_set",)
)
