# -*- encoding: utf-8 -*-
from django import shortcuts
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

import json
from django import http


class JsonResponse(HttpResponse):
    """
        JSON response
    """
    def __init__(self, content, status=None, content_type=None):
        super(JsonResponse, self).__init__(
            content=json.dumps(content),
            status=status,
            content_type=content_type,
        )


class JSONResponseMixin(object):
    def render_to_response(self, context):
        "Returns a JSON response containing 'context' as payload"
        return self.get_json_response(self.convert_context_to_json(context))

    def get_json_response(self, content, **httpresponse_kwargs):
        "Construct an `HttpResponse` object."
        return http.HttpResponse(content,
                                 content_type='application/json',
                                 **httpresponse_kwargs)

    def convert_context_to_json(self, context):
        "Convert the context dictionary into a JSON object"
        # Note: This is *EXTREMELY* naive; in reality, you'll need
        # to do much more complex handling to ensure that arbitrary
        # objects -- such as Django model instances or querysets
        # -- can be serialized as JSON.
        return json.dumps(context)


@login_required
def charmap(request):
    return shortcuts.render(request, "charmap.html", dict(
        choosen=None, fieldId=request.GET.get('fieldId'),
        active=request.user.active_charmap_tab
    ))

@login_required
def charmap_update_setting(request):
    try:
        request.user.active_charmap_tab = int(request.GET.get('active_tab'))
    except (TypeError, ValueError):
        return
    request.user.save()
    return JsonResponse(dict(status='ok'))
