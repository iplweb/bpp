# -*- encoding: utf-8 -*-

def test_loginas(admin_app, admin_user, normal_django_user):
    res = admin_app.get("/")
    assert "zalogowany/a jako %s" % admin_user.username in res.content

    # robimy SUDO
    res = admin_app.get("/login/user/%i/" % normal_django_user.pk)
    res = admin_app.get("/")
    assert "zalogowany/a jako %s" % admin_user.username not in res.content
    assert "zalogowany/a jako %s" % normal_django_user.username in res.content

