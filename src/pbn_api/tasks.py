"""Wsteczna kompatybilność — re-eksport kanonicznego zadania.

Historycznie ``pbn_api.tasks`` zawierało WŁASNĄ implementację
``download_institution_publications`` (osobny patcher tqdm, osobne
helpery), rozjeżdżającą się z bliźniaczą implementacją w
``pbn_downloader_app.tasks``. To była duplikacja dwóch torów tego samego
pobierania. Kanoniczna, jedyna implementacja żyje teraz w
``pbn_downloader_app.tasks`` — tutaj tylko re-eksport, żeby nie zepsuć
ewentualnych importów ``from pbn_api.tasks import ...``.
"""

from pbn_downloader_app.tasks import (  # noqa: F401
    download_institution_publications,
)

__all__ = ["download_institution_publications"]
