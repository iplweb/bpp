"""Wspólny punkt prawdy o lokalizacji tymczasowego storage kreatora zgłoszeń.

Pliki tymczasowe (in-flight w kreatorze) trzymamy w OSOBNYM katalogu niż
pliki trwałe ukończonych zgłoszeń (`upload_to = protected/zglos_publikacje/`).
Dzięki temu komenda czyszcząca sieroty (`wyczysc_zglos_tmp`) może kasować po
wieku, mając gwarancję z konstrukcji, że nigdy nie tknie pliku realnego
zgłoszenia — w tym katalogu trwałych plików po prostu nie ma.

Lokalizacja liczona w runtime (nie zamrożona na import), żeby
`@override_settings(MEDIA_ROOT=...)` w testach działał.
"""

import os

from django.conf import settings

# Nazwa katalogu tmp — strażnik w komendzie cleanup weryfikuje ją przez
# równość basename (nie endswith), więc musi być stała i dokładna.
ZGLOS_TMP_DIRNAME = "zglos_publikacje_tmp"


def zglos_tmp_dir():
    """Bezwzględna ścieżka katalogu tmp uploadów kreatora zgłoszeń."""
    return os.path.join(settings.MEDIA_ROOT, "protected", ZGLOS_TMP_DIRNAME)
