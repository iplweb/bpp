from django.apps import AppConfig


class TestBppConfig(AppConfig):
    """Aplikacja pomocnicza dostarczająca modele-doubles dla testów
    aplikacji ``long_running``. NIE USUWAĆ — patrz ``src/test_bpp/README.md``.
    """

    name = "test_bpp"
