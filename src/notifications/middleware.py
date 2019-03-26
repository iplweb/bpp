from django.utils.deprecation import MiddlewareMixin
from messages_extends.models import Message

class NotificationsMiddleware(MiddlewareMixin):
    def process_request(self, request):
        """After entering a web page, we may want to mark some messages as read
        basing on the URL they contain.
        """

        # request.user may be a SimpleLazyObject instance
        try:
            user_id = request.user.pk
        except AttributeError:
            return

        if user_id is None:
            return

        url = request.get_full_path()
        Message.objects.filter(user_id=user_id, read=False, message__icontains=url).update(read=True)
