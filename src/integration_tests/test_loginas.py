# -*- encoding: utf-8 -*-
from django_bpp.selenium_util import wait_for_page_load


def test_loginas(live_server,
                 preauth_admin_browser,
                 admin_user,
                 normal_django_user):
    """
    :ptype admin_app: django_webtest.DjangoTestApp
    """
    assert u"zalogowany/a jako %s" % admin_user.username in \
           preauth_admin_browser.html

    with wait_for_page_load(preauth_admin_browser):
        preauth_admin_browser.visit(
            live_server.url + "/admin/bpp/bppuser/%s/change/" % \
                        normal_django_user.pk)

    with wait_for_page_load(preauth_admin_browser):
        preauth_admin_browser.find_by_id("loginas-link").click()

    assert u"zalogowany/a jako %s" % admin_user.username not in \
           preauth_admin_browser.html
    print("X" * 90)
    print("DEBUG")
    print(preauth_admin_browser.html)
    assert u"zalogowany/a jako %s" % normal_django_user.username in \
           preauth_admin_browser.html
