from django.conf.urls import url


def bad_page(request):
    1 / 0


urlpatterns = [
    url(r'test_500', bad_page, name="test_500"),

    # Trzeba to dodać, inaczej rendering strony się wysypie
    url(r'noop', bad_page, name="password_change")
]
