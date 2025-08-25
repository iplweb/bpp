import gzip
import json as complexjson
from gzip import BadGzipFile

from crossref.restful import Works, build_url_endpoint
from requests.exceptions import JSONDecodeError as RequestsJSONDecodeError
from requests.utils import guess_json_utf


class PatchedWorks(Works):
    # To jest zabrane z Requests
    def json(self, content, encoding, **kwargs):
        r"""Returns the json-encoded content of a response, if any.

        :param \*\*kwargs: Optional arguments that ``json.loads`` takes.
        :raises requests.exceptions.JSONDecodeError: If the response body does not
            contain valid json.
        """

        if not encoding and content and len(content) > 3:
            # No encoding set. JSON RFC 4627 section 3 states we should expect
            # UTF-8, -16 or -32. Detect which one to use; If the detection or
            # decoding fails, fall back to `self.text` (using charset_normalizer to make
            # a best guess).
            encoding = guess_json_utf(content)
            if encoding is not None:
                try:
                    return complexjson.loads(content.decode(encoding), **kwargs)
                except UnicodeDecodeError:
                    # Wrong UTF codec detected; usually because it's not UTF-8
                    # but some other 8-bit codec.  This is an RFC violation,
                    # and the server didn't bother to tell us what codec *was*
                    # used.
                    pass
                except RequestsJSONDecodeError as e:
                    raise RequestsJSONDecodeError(e.msg, e.doc, e.pos)

        try:
            return complexjson.loads(content, **kwargs)
        except RequestsJSONDecodeError as e:
            # Catch JSON-related errors and raise as requests.JSONDecodeError
            # This aliases json.JSONDecodeError and simplejson.JSONDecodeError
            raise RequestsJSONDecodeError(e.msg, e.doc, e.pos)

    # A to jest zabrane z crossref.restful.Works
    def doi(self, doi, only_message=True):
        request_url = build_url_endpoint("/".join([self.ENDPOINT, doi]))
        request_params = {}
        result = self.do_http_request(
            "get",
            request_url,
            data=request_params,
            custom_header=self.custom_header,
            timeout=self.timeout,
        )

        if result.status_code == 404:
            return None

        if result.headers.get("content-encoding", "") == "gzip":
            try:
                content = gzip.decompress(result.content)
                result = self.json(content, result.encoding)
                return result["message"] if only_message is True else content
            except BadGzipFile:
                pass

        result = result.json()

        return result["message"] if only_message is True else result
