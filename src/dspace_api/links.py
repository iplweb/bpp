"""Budowanie publicznych linków do rekordów w repozytorium DSpace.

Link składamy z lokalnego resolvera handle danej instalacji:
``{baza}/handle/{handle}``, gdzie ``baza`` to adres API uczelni po odcięciu
sufiksu ``/server/api``. Lokalny resolver zawsze działa dla danej instalacji
(w przeciwieństwie do globalnego ``hdl.handle.net``, który wymaga rejestracji
prefiksu w CNRI)."""

from __future__ import annotations


def _frontend_base(endpoint: str) -> str:
    """Adres frontu DSpace wyprowadzony z adresu API."""
    base = (endpoint or "").strip().rstrip("/")
    if base.endswith("/server/api"):
        base = base[: -len("/server/api")]
    return base.rstrip("/")


def public_url_for_sent(sent) -> str | None:
    """Publiczny URL rekordu w repozytorium na podstawie ``SentToDSpace``.

    Zwraca ``None``, gdy brak handle lub brak skonfigurowanego endpointu."""
    handle = (sent.dspace_handle or "").strip()
    if not handle:
        return None
    base = _frontend_base(sent.uczelnia.dspace_api_endpoint)
    if not base:
        return None
    return f"{base}/handle/{handle}"


def public_links_for_rec(rec) -> list[tuple]:
    """Lista ``(Uczelnia, url)`` dla udanych wysyłek rekordu z handle.

    Jeden rekord może być wysłany do DSpace wielu uczelni — zwracamy wszystkie
    rozwiązywalne linki."""
    from django.contrib.contenttypes.models import ContentType

    from dspace_api.models import SentToDSpace

    ct = ContentType.objects.get_for_model(rec)
    wyniki = []
    qs = SentToDSpace.objects.filter(
        content_type=ct, object_id=rec.pk, submitted_successfully=True
    ).select_related("uczelnia")
    for sent in qs:
        url = public_url_for_sent(sent)
        if url:
            wyniki.append((sent.uczelnia, url))
    return wyniki
