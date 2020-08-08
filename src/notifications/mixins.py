from notifications.core import convert_obj_to_channel_name


class ChannelSubscriberMixin:
    """Mixin który trzyma listę zasubskrybowanych obiektów i wyrzuca ją
    w context_data celem zarenderowania (i zasubskrybowania tych obiektów)
    po stronie HTMLu"""

    _subscribed_to = None
    channels_template_variable_name = "extraChannels"

    def subscribe_to(self, obj):
        if self._subscribed_to is None:
            self._subscribed_to = []
        cn = convert_obj_to_channel_name(obj)
        self._subscribed_to.append(cn)
        return cn

    def get_context_data(self, **kwargs):
        context = super(ChannelSubscriberMixin, self).get_context_data(**kwargs)
        context[self.channels_template_variable_name] = self._subscribed_to
        return context


class ChannelSubscriberSingleObjectMixin(ChannelSubscriberMixin):
    """Mixin ChannelSubscriber współpracujący z SingleObjectMixin, to znaczy
    subskrybujący kanał dla obiektu zwracanego w get_object"""

    def get_object(self, *args, **kw):
        obj = super(ChannelSubscriberSingleObjectMixin, self).get_object(*args, **kw)
        self.subscribe_to(obj)
        return obj
