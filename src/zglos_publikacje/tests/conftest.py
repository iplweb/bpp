import pytest


@pytest.fixture
def autor_jan_kowalski(autor_jan_kowalski, jednostka):
    """FD#640: w formularzu zgłoszenia autor bez żadnego przypisania to autor
    spoza uczelni — może mieć wyłącznie obcą jednostkę uczelni. Testy
    zgłoszeń używają Jana Kowalskiego jako zwykłego autora uczelni, więc
    przypisujemy go do jednostki uczelni."""
    from bpp.models import Autor_Jednostka

    Autor_Jednostka.objects.get_or_create(autor=autor_jan_kowalski, jednostka=jednostka)
    autor_jan_kowalski.refresh_from_db()
    return autor_jan_kowalski
