from notifications.mixins import (
    ChannelSubscriberMixin,
    ChannelSubscriberSingleObjectMixin,
)
import pytest


@pytest.mark.django_db
def test_ChannelSubscriberMixin_subscribe_to(wydawnictwo_zwarte):
    x = ChannelSubscriberMixin()
    x.subscribe_to(wydawnictwo_zwarte)
    assert len(x._subscribed_to) == 1


@pytest.mark.django_db
def test_ChannelSubscriberMixin_get_context_data():
    class Foo:
        def get_context_data(self):
            return {"a": "B"}

    class Bar(ChannelSubscriberMixin, Foo):
        pass

    x = Bar()
    res = x.get_context_data()
    assert "extraChannels" in res.keys()


@pytest.mark.django_db
def test_ChannelSubscriberSingleObjectMixin(wydawnictwo_zwarte):
    class Foo:
        def get_object(self):
            return wydawnictwo_zwarte

    class Bar(ChannelSubscriberSingleObjectMixin, Foo):
        pass

    x = Bar()
    assert x.get_object() == wydawnictwo_zwarte
    assert len(x._subscribed_to) == 1
