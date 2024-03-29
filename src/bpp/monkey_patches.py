from asgiref.sync import sync_to_async

# https://stackoverflow.com/questions/71952949/serving-file-asyncronously-with-django-and-uvicorn

# https://github.com/django/channels/issues/1722


def patch_sync_to_async(*args, **kwargs):
    """
    Monkey Patch the sync_to_async decorator
    ---------------------------------------
    ASGIRef made a change in their defaults that has caused major problems
    for channels. The decorator below needs to be updated to use
    thread_sensitive=False, thats why we are patching it on our side for now.
    https://github.com/django/channels/blob/main/channels/http.py#L220
    """
    kwargs["thread_sensitive"] = False
    return sync_to_async(*args, **kwargs)
