"""``_send_notification_email`` nie może się wywrócić na autorze bez
jednostki — wtedy powiadomienie idzie do grupy obsługi zgłoszeń."""

from types import SimpleNamespace
from unittest import mock

from zglos_publikacje import views


class _Autorzy:
    def __init__(self, wpisy):
        self._wpisy = wpisy

    def all(self):
        return self

    def select_related(self, *args):
        return list(self._wpisy)


def _zgloszenie(*wpisy):
    return SimpleNamespace(
        zgloszenie_publikacji_autor_set=_Autorzy(wpisy),
        email="autor@example.com",
        tytul_oryginalny="Tytuł",
    )


def _wyslij(zgloszenie, rf):
    with (
        mock.patch.object(views, "send_templated_mail") as send,
        mock.patch.object(
            views,
            "zgloszenia_publikacji_emails",
            return_value=["grupa@example.com"],
        ),
    ):
        views._send_notification_email(zgloszenie, rf.get("/"))
    return send.call_args.kwargs["recipient_list"]


def test_autor_bez_jednostki_idzie_do_grupy(rf):
    zgloszenie = _zgloszenie(SimpleNamespace(jednostka_id=None, jednostka=None))

    assert _wyslij(zgloszenie, rf) == ["grupa@example.com"]


def test_autor_bez_jednostki_przed_autorem_z_jednostka(rf):
    korzen = object()
    jednostka = SimpleNamespace(skupia_pracownikow=True, get_root=lambda: korzen)
    zgloszenie = _zgloszenie(
        SimpleNamespace(jednostka_id=None, jednostka=None),
        SimpleNamespace(jednostka_id=1, jednostka=jednostka),
    )

    with mock.patch.object(
        views.Obslugujacy_Zgloszenia_Wydzialow.objects,
        "emaile_dla_obslugujacego",
        return_value=["wydzial@example.com"],
    ) as emaile:
        assert _wyslij(zgloszenie, rf) == ["wydzial@example.com"]

    emaile.assert_called_once_with(korzen)
