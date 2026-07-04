def orcid_auth_status(request):
    """Provides ORCID authentication status to templates."""
    from bpp.models import Uczelnia

    uczelnia = Uczelnia.objects.get_for_request(request)
    return {
        "orcid_login_enabled": uczelnia.orcid_enabled if uczelnia else False,
    }
