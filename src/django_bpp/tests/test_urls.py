from django.urls import reverse


def test_toz_url_names_resolve_to_distinct_paths():
    ciagle = reverse("admin_bpp_wydawnictwo_ciagle_toz", args=[1])
    zwarte = reverse("admin_bpp_wydawnictwo_zwarte_toz", args=[1])
    patent = reverse("admin_bpp_patent_toz", args=[1])

    assert ciagle == "/admin/bpp/wydawnictwo_ciagle/toz/1/"
    assert zwarte == "/admin/bpp/wydawnictwo_zwarte/toz/1/"
    assert patent == "/admin/bpp/patent/toz/1/"
    assert len({ciagle, zwarte, patent}) == 3
