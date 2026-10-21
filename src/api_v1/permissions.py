from rest_framework.exceptions import NotAuthenticated, NotFound
from rest_framework.permissions import BasePermission

from bpp.const import GR_RAPORTY_WYSWIETLANIE
from bpp.models import Uczelnia
from bpp.models.uczelnia import GrupaApiV1
from bpp.views.zapytanie import user_can_use_query_editor

KOMUNIKAT_GLOWNY = "REST API tego serwisu zostało wyłączone przez administratora."
KOMUNIKAT_GRUPA = (
    "Ta część REST API została wyłączona przez administratora tego serwisu."
)
KOMUNIKAT_ZALOGOWANI = (
    "REST API tego serwisu jest dostępne wyłącznie dla zalogowanych użytkowników."
)


class BramkaApiV1(BasePermission):
    """Bramka ``/api/v1/`` — sześć przełączników z obiektu ``Uczelnia``.

    Kolejność rozstrzygania:

    1. uczelnia nierozstrzygnięta (pusta baza, kreator konfiguracji, brak
       mapowania Site→Uczelnia) → przepuszczamy, bo nie ma kto podjąć
       decyzji, a świeża instalacja musi działać;
    2. grupa ``KAFELKI`` → rozstrzyga wyłącznie ``api_v1_kafelki``;
    3. główny wyłącznik → 404;
    4. przełącznik grupy → 404;
    5. ograniczenie do zalogowanych → 401.

    Krok 2 świadomie łamie hierarchię: widget ``embed/bpp-publikacje.js``
    wisi na publicznych stronach WWW jednostek, których administrator BPP
    nie kontroluje, więc wyłączenie API nie może po cichu psuć cudzych
    stron. Jest pierwszym testem przełączników i kończy się wcześnie po to,
    żeby wyjątek był widoczny w jednym miejscu, a nie rozproszony po
    warunkach.

    Kolejność 4 → 5 pozwala anonimowi poznać stan grup (404 kontra 401).
    Przyjęte świadomie: stan grup nie jest tajemnicą, a odwrotna kolejność
    byłaby myląca — anonim dostawałby „zaloguj się" pod adresem, który po
    zalogowaniu i tak zwraca 404, bo grupa jest wyłączona dla wszystkich.

    Odmowy niosą klucz ``powod``. ``exception_handler`` DRF renderuje
    ``exc.detail`` bezpośrednio, gdy jest listą albo słownikiem, więc nie
    potrzeba własnego handlera ani nagłówków. Kontrakt dla klientów:
    **obecność klucza ``powod`` znaczy „to decyzja konfiguracyjna
    administratora, nie błąd"**. Odpowiedzi 404 spoza bramki
    (``pobierz_encje_lub_404`` — nieistniejąca albo ukryta encja) tego klucza
    nie mają i nie będą miały; dzięki temu widget rozstrzyga jednym testem
    obecności klucza, a nie listą znanych wartości.

    ``NotAuthenticated``, a nie ``PermissionDenied``: rzucenie wyjątku wprost
    omija ``APIView.permission_denied()``, więc ``PermissionDenied`` dałby
    zawsze 403 i zepsuł kontrakt ``whoami/`` (spec bpp-mcp §5.4d: brak tokenu
    → 401 mapowalne przez klienta MCP na ponowne logowanie).
    ``NotAuthenticated`` oddaje decyzję DRF-owi, a że
    ``StrictOAuth2Authentication`` jest pierwszym authenticatorem i dostarcza
    challenge ``Bearer``, efektywnym kodem jest 401 — spójnie z tym, co ten
    stack już robi dla ``IsAuthenticated``.
    """

    def __init__(self, grupa):
        self.grupa = grupa

    def has_permission(self, request, view):
        uczelnia = Uczelnia.objects.get_for_request(request)
        if uczelnia is None:
            return True

        if self.grupa is GrupaApiV1.KAFELKI:
            if not uczelnia.api_v1_kafelki:
                raise self._grupa_wylaczona()
            return True

        if not uczelnia.api_v1_wlaczone:
            raise NotFound({"detail": KOMUNIKAT_GLOWNY, "powod": "api_wylaczone"})

        if self.grupa is not None and not uczelnia.api_v1_grupa_wlaczona(self.grupa):
            raise self._grupa_wylaczona()

        if uczelnia.api_v1_tylko_zalogowani and not request.user.is_authenticated:
            raise NotAuthenticated(
                {"detail": KOMUNIKAT_ZALOGOWANI, "powod": "wymagane_zalogowanie"}
            )

        return True

    def _grupa_wylaczona(self) -> NotFound:
        return NotFound(
            {
                "detail": KOMUNIKAT_GRUPA,
                "powod": "grupa_wylaczona",
                "grupa": self.grupa.value,
            }
        )


class BramkaApiV1Mixin:
    """Dokleja :class:`BramkaApiV1` na początek uprawnień widoku.

    Przez ``get_permissions()``, a nie przez ``permission_classes`` — po
    pierwsze nie kasujemy deklaracji widoku (np. ``MoznaUzywacZapytania``
    w ``/zapytanie/``, ``IsGrupaRaportyWyswietlanie`` w raporcie slotów),
    po drugie bramka potrzebuje argumentu konstruktora, a DRF
    instancjonowałby klasę z ``permission_classes`` bezargumentowo.

    Grupa siedzi w atrybucie z prefiksem, bo mixin owija także klasy
    z innych aplikacji (``WhoAmIView`` z ``oauth_mcp``).
    """

    bramka_api_v1_grupa = None

    def get_permissions(self):
        return [BramkaApiV1(self.bramka_api_v1_grupa), *super().get_permissions()]


def z_bramka_api_v1(view_cls, grupa):
    """Zwróć podklasę ``view_cls`` objętą bramką, przypisaną do ``grupa``.

    ``grupa`` jest argumentem **wymaganym** (widoki bez grupy — root oraz
    ``whoami/`` — podają jawnie ``None``). Wartość domyślna odtworzyłaby
    furtkę o piętro niżej niż ``CustomRouter.register``: te dwa widoki są
    owijane bezpośrednio, z pominięciem routera.

    Podklasa, a nie mutacja ``view_cls`` w miejscu: viewsety bywają
    importowane i testowane bezpośrednio, a klasa ``WhoAmIView`` należy do
    innej aplikacji — doklejanie im uprawnień „z zewnątrz" byłoby zmianą
    globalną, widoczną poza ``/api/v1/``. Podklasa dotyczy wyłącznie tego,
    co realnie wisi pod tym prefiksem.
    """
    return type(
        view_cls.__name__,
        (BramkaApiV1Mixin, view_cls),
        {
            "__module__": view_cls.__module__,
            "__doc__": view_cls.__doc__,
            "bramka_api_v1_grupa": grupa,
        },
    )


class IsGrupaRaportyWyswietlanie(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_superuser or (
            GR_RAPORTY_WYSWIETLANIE
            in request.user.groups.values_list("name", flat=True)
        )


class MoznaUzywacZapytania(BasePermission):
    """Dostęp do DjangoQL po API = ten sam kontrakt co web-edytor:
    superuser albo staff w grupie „wprowadzanie danych"."""

    message = (
        "Wymagane konto redaktora (staff w grupie 'wprowadzanie danych') "
        "lub superusera."
    )

    def has_permission(self, request, view):
        return user_can_use_query_editor(request.user)
