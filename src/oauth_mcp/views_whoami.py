from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from oauth_mcp.authentication import StrictOAuth2Authentication


class WhoAmIView(APIView):
    """Preflight tożsamości dla bpp-mcp (spec §5.4d).

    Ważny token → 200 z tożsamością; brak/nieważny → 401 (transportowy,
    mapowalny przez klienta MCP na re-auth). Świadomie NIE dopuszczamy
    anonimowego 200.
    """

    authentication_classes = [StrictOAuth2Authentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        return Response(
            {
                "id": u.pk,
                "username": u.get_username(),
                "is_staff": u.is_staff,
                "is_superuser": u.is_superuser,
            }
        )
