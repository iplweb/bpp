from bpp.multiseek_registry.mixins import BppMultiseekVisibilityMixin


def test_BppMultiseekVisibilityMixin_request_none():
    b = BppMultiseekVisibilityMixin()

    b.public = True
    assert b.enable(None)

    b.public = False
    assert b.enable(None) is False
