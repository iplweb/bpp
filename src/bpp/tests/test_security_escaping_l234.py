"""Testy utwardzeń bezpieczeństwa L2-L4 (audyt SAST 2026-07)."""

import pytest
from model_bakery import baker

# --- L3: tytuł multiseek z POST bez sanityzacji ---------------------------


def test_sanitize_multiseek_title_usuwa_xss():
    """suggested-title z formularza wyszukiwania trafia do sesji i jest
    renderowany |safe — musi być sanityzowany (jak AJAX update_multiseek_title)."""
    from bpp.util import sanitize_multiseek_title

    out = sanitize_multiseek_title("<script>alert(1)</script>Raport słotów")
    assert "<script>" not in out
    assert "Raport" in out

    out2 = sanitize_multiseek_title('<img src=x onerror="alert(1)">')
    assert "onerror" not in out2


# --- L2: message.message wstrzykiwany do <script> -------------------------


def test_base_html_toast_uzywa_escapejs():
    """base.html wstrzykuje message.message do bloku <script>; musi używać
    escapejs (kontekst JS), nie |safe — inaczej </script> w komunikacie
    wyłamuje się z bloku.

    Czytamy plik wprost z dysku (nie przez loader) — dbtemplates może podać
    „base.html" z bazy, jeśli inny test go tam wgra (niedeterministyczne pod
    xdist)."""
    from pathlib import Path

    import django_bpp

    src = (
        Path(django_bpp.__file__).parent / "templates" / "base.html"
    ).read_text(encoding="utf-8")
    assert "message.message|just_single_quotes|safe" not in src
    assert "message.message|escapejs" in src


# --- L4: admin mark_safe f-string z nieescapowaną nazwą -------------------


@pytest.mark.django_db
def test_link_do_obiektu_escapuje_nazwe():
    """link_do_obiektu budował etykietę przez mark_safe(obj) — nazwa obiektu
    (np. nazwisko autora) trafiała do HTML bez escapowania (admin)."""
    from bpp.admin.helpers import link_do_obiektu
    from bpp.models import Autor

    autor = baker.make(
        Autor, nazwisko="<script>alert(1)</script>", imiona="J", tytul=None
    )
    link = str(link_do_obiektu(autor))

    assert "<script>" not in link
    assert "&lt;script&gt;" in link
