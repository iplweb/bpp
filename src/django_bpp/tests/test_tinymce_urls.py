import pytest
from django.core.cache import cache
from django.urls import NoReverseMatch, reverse


@pytest.mark.parametrize(
    "name", ["tinymce-compressor", "tinymce-linklist", "tinymce-filebrowser"]
)
def test_tinymce_pomocnicze_trasy_nie_sa_montowane(name):
    with pytest.raises(NoReverseMatch):
        reverse(name)


@pytest.mark.django_db
def test_tinymce_compressor_niedostepny(client):
    cache.delete("abc")
    res = client.get("/tinymce/compressor/", {"js": "true", "plugins": "abc"})
    assert res.status_code == 404
    assert cache.get("abc") is None


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["flatpages_link_list/", "filebrowser/"])
def test_tinymce_pozostale_trasy_niedostepne(client, path):
    res = client.get(f"/tinymce/{path}")
    assert res.status_code == 404


@pytest.mark.django_db
def test_admin_jednostka_nadal_renderuje_widget_tinymce(admin_client, jednostka):
    url = reverse("admin:bpp_jednostka_change", args=[jednostka.pk])
    res = admin_client.get(url)
    assert res.status_code == 200
    content = res.content.decode()
    assert "/static/tinymce/tinymce.min." in content
    assert "django_tinymce/init_tinymce." in content
    assert "data-mce-conf" in content
