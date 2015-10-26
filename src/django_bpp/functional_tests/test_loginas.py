# -*- encoding: utf-8 -*-

def test_loginas(preauth_webtest_admin_app, admin_user, normal_django_user):
    res = preauth_webtest_admin_app.get("/")
    assert "zalogowany/a jako %s" % admin_user.username in res.content

    # robimy SUDO
    res = preauth_webtest_admin_app.get("/login/user/%i/" % normal_django_user.pk)
    res = preauth_webtest_admin_app.get("/")
    assert "zalogowany/a jako %s" % admin_user.username not in res.content
    assert "zalogowany/a jako %s" % normal_django_user.username in res.content

