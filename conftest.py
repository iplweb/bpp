import pytest

NORMAL_DJANGO_USER_LOGIN = 'test_login_bpp'
NORMAL_DJANGO_USER_PASSWORD = 'test_password'

@pytest.fixture
def normal_django_user(request, db, django_user_model): # , django_username_field):
    """
    A normal Django user
    """
    UserModel = django_user_model
    # username_field = django_username_field

    try:
        obj = UserModel.objects.get(username=NORMAL_DJANGO_USER_LOGIN)
    except UserModel.DoesNotExist:
        obj = UserModel.objects.create_user(
            username=NORMAL_DJANGO_USER_LOGIN, password=NORMAL_DJANGO_USER_PASSWORD)

    def fin():
        obj.delete()

    return obj

def _preauth_session_id_helper(username, password, client, browser, live_server):
    client.login(username=username, password=password)
    browser.visit(live_server + '/favicon.ico') # /404-unexistent-WSZYSTKO-W-PORZADKU')
    browser.cookies.add({'sessionid': client.cookies['sessionid'].value})
    browser.visit(live_server + '/')
    return browser

@pytest.fixture
def preauth_browser(normal_django_user, client, browser, live_server):
    return _preauth_session_id_helper(
        NORMAL_DJANGO_USER_LOGIN, NORMAL_DJANGO_USER_PASSWORD, client,
        browser, live_server)

@pytest.fixture
def preauth_browser_admin(admin_user, client, browser, live_server):
    return _preauth_session_id_helper('admin', 'password', client, browser, live_server)
