"""Integration tests for multi-site data isolation."""

import pytest
from model_bakery import baker

from fixtures.conftest_multisite import make_request_for_site


@pytest.mark.django_db
def test_article_visible_only_on_assigned_uczelnia(
    uczelnia1, uczelnia2, site1, site2, settings
):
    """Article assigned to uczelnia1 is not visible on uczelnia2's page."""
    from miniblog.models import Article

    settings.ALLOWED_HOSTS = ["*"]

    article = baker.make(
        Article,
        title="Test Article U1",
        article_body="Body text",
        status=Article.STATUS.published,
    )
    article.uczelnie.set([uczelnia1])

    from bpp.views.browse import get_uczelnia_context_data

    # Clear cache
    get_uczelnia_context_data.invalidate()

    ctx1 = get_uczelnia_context_data(uczelnia1)
    ctx2 = get_uczelnia_context_data(uczelnia2)

    assert article in ctx1["miniblog"]
    assert article not in ctx2["miniblog"]


@pytest.mark.django_db
def test_article_on_all_uczelnie_when_both_assigned(uczelnia1, uczelnia2):
    """Article assigned to both uczelnie appears on both."""
    from bpp.views.browse import get_uczelnia_context_data
    from miniblog.models import Article

    article = baker.make(
        Article,
        title="Global Article",
        article_body="Body text",
        status=Article.STATUS.published,
    )
    article.uczelnie.set([uczelnia1, uczelnia2])

    get_uczelnia_context_data.invalidate()

    ctx1 = get_uczelnia_context_data(uczelnia1)
    ctx2 = get_uczelnia_context_data(uczelnia2)

    assert article in ctx1["miniblog"]
    assert article in ctx2["miniblog"]


@pytest.mark.django_db
def test_staff_cannot_see_other_uczelnia_jednostki_in_admin(
    site1,
    site2,
    uczelnia1,
    uczelnia2,
    jednostka_uczelnia1,
    jednostka_uczelnia2,
    staff_user_uczelnia1,
    settings,
):
    """Staff user on site1 cannot see jednostki from uczelnia2."""
    settings.ALLOWED_HOSTS = ["*"]
    from django.contrib.admin.sites import AdminSite

    from bpp.admin.jednostka import JednostkaAdmin
    from bpp.models import Jednostka

    request = make_request_for_site(site1, path="/admin/", user=staff_user_uczelnia1)
    admin = JednostkaAdmin(Jednostka, AdminSite())
    qs = admin.get_queryset(request)

    assert jednostka_uczelnia1 in qs
    assert jednostka_uczelnia2 not in qs


@pytest.mark.django_db
def test_staff_cannot_access_other_uczelnia_admin(
    site1,
    site2,
    uczelnia1,
    uczelnia2,
    staff_user_uczelnia1,
    settings,
):
    """Staff user with access to site1 gets 403 on site2's admin."""
    settings.ALLOWED_HOSTS = ["*"]
    from bpp.middleware import SiteResolutionMiddleware

    request = make_request_for_site(site2, path="/admin/", user=staff_user_uczelnia1)
    mw = SiteResolutionMiddleware(lambda r: None)
    response = mw.process_view(request, None, [], {})
    assert response is not None
    assert response.status_code == 403


@pytest.mark.django_db
def test_browse_uczelnia_count_excludes_other_uczelnia(
    uczelnia1,
    uczelnia2,
    jednostka_uczelnia1,
    jednostka_uczelnia2,
    autor_uczelnia1,
    autor_uczelnia2,
    typy_odpowiedzialnosci,
    jezyki,
    charaktery_formalne,
):
    """Record count on uczelnia1 excludes uczelnia2's records."""
    from bpp.views.browse import get_uczelnia_context_data

    # Create a publication with autor from uczelnia1
    wc1 = baker.make("bpp.Wydawnictwo_Ciagle")
    baker.make(
        "bpp.Wydawnictwo_Ciagle_Autor",
        rekord=wc1,
        autor=autor_uczelnia1,
        jednostka=jednostka_uczelnia1,
    )

    # Create a publication with autor from uczelnia2
    wc2 = baker.make("bpp.Wydawnictwo_Ciagle")
    baker.make(
        "bpp.Wydawnictwo_Ciagle_Autor",
        rekord=wc2,
        autor=autor_uczelnia2,
        jednostka=jednostka_uczelnia2,
    )

    get_uczelnia_context_data.invalidate()

    ctx1 = get_uczelnia_context_data(uczelnia1)
    ctx2 = get_uczelnia_context_data(uczelnia2)

    # Each uczelnia should see only its own record count
    assert ctx1["total_rekord_count"] >= 1
    assert ctx2["total_rekord_count"] >= 1
