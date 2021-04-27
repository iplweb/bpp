class PraceSerwisoweException(Exception):
    pass


class HttpException(Exception):
    def __init__(self, status_code, url, content):
        self.status_code = status_code
        self.url = url
        self.content = content


class AccessDeniedException(Exception):
    def __init__(self, url):
        self.url = url


class SciencistDoesNotExist(Exception):
    pass


class AuthenticationResponseError(Exception):
    pass


class IntegracjaWylaczonaException(Exception):
    pass


class SameDataUploadedRecently(Exception):
    pass
